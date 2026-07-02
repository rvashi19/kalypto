# ruff: noqa: E501
"""Document Builder API — /api/v1/documents.

Eight endpoints:
  POST /documents/import/upload        — upload XLSX/CSV, get column preview
  POST /documents/import/{session_id}/confirm-mapping  — confirm column mapping
  POST /documents/validate             — validate shipment data without generating
  POST /documents/generate             — generate all requested doc types, return ZIP
  GET  /documents/packs                — list saved packs for current tenant
  GET  /documents/packs/{pack_id}      — pack detail + doc list
  GET  /documents/packs/{pack_id}/download  — re-download ZIP of generated docs
  DELETE /documents/packs/{pack_id}    — soft-archive a pack
"""

from __future__ import annotations

import io
import os
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.core.settings import get_settings
from app.models.documents import (
    DocumentImportSession,
    ExportDocumentPack,
    GeneratedExportDocument,
)
from app.schemas.documents import (
    GenerateRequest,
    GenerateResponse,
    GeneratedDocumentMeta,
    ImportSessionUploadResponse,
    MappingConfirmRequest,
    MappingConfirmResponse,
    PackDetail,
    PackSummary,
    ValidationIssue,
    ValidateRequest,
    ValidateResponse,
)
from app.services.document_generator import (
    SUPPORTED_DOC_TYPES,
    checksum,
    generate_document,
    generate_zip,
)
from app.services.document_sheet_parser import (
    detect_column_mapping,
    detect_missing_fields,
    parse_csv,
    parse_rows,
    parse_xlsx,
)
from app.services.document_validator import validate_shipment_data

router = APIRouter(prefix="/documents", tags=["documents"])

_IMPORT_SESSION_TTL_HOURS = 24
_ALLOWED_MIME = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "text/csv",
    "application/csv",
    "application/octet-stream",  # some clients send this for xlsx
}
_MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


def _storage_key(tenant_id: UUID, sub_path: str) -> str:
    return f"documents/{tenant_id}/{sub_path}"


def _save_file(storage_key: str, data: bytes) -> None:
    """Write bytes to local upload_dir. Replace with S3 put_object for cloud."""
    settings = get_settings()
    full_path = os.path.join(settings.upload_dir, storage_key)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "wb") as f:
        f.write(data)


def _load_file(storage_key: str) -> bytes:
    settings = get_settings()
    full_path = os.path.join(settings.upload_dir, storage_key)
    if not os.path.exists(full_path):
        raise FileNotFoundError(storage_key)
    with open(full_path, "rb") as f:
        return f.read()


def _assert_pack_owner(pack: ExportDocumentPack, ctx: Any) -> None:
    if pack.tenant_id != ctx.organization.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pack not found.")


# ── 1. Upload spreadsheet ─────────────────────────────────────────────────────

@router.post("/import/upload", response_model=ImportSessionUploadResponse)
async def upload_import_file(
    file: UploadFile = File(...),
    sheet_name: str | None = Form(default=None),
    db: DbSession = ...,
    ctx: CurrentUser = ...,
) -> ImportSessionUploadResponse:
    raw = await file.read()
    if len(raw) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File exceeds 10 MB limit.")

    filename = file.filename or "upload"
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext not in ("xlsx", "csv"):
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Only .xlsx and .csv files are accepted.")

    if ext == "xlsx":
        headers, rows, sheet_names = parse_xlsx(raw, sheet_name)
        file_type = "xlsx"
    else:
        headers, rows = parse_csv(raw)
        sheet_names = []
        file_type = "csv"

    if not headers:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Could not detect headers in the uploaded file.")

    mapping, unmatched = detect_column_mapping(headers)
    items = parse_rows(rows[:5], mapping)  # preview: first 5 data rows
    missing = detect_missing_fields(parse_rows(rows, mapping))

    session_id = uuid.uuid4()
    storage_key = _storage_key(ctx.organization.id, f"import/{session_id}.{ext}")
    _save_file(storage_key, raw)

    warnings: list[dict[str, str]] = []
    if unmatched:
        warnings.append({"code": "UNMATCHED_COLS", "message": f"Unrecognised columns (will be ignored): {', '.join(unmatched)}", "severity": "info"})
    if missing:
        warnings.append({"code": "MISSING_FIELDS", "message": f"Missing or unmapped required fields: {', '.join(missing)}", "severity": "warning"})

    session = DocumentImportSession(
        id=session_id,
        tenant_id=ctx.organization.id,
        user_id=ctx.user.id,
        original_filename=filename,
        file_type=file_type,
        sheet_name=sheet_name,
        detected_columns_json=headers,
        suggested_mapping_json=mapping,
        parsed_preview_json=items,
        raw_file_storage_key=storage_key,
        status="uploaded",
        warnings_json=warnings,
        expires_at=datetime.now(UTC) + timedelta(hours=_IMPORT_SESSION_TTL_HOURS),
    )
    db.add(session)
    db.commit()

    return ImportSessionUploadResponse(
        session_id=session_id,
        original_filename=filename,
        file_type=file_type,
        sheet_names=sheet_names,
        detected_columns=headers,
        suggested_mapping=mapping,
        parsed_preview=items,
        warnings=warnings,
        status="uploaded",
    )


