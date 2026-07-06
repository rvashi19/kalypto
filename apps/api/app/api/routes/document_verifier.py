# ruff: noqa: B008, E501
"""AI Document Verifier API."""

from __future__ import annotations

import io
import uuid
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models.document_verifier import (
    DocumentExtractedField,
    DocumentVerificationIssue,
    DocumentVerificationReport,
    DocumentVerificationRun,
    VerificationDocument,
)
from app.schemas.document_verifier import (
    DocumentExtractedFieldResponse,
    DocumentUploadResponse,
    DocumentVerificationIssueResponse,
    DocumentVerificationReportResponse,
    DocumentVerificationRunCreate,
    DocumentVerificationRunResponse,
    ExtractionRunResponse,
    VerificationDocumentResponse,
    VerificationRunResponse,
)
from app.services.document_verifier import (
    DocumentVerifierError,
    allowed_file,
    extract_document,
    generate_report_pdf,
    max_file_bytes,
    storage_key,
    verify_run,
)
from app.services.storage import storage

router = APIRouter(prefix="/document-verifier", tags=["document-verifier"])


def _get_run(db: DbSession, ctx: CurrentUser, run_id: UUID) -> DocumentVerificationRun:
    run = db.get(DocumentVerificationRun, run_id)
    if run is None or run.tenant_id != ctx.organization.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Verification run not found.")
    return run


def _get_issue(db: DbSession, ctx: CurrentUser, issue_id: UUID) -> DocumentVerificationIssue:
    issue = db.get(DocumentVerificationIssue, issue_id)
    if issue is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found.")
    run = _get_run(db, ctx, issue.verification_run_id)
    if run.tenant_id != ctx.organization.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found.")
    return issue


def _run_response(db: DbSession, run: DocumentVerificationRun) -> DocumentVerificationRunResponse:
    documents = db.scalars(
        select(VerificationDocument)
        .where(VerificationDocument.verification_run_id == run.id)
        .order_by(VerificationDocument.created_at.asc())
    ).all()
    fields = db.scalars(
        select(DocumentExtractedField)
        .where(DocumentExtractedField.verification_run_id == run.id)
        .order_by(DocumentExtractedField.created_at.asc())
    ).all()
    issues = db.scalars(
        select(DocumentVerificationIssue)
        .where(DocumentVerificationIssue.verification_run_id == run.id)
        .order_by(DocumentVerificationIssue.severity.asc(), DocumentVerificationIssue.created_at.asc())
    ).all()
    report = db.scalars(
        select(DocumentVerificationReport)
        .where(DocumentVerificationReport.verification_run_id == run.id)
        .order_by(DocumentVerificationReport.created_at.desc())
    ).first()
    return DocumentVerificationRunResponse(
        **DocumentVerificationRunResponse.model_validate(run).model_dump(exclude={"documents", "fields", "issues", "report"}),
        documents=[VerificationDocumentResponse.model_validate(doc) for doc in documents],
        fields=[DocumentExtractedFieldResponse.model_validate(field) for field in fields],
        issues=[DocumentVerificationIssueResponse.model_validate(issue) for issue in issues],
        report=DocumentVerificationReportResponse.model_validate(report) if report else None,
    )


@router.post("/runs", response_model=DocumentVerificationRunResponse, status_code=status.HTTP_201_CREATED)
def create_run(
    body: DocumentVerificationRunCreate,
    db: DbSession,
    ctx: CurrentUser,
) -> DocumentVerificationRunResponse:
    run = DocumentVerificationRun(
        tenant_id=ctx.organization.id,
        user_id=ctx.user.id,
        shipment_id=body.shipment_id,
        quote_id=body.quote_id,
        status="uploaded",
        title=body.title,
        reference_number=body.reference_number,
        origin_country=body.origin_country,
        destination_country=body.destination_country,
        hsn_code=body.hsn_code,
        product_description=body.product_description,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return _run_response(db, run)


@router.get("/runs", response_model=list[DocumentVerificationRunResponse])
def list_runs(db: DbSession, ctx: CurrentUser) -> list[DocumentVerificationRunResponse]:
    runs = db.scalars(
        select(DocumentVerificationRun)
        .where(DocumentVerificationRun.tenant_id == ctx.organization.id)
        .order_by(DocumentVerificationRun.created_at.desc())
    ).all()
    return [_run_response(db, run) for run in runs]


@router.get("/runs/{run_id}", response_model=DocumentVerificationRunResponse)
def get_run(run_id: UUID, db: DbSession, ctx: CurrentUser) -> DocumentVerificationRunResponse:
    return _run_response(db, _get_run(db, ctx, run_id))


@router.post("/runs/{run_id}/documents", response_model=DocumentUploadResponse)
async def upload_documents(
    run_id: UUID,
    files: Annotated[list[UploadFile], File(...)],
    db: DbSession,
    ctx: CurrentUser,
) -> DocumentUploadResponse:
    run = _get_run(db, ctx, run_id)
    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Upload at least one document.")

    saved: list[VerificationDocument] = []
    for file in files:
        filename = file.filename or "upload"
        valid, ext = allowed_file(filename, file.content_type)
        if not valid:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Accepted formats: PDF, XLSX, CSV, JPG, JPEG, PNG.",
            )
        raw = await file.read()
        if len(raw) > max_file_bytes():
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds {max_file_bytes() // (1024 * 1024)} MB limit.",
            )
        document = VerificationDocument(
            id=uuid.uuid4(),
            verification_run_id=run.id,
            file_name=filename,
            file_type=ext,
            mime_type=file.content_type,
            storage_key="pending",
            document_type=None,
            parser_used="pending",
            extraction_status="pending",
            uploaded_at=datetime.now(UTC),
        )
        document.storage_key = storage_key(ctx.organization.id, run.id, document.id, filename)
        storage.put(document.storage_key, raw, file.content_type or "application/octet-stream")
        db.add(document)
        saved.append(document)
    run.status = "uploaded"
    db.commit()
    for document in saved:
        db.refresh(document)
    return DocumentUploadResponse(documents=[VerificationDocumentResponse.model_validate(doc) for doc in saved])


