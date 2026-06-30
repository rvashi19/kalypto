# ruff: noqa: E501
"""Incentive Finder API (/api/v1/incentives) — rates for an already-selected HSN.

Classification lives in the HSN Finder (/api/v1/hsn). This module never guesses a
product's HSN; it only looks up incentive records for a given code and never says
"HSN not found" merely because no rate row exists.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models import IncentiveImportJob, IncentiveRate, IncentiveSourceEvidence, MembershipRole
from app.schemas.incentive import (
    IncentiveDetailResponse,
    IncentiveEvidenceItem,
    IncentiveImportError,
    IncentiveImportJobResponse,
    IncentiveImportResponse,
    IncentiveRateItem,
    IncentiveSearchResponse,
)
from app.services.hsn_normalization import InvalidHsnCodeError, normalize_code
from app.services.incentive_import import import_incentive_snapshot
from app.services.incentive_search import (
    IncentiveMatch,
    hsn_exists_in_master,
    search_incentives,
)
from app.services.rate_limit import rate_limit_upload_requests

router = APIRouter(prefix="/incentives", tags=["incentives"])

_ALLOWED_IMPORT_TYPES = {"csv", "json", "xlsx"}
_LEVELS = {2: 2, 4: 4, 6: 6, 8: 8}


def _parse_export_date(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def _require_admin(current_user: CurrentUser) -> None:
    if current_user.membership.role != MembershipRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only organisation admins (owner role) can import or verify incentive rates.",
        )


def _row_item(match: IncentiveMatch) -> IncentiveRateItem:
    row = match.row
    return IncentiveRateItem(
        id=str(row.id),
        scheme=row.scheme,
        hsn_code=row.hsn_code,
        normalized_hsn_code=row.normalized_hsn_code,
        digit_level=row.digit_level,
        product_description=row.product_description,
        rate_type=row.rate_type,
        rate_value=float(row.rate_value),
        cap_value=float(row.cap_value) if row.cap_value is not None else None,
        cap_unit=row.cap_unit,
        unit_of_quantity=row.unit_of_quantity,
        condition_text=row.condition_text,
        effective_from=row.effective_from,
        effective_to=row.effective_to,
        source_name=row.source_name,
        source_url=row.source_url,
        source_document_title=row.source_document_title,
        source_document_date=row.source_document_date,
        source_version=row.source_version,
        approval_status=row.approval_status,
        verified_by=row.verified_by,
        verified_at=row.verified_at,
        is_active=row.is_active,
        match_level=match.match_level,
        source_evidence_count=match.evidence_count,
    )


@router.get("/search", response_model=IncentiveSearchResponse)
def search(
    session: DbSession,
    current_user: CurrentUser,
    hsn_code: str = Query(min_length=1),
    scheme: str | None = Query(default=None),
    export_date: str | None = Query(default=None),
    country: str | None = Query(default=None),
    include_unapproved: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
) -> IncentiveSearchResponse:
    _ = country  # reserved for future country-specific incentive filtering
    is_admin = current_user.membership.role == MembershipRole.OWNER
    show_unapproved = include_unapproved and is_admin
    asof = _parse_export_date(export_date)
    try:
        matches = search_incentives(
            session=session,
            tenant_id=current_user.organization.id,
            hsn_code=hsn_code,
            scheme=scheme,
            export_date=asof,
            include_unapproved=show_unapproved,
            limit=limit,
        )
    except InvalidHsnCodeError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        ) from error

    normalized = normalize_code(hsn_code)
    hsn_exists = hsn_exists_in_master(session, normalized)
    items = [_row_item(match) for match in matches]
    schemes = sorted({item.scheme for item in items})

    message: str | None = None
    if not items:
        if hsn_exists:
            message = "HSN exists, but no approved incentive/rate data is available for this code."
        else:
            message = (
                "No incentive/rate records found for this HSN. Classify or verify the HSN in "
                "HSN Finder before relying on incentive rates."
            )

    return IncentiveSearchResponse(
        hsn_code=hsn_code,
        normalized_hsn_code=normalized,
        digit_level=_LEVELS.get(len(normalized)),
        hsn_exists=hsn_exists,
        count=len(items),
        schemes_present=schemes,
        results=items,
        message=message,
    )


@router.get("/import-jobs", response_model=list[IncentiveImportJobResponse])
def import_jobs(session: DbSession, current_user: CurrentUser) -> list[IncentiveImportJobResponse]:
    _require_admin(current_user)
    rows = session.scalars(
        select(IncentiveImportJob).order_by(IncentiveImportJob.created_at.desc()).limit(100)
    ).all()
    return [
        IncentiveImportJobResponse(
            id=str(row.id),
            scheme=row.scheme,
            source_name=row.source_name,
            source_url=row.source_url,
            import_type=row.import_type,
            status=row.status,
            records_seen=row.records_seen,
            records_created=row.records_created,
            records_updated=row.records_updated,
            records_deactivated=row.records_deactivated,
            error_message=row.error_message,
            checksum=row.checksum,
            started_at=row.started_at,
            completed_at=row.completed_at,
            created_by=row.created_by,
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.post(
    "/import",
    response_model=IncentiveImportResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit_upload_requests)],
)
async def import_snapshot(
    session: DbSession,
    current_user: CurrentUser,
    file: UploadFile,
    source_name: str = Form(...),
    scheme: str | None = Form(default=None),
    source_url: str | None = Form(default=None),
    source_document_title: str | None = Form(default=None),
    source_document_date: str | None = Form(default=None),
    source_version: str | None = Form(default=None),
    import_type: str | None = Form(default=None),
) -> IncentiveImportResponse:
    _require_admin(current_user)
    filename = (file.filename or "").lower()
    resolved_type = (import_type or filename.rsplit(".", 1)[-1] if "." in filename else import_type or "").lower()
    if resolved_type not in _ALLOWED_IMPORT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported import type '{resolved_type}'. Use one of: {', '.join(sorted(_ALLOWED_IMPORT_TYPES))}.",
        )

    raw_bytes = await file.read()
    result = import_incentive_snapshot(
        session=session,
        tenant_id=current_user.organization.id,
        raw_bytes=raw_bytes,
        import_type=resolved_type,
        source_name=source_name,
        scheme=scheme,
        source_url=source_url,
        source_document_title=source_document_title,
        source_document_date=source_document_date,
        source_version=source_version,
        created_by=current_user.user.email,
    )
    job = result.job
    return IncentiveImportResponse(
        job_id=str(job.id),
        status=job.status,
        scheme=job.scheme,
        source_name=job.source_name,
        import_type=job.import_type,
        checksum=job.checksum,
        records_seen=job.records_seen,
        records_created=job.records_created,
        records_updated=job.records_updated,
        records_deactivated=job.records_deactivated,
        error_message=job.error_message,
        errors=[IncentiveImportError(row=e["row"], message=e["message"]) for e in result.errors],
    )


@router.post("/{rate_id}/approve", response_model=IncentiveDetailResponse)
def approve(rate_id: UUID, session: DbSession, current_user: CurrentUser) -> IncentiveDetailResponse:
    _require_admin(current_user)
    row = session.get(IncentiveRate, rate_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incentive rate not found.")
    row.approval_status = "approved"
    row.is_active = True
    row.verified_by = current_user.user.email
    row.verified_at = datetime.now(UTC)
    session.commit()
    session.refresh(row)
    return _detail_response(session, row)


@router.get("/{rate_id}", response_model=IncentiveDetailResponse)
def get_detail(rate_id: UUID, session: DbSession, current_user: CurrentUser) -> IncentiveDetailResponse:
    row = session.get(IncentiveRate, rate_id)
    is_admin = current_user.membership.role == MembershipRole.OWNER
    tenant_ok = row is not None and row.tenant_id in (None, current_user.organization.id)
    if row is None or not tenant_ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incentive rate not found.")
    if not is_admin and row.approval_status != "approved":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incentive rate not found.")
    return _detail_response(session, row)


def _detail_response(session: DbSession, row: IncentiveRate) -> IncentiveDetailResponse:
    evidence_rows = session.scalars(
        select(IncentiveSourceEvidence)
        .where(IncentiveSourceEvidence.incentive_rate_id == row.id)
        .order_by(IncentiveSourceEvidence.retrieved_at.desc())
    ).all()
    item = _row_item(IncentiveMatch(row=row, match_level="exact", evidence_count=len(evidence_rows)))
    return IncentiveDetailResponse(
        **item.model_dump(),
        source_evidence=[
            IncentiveEvidenceItem(
                source_name=e.source_name,
                source_url=e.source_url,
                document_title=e.document_title,
                document_date=e.document_date,
                raw_text_excerpt=e.raw_text_excerpt,
                retrieved_at=e.retrieved_at,
                evidence_type=e.evidence_type,
                confidence_weight=float(e.confidence_weight) if e.confidence_weight is not None else None,
            )
            for e in evidence_rows
        ],
    )
