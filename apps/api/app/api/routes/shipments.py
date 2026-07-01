from __future__ import annotations

import csv
import logging
import os
import re
from decimal import Decimal
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse

from app.api.deps import CurrentUser, DbSession
from app.core.settings import get_settings
from app.db.session import SessionLocal
from app.models import (
    DiscrepancySeverity,
    DocumentType,
    DocumentUploadStatus,
    ExportDiscrepancy,
    ExportShipment,
    ShipmentDocument,
)
from app.repositories.shipment import (
    DocumentRepository,
    ExportDiscrepancyRepository,
    ShipmentRepository,
)
from app.schemas.shipment import (
    DocumentChecklist,
    DocumentResponse,
    HsnRateLookupResponse,
    ReconciliationIssueResponse,
    ReconciliationResponse,
    ShipmentCreate,
    ShipmentImportError,
    ShipmentImportResponse,
    ShipmentResponse,
    ShipmentUpdate,
    VerificationReport,
)
from app.services import ocr_service
from app.services.checklist_service import generate_checklist
from app.services.groq_client import GroqClientError
from app.services.hsn_rate_service import lookup_rates
from app.services.pdf_document_service import generate_shipment_pdf
from app.services.rate_governance import approved_current_rate_rows, latest_rate_by_scheme
from app.services.rate_limit import rate_limit_upload_requests
from app.services.verification_service import run_verification
from engine.reconciliation import ReconciliationInput, StructuredDocument, reconcile_shipment

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/shipments", tags=["shipments"])

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
REQUIRED_IMPORT_COLUMNS = {
    "exporter_name",
    "product_name",
    "hsn_code",
    "destination_country",
    "buyer_country",
    "incoterm",
    "payment_term",
    "shipment_mode",
    "shipment_stage",
}


def _safe_display_name(file_name: str | None) -> str:
    candidate = Path(file_name or "upload").name
    sanitized = re.sub(r"[^A-Za-z0-9._ -]", "_", candidate).strip(" .")
    return sanitized[:180] or "upload"


def _shipment_rows(file_name: str, contents: bytes) -> list[dict[str, Any]]:
    suffix = Path(file_name).suffix.lower()
    if suffix == ".csv":
        text = contents.decode("utf-8-sig")
        return [dict(row) for row in csv.DictReader(StringIO(text))]
    if suffix == ".xlsx":
        from openpyxl import load_workbook  # noqa: PLC0415

        workbook = load_workbook(BytesIO(contents), read_only=True, data_only=True)
        worksheet = workbook.active
        if worksheet is None:
            return []
        rows = worksheet.iter_rows(values_only=True)
        headers = [str(value or "").strip() for value in next(rows, ())]
        return [
            {headers[index]: value for index, value in enumerate(row) if index < len(headers)}
            for row in rows
        ]
    raise ValueError("Use a UTF-8 CSV or .xlsx workbook.")


def _normalize_import_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized = {
        str(key).strip().lower(): value
        for key, value in row.items()
        if key is not None and str(key).strip()
    }
    missing = sorted(
        column
        for column in REQUIRED_IMPORT_COLUMNS
        if normalized.get(column) is None or str(normalized[column]).strip() == ""
    )
    if missing:
        raise ValueError(f"Missing required columns/values: {', '.join(missing)}")
    for optional in (
        "container_type",
        "fob_value",
        "shipping_bill_no",
        "port_of_loading",
        "shipment_date",
    ):
        if normalized.get(optional) == "":
            normalized[optional] = None
    normalized.setdefault("invoice_currency", "USD")
    return normalized


# ── HSN rate lookup (public — no auth required) ────────────────────────────────


@router.get("/hsn-rates", response_model=HsnRateLookupResponse)
def get_hsn_rates(
    hsn: str,
    session: DbSession,
    current_user: CurrentUser,
    fob_value: float | None = None,
) -> HsnRateLookupResponse:
    result = lookup_rates(
        session=session,
        tenant_id=current_user.organization.id,
        hsn_code=hsn,
        fob_value=fob_value,
    )
    return HsnRateLookupResponse.model_validate(result)


# ── Shipment CRUD ──────────────────────────────────────────────────────────────


@router.post("", response_model=ShipmentResponse, status_code=status.HTTP_201_CREATED)
def create_shipment(
    payload: ShipmentCreate, session: DbSession, current_user: CurrentUser
) -> ShipmentResponse:
    repo = ShipmentRepository(
        session=session,
        tenant_id=current_user.organization.id,
        actor_user_id=current_user.user.id,
    )
    shipment = ExportShipment(tenant_id=current_user.organization.id, **payload.model_dump())
    repo.add(shipment)
    session.commit()
    session.refresh(shipment)
    return ShipmentResponse.model_validate(shipment)