@router.post("/runs/{run_id}/extract", response_model=ExtractionRunResponse)
def extract_run(run_id: UUID, db: DbSession, ctx: CurrentUser) -> ExtractionRunResponse:
    run = _get_run(db, ctx, run_id)
    documents = db.scalars(
        select(VerificationDocument).where(VerificationDocument.verification_run_id == run.id)
    ).all()
    if not documents:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Upload documents before extraction.")
    run.status = "extracting"
    db.commit()

    failures = 0
    fields_extracted = 0
    for document in documents:
        try:
            fields_extracted += extract_document(db, document)
        except Exception as error:  # noqa: BLE001
            document.extraction_status = "failed"
            document.extraction_error = str(error)
            document.parser_used = document.parser_used or "failed"
            failures += 1
    run.status = "failed" if failures == len(documents) else "extracted"
    db.commit()
    return ExtractionRunResponse(
        run_id=run.id,
        status=run.status,
        documents_extracted=len(documents) - failures,
        fields_extracted=fields_extracted,
        failures=failures,
        message="Extraction completed." if failures == 0 else "Extraction completed with failures.",
    )


@router.post("/runs/{run_id}/verify", response_model=VerificationRunResponse)
def verify_documents(run_id: UUID, db: DbSession, ctx: CurrentUser) -> VerificationRunResponse:
    run = _get_run(db, ctx, run_id)
    try:
        report = verify_run(db, run)
    except DocumentVerifierError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    db.commit()
    db.refresh(report)
    return VerificationRunResponse(
        run_id=run.id,
        status=run.status,
        issues_count=report.issues_count,
        critical_count=report.critical_count,
        high_count=report.high_count,
        medium_count=report.medium_count,
        low_count=report.low_count,
        message=(
            "No major mismatches found. Manual review is still recommended before filing."
            if report.issues_count == 0
            else "Review required. Verification issues were found."
        ),
    )


@router.get("/runs/{run_id}/issues", response_model=list[DocumentVerificationIssueResponse])
def list_issues(run_id: UUID, db: DbSession, ctx: CurrentUser) -> list[DocumentVerificationIssueResponse]:
    run = _get_run(db, ctx, run_id)
    issues = db.scalars(
        select(DocumentVerificationIssue)
        .where(DocumentVerificationIssue.verification_run_id == run.id)
        .order_by(DocumentVerificationIssue.created_at.desc())
    ).all()
    return [DocumentVerificationIssueResponse.model_validate(issue) for issue in issues]


@router.post("/issues/{issue_id}/resolve", response_model=DocumentVerificationIssueResponse)
def resolve_issue(issue_id: UUID, db: DbSession, ctx: CurrentUser) -> DocumentVerificationIssueResponse:
    issue = _get_issue(db, ctx, issue_id)
    issue.status = "resolved"
    db.commit()
    db.refresh(issue)
    return DocumentVerificationIssueResponse.model_validate(issue)


@router.post("/issues/{issue_id}/ignore", response_model=DocumentVerificationIssueResponse)
def ignore_issue(issue_id: UUID, db: DbSession, ctx: CurrentUser) -> DocumentVerificationIssueResponse:
    issue = _get_issue(db, ctx, issue_id)
    issue.status = "ignored"
    db.commit()
    db.refresh(issue)
    return DocumentVerificationIssueResponse.model_validate(issue)


@router.get("/runs/{run_id}/report", response_model=DocumentVerificationReportResponse)
def get_report(run_id: UUID, db: DbSession, ctx: CurrentUser) -> DocumentVerificationReportResponse:
    run = _get_run(db, ctx, run_id)
    report = db.scalars(
        select(DocumentVerificationReport)
        .where(DocumentVerificationReport.verification_run_id == run.id)
        .order_by(DocumentVerificationReport.created_at.desc())
    ).first()
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report has not been generated yet.")
    return DocumentVerificationReportResponse.model_validate(report)


@router.post("/runs/{run_id}/report/pdf")
def download_report_pdf(run_id: UUID, db: DbSession, ctx: CurrentUser) -> StreamingResponse:
    run = _get_run(db, ctx, run_id)
    report = db.scalars(
        select(DocumentVerificationReport)
        .where(DocumentVerificationReport.verification_run_id == run.id)
        .order_by(DocumentVerificationReport.created_at.desc())
    ).first()
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report has not been generated yet.")
    documents = db.scalars(
        select(VerificationDocument).where(VerificationDocument.verification_run_id == run.id)
    ).all()
    issues = db.scalars(
        select(DocumentVerificationIssue).where(DocumentVerificationIssue.verification_run_id == run.id)
    ).all()
    pdf = generate_report_pdf(run=run, documents=list(documents), issues=list(issues), report=report)
    key = f"document-verifier/{ctx.organization.id}/{run.id}/report.pdf"
    storage.put(key, pdf, "application/pdf")
    report.report_storage_key = key
    db.commit()
    return StreamingResponse(
        io.BytesIO(pdf),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="document-verifier-{run.id}.pdf"'},
    )