# ── 2. Confirm column mapping ────────────────────────────────────────────────

@router.post("/import/{session_id}/confirm-mapping", response_model=MappingConfirmResponse)
def confirm_mapping(
    session_id: UUID,
    body: MappingConfirmRequest,
    db: DbSession = ...,
    ctx: CurrentUser = ...,
) -> MappingConfirmResponse:
    session = db.get(DocumentImportSession, session_id)
    if not session or session.tenant_id != ctx.organization.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import session not found.")
    if session.status == "expired" or (session.expires_at and session.expires_at < datetime.now(UTC)):
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Import session has expired. Please upload again.")

    raw = _load_file(session.raw_file_storage_key)
    if session.file_type == "xlsx":
        _, rows, _ = parse_xlsx(raw, body.sheet_name or session.sheet_name)
    else:
        _, rows = parse_csv(raw)

    items = parse_rows(rows, body.mapping)
    missing = detect_missing_fields(items)

    warnings: list[dict[str, str]] = []
    if missing:
        warnings.append({"code": "MISSING_FIELDS", "message": f"Fields still missing after mapping: {', '.join(missing)}", "severity": "warning"})

    session.suggested_mapping_json = body.mapping
    session.parsed_preview_json = items[:10]
    session.status = "mapped"
    session.warnings_json = warnings
    db.commit()

    return MappingConfirmResponse(
        session_id=session_id,
        status="mapped",
        parsed_items=items,
        missing_fields=missing,
        warnings=warnings,
    )


# ── 3. Validate shipment data ────────────────────────────────────────────────

@router.post("/validate", response_model=ValidateResponse)
def validate_data(
    body: ValidateRequest,
    ctx: CurrentUser = ...,
) -> ValidateResponse:
    raw_issues = validate_shipment_data(body.data.model_dump())
    errors = [ValidationIssue(**i) for i in raw_issues if i["severity"] == "error"]
    warnings = [ValidationIssue(**i) for i in raw_issues if i["severity"] != "error"]
    return ValidateResponse(valid=not errors, errors=errors, warnings=warnings)


# ── 4. Generate documents ────────────────────────────────────────────────────

@router.post("/generate")
def generate_documents(
    body: GenerateRequest,
    db: DbSession = ...,
    ctx: CurrentUser = ...,
) -> StreamingResponse:
    # Validate first
    raw_issues = validate_shipment_data(body.data.model_dump())
    errors = [i for i in raw_issues if i["severity"] == "error"]
    if errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Validation errors prevent document generation.", "errors": errors},
        )

    doc_types = [t for t in body.document_types if t in SUPPORTED_DOC_TYPES]
    if not doc_types:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No valid document_types requested.")

    # Generate all PDFs
    generated: list[tuple[str, bytes]] = []
    metas: list[GeneratedDocumentMeta] = []
    data_dict = body.data.model_dump()
    for doc_type in doc_types:
        pdf_bytes, file_name = generate_document(doc_type, data_dict)
        generated.append((file_name, pdf_bytes))
        metas.append(GeneratedDocumentMeta(
            document_type=doc_type,
            file_name=file_name,
            file_size=len(pdf_bytes),
            checksum=checksum(pdf_bytes),
        ))

    zip_bytes = generate_zip(generated)

    # Optionally persist the pack + document records
    pack_id: UUID | None = None
    if body.save_pack:
        shipment = body.data.shipment
        buyer = body.data.buyer
        inv_num = shipment.invoice_number or ""
        pack_num = f"EPK-{inv_num or uuid.uuid4().hex[:8].upper()}"
        pack = ExportDocumentPack(
            id=uuid.uuid4(),
            tenant_id=ctx.organization.id,
            user_id=ctx.user.id,
            pack_number=pack_num,
            shipment_reference=shipment.shipment_reference,
            invoice_number=inv_num or None,
            buyer_name=buyer.buyer_name,
            consignee_name=buyer.consignee_name,
            destination_country=buyer.buyer_country,
            incoterm=shipment.incoterm,
            currency=shipment.currency,
            total_invoice_value=sum(
                (i.total_value or 0) for i in body.data.items
            ) or None,
            status="generated",
            shipment_data_json=data_dict,
            validation_warnings_json=[i for i in raw_issues if i["severity"] != "error"],
        )
        db.add(pack)
        db.flush()  # get pack.id before doc records
        pack_id = pack.id

        # Save ZIP to storage
        zip_key = _storage_key(ctx.organization.id, f"packs/{pack_id}/documents.zip")
        _save_file(zip_key, zip_bytes)

        for fname, pdf_bytes in generated:
            doc_type_key = next(m.document_type for m in metas if m.file_name == fname)
            pdf_key = _storage_key(ctx.organization.id, f"packs/{pack_id}/{fname}")
            _save_file(pdf_key, pdf_bytes)
            gd = GeneratedExportDocument(
                id=uuid.uuid4(),
                tenant_id=ctx.organization.id,
                user_id=ctx.user.id,
                pack_id=pack_id,
                document_type=doc_type_key,
                file_name=fname,
                file_format="pdf",
                storage_key=pdf_key,
                file_size=len(pdf_bytes),
                checksum=checksum(pdf_bytes),
                version_number=1,
            )
            db.add(gd)

        pack.generated_documents_json = [m.model_dump() for m in metas]
        db.commit()

    inv_label = (body.data.shipment.invoice_number or "documents").replace("/", "-")
    zip_filename = f"ExportDocs_{inv_label}.zip"

    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{zip_filename}"',
            "X-Pack-Id": str(pack_id) if pack_id else "",
        },
    )