@router.post(
    "/import",
    response_model=ShipmentImportResponse,
    dependencies=[Depends(rate_limit_upload_requests)],
)
async def import_shipments(
    file: UploadFile,
    session: DbSession,
    current_user: CurrentUser,
) -> ShipmentImportResponse:
    file_name = _safe_display_name(file.filename)
    contents = await file.read()
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Import file exceeds the 10 MB limit.",
        )
    try:
        rows = _shipment_rows(file_name, contents)
    except (UnicodeDecodeError, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error

    repository = ShipmentRepository(
        session=session,
        tenant_id=current_user.organization.id,
        actor_user_id=current_user.user.id,
    )
    created: list[ExportShipment] = []
    errors: list[ShipmentImportError] = []
    for row_number, raw_row in enumerate(rows, start=2):
        try:
            payload = ShipmentCreate.model_validate(_normalize_import_row(raw_row))
            shipment = ExportShipment(
                tenant_id=current_user.organization.id,
                **payload.model_dump(),
            )
            repository.add(shipment)
            created.append(shipment)
        except (ValueError, TypeError) as error:
            errors.append(ShipmentImportError(row=row_number, message=str(error)))

    session.commit()
    for shipment in created:
        session.refresh(shipment)
    return ShipmentImportResponse(
        created=len(created),
        failed=len(errors),
        shipments=[ShipmentResponse.model_validate(shipment) for shipment in created],
        errors=errors,
    )


@router.get("", response_model=list[ShipmentResponse])
def list_shipments(session: DbSession, current_user: CurrentUser) -> list[ShipmentResponse]:
    repo = ShipmentRepository(
        session=session,
        tenant_id=current_user.organization.id,
        actor_user_id=current_user.user.id,
    )
    return [ShipmentResponse.model_validate(s) for s in repo.list()]


@router.get("/{shipment_id}", response_model=ShipmentResponse)
def get_shipment(
    shipment_id: UUID, session: DbSession, current_user: CurrentUser
) -> ShipmentResponse:
    repo = ShipmentRepository(
        session=session,
        tenant_id=current_user.organization.id,
        actor_user_id=current_user.user.id,
    )
    shipment = repo.get(shipment_id)
    if shipment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shipment not found.")
    return ShipmentResponse.model_validate(shipment)


@router.patch("/{shipment_id}", response_model=ShipmentResponse)
def update_shipment(
    shipment_id: UUID,
    payload: ShipmentUpdate,
    session: DbSession,
    current_user: CurrentUser,
) -> ShipmentResponse:
    repo = ShipmentRepository(
        session=session,
        tenant_id=current_user.organization.id,
        actor_user_id=current_user.user.id,
    )
    shipment = repo.get(shipment_id)
    if shipment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shipment not found.")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(shipment, field, value)
    session.commit()
    session.refresh(shipment)
    return ShipmentResponse.model_validate(shipment)


@router.delete("/{shipment_id}")
def delete_shipment(shipment_id: UUID, session: DbSession, current_user: CurrentUser) -> Response:
    repo = ShipmentRepository(
        session=session,
        tenant_id=current_user.organization.id,
        actor_user_id=current_user.user.id,
    )
    shipment = repo.get(shipment_id)
    if shipment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shipment not found.")
    repo.delete(shipment)
    session.commit()
    return Response(status_code=204)


# ── Document upload ────────────────────────────────────────────────────────────


def _run_ocr_background(doc_id: UUID, file_path: str, mime_type: str | None) -> None:
    """Background task: extract fields from an uploaded document and persist results."""
    session = SessionLocal()
    try:
        doc = session.get(ShipmentDocument, doc_id)
        if doc is None:
            return
        fields = ocr_service.extract_fields(file_path=file_path, mime_type=mime_type)
        doc.extracted_fields = fields
        doc.upload_status = DocumentUploadStatus.EXTRACTED
        session.commit()
    except Exception as exc:
        logger.error("OCR background task failed for doc %s: %s", doc_id, exc)
        try:
            doc = session.get(ShipmentDocument, doc_id)
            if doc is not None:
                doc.upload_status = DocumentUploadStatus.FAILED
                session.commit()
        except Exception:
            pass
    finally:
        session.close()


@router.post(
    "/{shipment_id}/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit_upload_requests)],
)
async def upload_document(
    shipment_id: UUID,
    document_type: DocumentType,
    file: UploadFile,
    background_tasks: BackgroundTasks,
    session: DbSession,
    current_user: CurrentUser,
) -> DocumentResponse:
    settings = get_settings()

    shipment_repo = ShipmentRepository(
        session=session,
        tenant_id=current_user.organization.id,
        actor_user_id=current_user.user.id,
    )
    if shipment_repo.get(shipment_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shipment not found.")

    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Unsupported file type: {file.content_type}. "
                "Allowed: PDF, JPEG, PNG, WEBP, Excel."
            ),
        )

    contents = await file.read()
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds the 10 MB limit.",
        )

    display_name = _safe_display_name(file.filename)
    extension = Path(display_name).suffix.lower()
    storage_name = f"{UUID(bytes=os.urandom(16))}{extension}"
    upload_dir = os.path.join(
        settings.upload_dir, str(current_user.organization.id), str(shipment_id)
    )
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, storage_name)
    with open(file_path, "wb") as f:
        f.write(contents)

    doc_repo = DocumentRepository(
        session=session,
        tenant_id=current_user.organization.id,
        actor_user_id=current_user.user.id,
    )
    doc = ShipmentDocument(
        tenant_id=current_user.organization.id,
        shipment_id=shipment_id,
        document_type=document_type,
        file_name=display_name,
        file_path=file_path,
        file_size_bytes=len(contents),
        mime_type=file.content_type,
        upload_status=DocumentUploadStatus.PENDING,
    )
    doc_repo.add(doc)
    session.commit()
    session.refresh(doc)

    background_tasks.add_task(_run_ocr_background, doc.id, file_path, file.content_type)

    return DocumentResponse.model_validate(doc)


