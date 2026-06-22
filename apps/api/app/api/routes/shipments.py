from __future__ import annotations

import logging
import os
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException, Response, UploadFile, status

from app.api.deps import CurrentUser, DbSession
from app.core.settings import get_settings
from app.db.session import SessionLocal
from app.models import DocumentType, DocumentUploadStatus, ExportShipment, ShipmentDocument
from app.repositories.shipment import DocumentRepository, ShipmentRepository
from app.schemas.shipment import (
    DocumentChecklist,
    DocumentResponse,
    HsnRateLookupResponse,
    ShipmentCreate,
    ShipmentResponse,
    ShipmentUpdate,
    VerificationReport,
)
from app.services import ocr_service
from app.services.checklist_service import generate_checklist
from app.services.groq_client import GroqClientError
from app.services.hsn_rate_service import estimate_incentives
from app.services.verification_service import run_verification

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


# ── HSN rate lookup (public — no auth required) ────────────────────────────────

@router.get("/hsn-rates", response_model=HsnRateLookupResponse)
def get_hsn_rates(hsn: str, fob_value: float | None = None) -> HsnRateLookupResponse:
    result = estimate_incentives(hsn_code=hsn, fob_value_usd=fob_value)
    return HsnRateLookupResponse(**result)


# ── Shipment CRUD ──────────────────────────────────────────────────────────────

@router.post("", response_model=ShipmentResponse, status_code=status.HTTP_201_CREATED)
def create_shipment(payload: ShipmentCreate, session: DbSession, current_user: CurrentUser) -> ShipmentResponse:
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


@router.get("", response_model=list[ShipmentResponse])
def list_shipments(session: DbSession, current_user: CurrentUser) -> list[ShipmentResponse]:
    repo = ShipmentRepository(
        session=session,
        tenant_id=current_user.organization.id,
        actor_user_id=current_user.user.id,
    )
    return [ShipmentResponse.model_validate(s) for s in repo.list()]


@router.get("/{shipment_id}", response_model=ShipmentResponse)
def get_shipment(shipment_id: UUID, session: DbSession, current_user: CurrentUser) -> ShipmentResponse:
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


@router.post("/{shipment_id}/documents", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
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
            detail=f"Unsupported file type: {file.content_type}. Allowed: PDF, JPEG, PNG, WEBP, Excel.",
        )

    contents = await file.read()
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds the 10 MB limit.",
        )

    upload_dir = os.path.join(settings.upload_dir, str(current_user.organization.id), str(shipment_id))
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, file.filename or "upload")
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
        file_name=file.filename or "upload",
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


@router.get("/{shipment_id}/documents", response_model=list[DocumentResponse])
def list_documents(shipment_id: UUID, session: DbSession, current_user: CurrentUser) -> list[DocumentResponse]:
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


# ── AI endpoints ───────────────────────────────────────────────────────────────

@router.get("/{shipment_id}/checklist", response_model=DocumentChecklist)
def get_checklist(shipment_id: UUID, session: DbSession, current_user: CurrentUser) -> DocumentChecklist:
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
def verify_shipment(shipment_id: UUID, session: DbSession, current_user: CurrentUser) -> VerificationReport:
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

    try:
        return run_verification(shipment, documents)
    except GroqClientError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e