# ── 5. List packs ────────────────────────────────────────────────────────────

@router.get("/packs", response_model=list[PackSummary])
def list_packs(
    db: DbSession = ...,
    ctx: CurrentUser = ...,
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[PackSummary]:
    rows = db.scalars(
        select(ExportDocumentPack)
        .where(
            ExportDocumentPack.tenant_id == ctx.organization.id,
            ExportDocumentPack.status != "archived",
        )
        .order_by(ExportDocumentPack.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return [PackSummary.model_validate(r) for r in rows]


# ── 6. Pack detail ───────────────────────────────────────────────────────────

@router.get("/packs/{pack_id}", response_model=PackDetail)
def get_pack(
    pack_id: UUID,
    db: DbSession = ...,
    ctx: CurrentUser = ...,
) -> PackDetail:
    pack = db.get(ExportDocumentPack, pack_id)
    if not pack:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pack not found.")
    _assert_pack_owner(pack, ctx)
    return PackDetail(
        id=pack.id,
        pack_number=pack.pack_number,
        invoice_number=pack.invoice_number,
        buyer_name=pack.buyer_name,
        destination_country=pack.destination_country,
        incoterm=pack.incoterm,
        currency=pack.currency,
        total_invoice_value=float(pack.total_invoice_value) if pack.total_invoice_value else None,
        status=pack.status,
        created_at=pack.created_at,
        updated_at=pack.updated_at,
        shipment_data=pack.shipment_data_json,
        validation_warnings=pack.validation_warnings_json,
        generated_documents=pack.generated_documents_json,
    )


# ── 7. Download pack ZIP ─────────────────────────────────────────────────────

@router.get("/packs/{pack_id}/download")
def download_pack(
    pack_id: UUID,
    db: DbSession = ...,
    ctx: CurrentUser = ...,
) -> StreamingResponse:
    pack = db.get(ExportDocumentPack, pack_id)
    if not pack:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pack not found.")
    _assert_pack_owner(pack, ctx)

    # Attempt to load stored ZIP first
    zip_key = _storage_key(ctx.organization.id, f"packs/{pack_id}/documents.zip")
    try:
        zip_bytes = _load_file(zip_key)
    except FileNotFoundError:
        # Re-generate on the fly from stored PDFs
        docs = db.scalars(
            select(GeneratedExportDocument).where(GeneratedExportDocument.pack_id == pack_id)
        ).all()
        if not docs:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No generated documents found for this pack.")
        pairs: list[tuple[str, bytes]] = []
        for d in docs:
            try:
                pairs.append((d.file_name, _load_file(d.storage_key)))
            except FileNotFoundError:
                pass
        if not pairs:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document files are no longer available. Please regenerate.")
        zip_bytes = generate_zip(pairs)

    inv_label = (pack.invoice_number or str(pack_id)[:8]).replace("/", "-")
    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="ExportDocs_{inv_label}.zip"'},
    )


# ── 8. Archive pack ──────────────────────────────────────────────────────────

@router.delete("/packs/{pack_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def archive_pack(
    pack_id: UUID,
    db: DbSession = ...,
    ctx: CurrentUser = ...,
) -> None:
    pack = db.get(ExportDocumentPack, pack_id)
    if not pack:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pack not found.")
    _assert_pack_owner(pack, ctx)
    pack.status = "archived"
    db.commit()