@router.post(
    "/{shipment_id}/documents/generate/{document_type}",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate_document(
    shipment_id: UUID,
    document_type: DocumentType,
    session: DbSession,
    current_user: CurrentUser,
) -> DocumentResponse:
    shipment_repo = ShipmentRepository(
        session=session,
        tenant_id=current_user.organization.id,
        actor_user_id=current_user.user.id,
    )
    shipment = shipment_repo.get(shipment_id)
    if shipment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shipment not found.")
    try:
        pdf_bytes = generate_shipment_pdf(shipment, document_type)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error

    settings = get_settings()
    upload_dir = os.path.join(
        settings.upload_dir,
        str(current_user.organization.id),
        str(shipment_id),
    )
    os.makedirs(upload_dir, exist_ok=True)
    file_name = f"{document_type.value.replace('_', '-')}-{shipment_id}.pdf"
    file_path = os.path.join(upload_dir, f"{UUID(bytes=os.urandom(16))}.pdf")
    with open(file_path, "wb") as generated_file:
        generated_file.write(pdf_bytes)

    repository = DocumentRepository(
        session=session,
        tenant_id=current_user.organization.id,
        actor_user_id=current_user.user.id,
    )
    stored = ShipmentDocument(
        tenant_id=current_user.organization.id,
        shipment_id=shipment_id,
        document_type=document_type,
        file_name=file_name,
        file_path=file_path,
        file_size_bytes=len(pdf_bytes),
        mime_type="application/pdf",
        upload_status=DocumentUploadStatus.EXTRACTED,
        extracted_fields={"generated_from_shipment": True},
    )
    repository.add(stored)
    session.commit()
    session.refresh(stored)
    return DocumentResponse.model_validate(stored)


@router.get("/{shipment_id}/documents/{document_id}/download")
def download_document(
    shipment_id: UUID,
    document_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
) -> FileResponse:
    shipment_repository = ShipmentRepository(
        session=session,
        tenant_id=current_user.organization.id,
        actor_user_id=current_user.user.id,
    )
    if shipment_repository.get(shipment_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shipment not found.")
    document_repository = DocumentRepository(
        session=session,
        tenant_id=current_user.organization.id,
        actor_user_id=current_user.user.id,
    )
    document = document_repository.get(document_id)
    if document is None or document.shipment_id != shipment_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    if not os.path.isfile(document.file_path):
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="The stored file is no longer available.",
        )
    return FileResponse(
        document.file_path,
        media_type=document.mime_type or "application/octet-stream",
        filename=document.file_name,
    )


@router.get("/{shipment_id}/documents", response_model=list[DocumentResponse])
def list_documents(
    shipment_id: UUID, session: DbSession, current_user: CurrentUser
) -> list[DocumentResponse]:
    shipment_repo = ShipmentRepository(
        session=session,
        tenant_id=current_user.organization.id,
        actor_user_id=current_user.user.id,
    )
    if shipment_repo.get(shipment_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shipment not found.")
    doc_repo = DocumentRepository(
        session=session,
        tenant_id=current_user.organization.id,
        actor_user_id=current_user.user.id,
    )
    return [DocumentResponse.model_validate(d) for d in doc_repo.list_for_shipment(shipment_id)]


@router.post("/{shipment_id}/reconcile", response_model=ReconciliationResponse)
def reconcile_export_shipment(
    shipment_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
) -> ReconciliationResponse:
    shipment_repository = ShipmentRepository(
        session=session,
        tenant_id=current_user.organization.id,
        actor_user_id=current_user.user.id,
    )
    shipment = shipment_repository.get(shipment_id)
    if shipment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shipment not found.")
    document_repository = DocumentRepository(
        session=session,
        tenant_id=current_user.organization.id,
        actor_user_id=current_user.user.id,
    )
    documents = document_repository.list_for_shipment(shipment_id)
    verified_rates = {
        row.scheme: Decimal(str(row.rate))
        for row in approved_current_rate_rows(
            session=session,
            tenant_id=current_user.organization.id,
            hsn_code=shipment.hsn_code,
        )
    }
    result = reconcile_shipment(
        ReconciliationInput(
            hsn_code=shipment.hsn_code,
            buyer_country=shipment.buyer_country,
            incoterm=shipment.incoterm,
            fob_value=(
                Decimal(str(shipment.fob_value))
                if shipment.fob_value is not None
                else None
            ),
            shipment_stage=shipment.shipment_stage.value,
            shipping_bill_no=shipment.shipping_bill_no,
            shipment_date=shipment.shipment_date,
            documents=[
                StructuredDocument(
                    document_type=document.document_type.value,
                    file_name=document.file_name,
                    fields=document.extracted_fields or {},
                )
                for document in documents
            ],
            verified_rates=verified_rates,
        )
    )
    stored = [
        ExportDiscrepancy(
            tenant_id=current_user.organization.id,
            shipment_id=shipment.id,
            type=issue.type,
            severity=DiscrepancySeverity(issue.severity),
            message=issue.message,
            suggested_fix=issue.suggested_fix,
            lock_risk=issue.lock_risk,
            potential_amount=issue.potential_amount,
        )
        for issue in result.issues
    ]
    discrepancy_repository = ExportDiscrepancyRepository(
        session=session,
        tenant_id=current_user.organization.id,
        actor_user_id=current_user.user.id,
    )
    discrepancy_repository.replace_for_shipment(
        shipment_id=shipment.id,
        discrepancies=stored,
    )
    session.commit()
    for discrepancy in stored:
        session.refresh(discrepancy)
    return ReconciliationResponse(
        shipment_id=shipment.id,
        discrepancies=[
            ReconciliationIssueResponse.model_validate(discrepancy)
            for discrepancy in stored
        ],
        potential_amount=float(result.potential_amount),
        disclaimer=(
            "Potential amounts use operator-verified rates but are not confirmed losses or claims. "
            "Add claimed and received amounts and verify with your CHA before acting."
        ),
    )


# ── AI endpoints ───────────────────────────────────────────────────────────────


@router.get("/{shipment_id}/checklist", response_model=DocumentChecklist)
def get_checklist(
    shipment_id: UUID, session: DbSession, current_user: CurrentUser
) -> DocumentChecklist:
    repo = ShipmentRepository(
        session=session,
        tenant_id=current_user.organization.id,
        actor_user_id=current_user.user.id,
    )
    shipment = repo.get(shipment_id)
    if shipment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shipment not found.")
    try:
        return generate_checklist(shipment)
    except GroqClientError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e


@router.get("/{shipment_id}/verify", response_model=VerificationReport)
def verify_shipment(
    shipment_id: UUID, session: DbSession, current_user: CurrentUser
) -> VerificationReport:
    shipment_repo = ShipmentRepository(
        session=session,
        tenant_id=current_user.organization.id,
        actor_user_id=current_user.user.id,
    )
    shipment = shipment_repo.get(shipment_id)
    if shipment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shipment not found.")

    doc_repo = DocumentRepository(
        session=session,
        tenant_id=current_user.organization.id,
        actor_user_id=current_user.user.id,
    )
    documents = doc_repo.list_for_shipment(shipment_id)
    latest_rows = latest_rate_by_scheme(
        approved_current_rate_rows(
            session=session,
            tenant_id=current_user.organization.id,
            hsn_code=shipment.hsn_code,
        )
    )
    rate_evidence = [
        {
            "scheme": row.scheme,
            "rate_percent": float(row.rate),
            "source": row.source,
            "source_url": row.source_url,
            "effective_date": row.effective_date.isoformat(),
            "version_stamp": row.version_stamp,
            "confidence": row.confidence,
            "review_status": row.review_status,
            "reviewed_by": row.reviewed_by,
            "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
            "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        }
        for row in latest_rows
    ]

    try:
        return run_verification(shipment, documents, rate_evidence=rate_evidence)
    except GroqClientError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e
