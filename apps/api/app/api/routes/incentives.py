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
from sqlalchemy import or_, select

from app.api.deps import CurrentUser, DbSession
from app.models import (
    IncentiveImportJob,
    IncentiveRate,
    IncentiveSource,
    IncentiveSourceEvidence,
    MembershipRole,
)
from app.schemas.incentive import (
    IncentiveAnomalyResponse,
    IncentiveDetailResponse,
    IncentiveEvidenceItem,
    IncentiveImportError,
    IncentiveImportJobResponse,
    IncentiveImportResponse,
    IncentiveRateItem,
    IncentiveRefreshResponse,
    IncentiveSearchResponse,
    IncentiveSourceCreate,
    IncentiveSourceResponse,
)
from app.services.hsn_llm_verify import HsnLlmError, HsnLlmNotConfiguredError
from app.services.hsn_normalization import InvalidHsnCodeError, normalize_code
from app.services.incentive_import import import_incentive_snapshot
from app.services.incentive_llm import anomaly_check
from app.services.incentive_search import (
    IncentiveMatch,
    hsn_exists_in_master,
    search_incentives,
)
from app.services.incentive_sources import (
    IncentiveSourceError,
    is_due,
    list_sources,
    refresh_source,
)
from app.services.rate_limit import rate_limit_upload_requests

router = APIRouter(prefix="/incentives", tags=["incentives"])

_ALLOWED_IMPORT_TYPES = {"csv", "json", "xlsx", "pdf"}
_PENDING_STATUSES = ("pending", "needs_review")
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
        review_note=row.review_note,
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


def _source_response(source: IncentiveSource) -> IncentiveSourceResponse:
    return IncentiveSourceResponse(
        id=str(source.id),
        scheme=source.scheme,
        source_name=source.source_name,
        source_url=source.source_url,
        source_document_title=source.source_document_title,
        source_type=source.source_type,
        refresh_interval_days=source.refresh_interval_days,
        last_fetched_at=source.last_fetched_at,
        last_source_version=source.last_source_version,
        last_status=source.last_status,
        last_records=source.last_records,
        is_active=source.is_active,
        due_for_refresh=is_due(source),
        created_at=source.created_at,
    )


@router.post("/sources", response_model=IncentiveSourceResponse, status_code=status.HTTP_201_CREATED)
def register_official_source(
    payload: IncentiveSourceCreate, session: DbSession, current_user: CurrentUser
) -> IncentiveSourceResponse:
    _require_admin(current_user)
    from app.services.incentive_sources import register_source

    source = register_source(
        session=session,
        tenant_id=current_user.organization.id,
        scheme=payload.scheme,
        source_name=payload.source_name,
        source_type=payload.source_type,
        source_url=payload.source_url,
        source_document_title=payload.source_document_title,
        refresh_interval_days=payload.refresh_interval_days,
        created_by=current_user.user.email,
    )
    return _source_response(source)


@router.get("/sources", response_model=list[IncentiveSourceResponse])
def list_official_sources(session: DbSession, current_user: CurrentUser) -> list[IncentiveSourceResponse]:
    _require_admin(current_user)
    return [_source_response(s) for s in list_sources(session=session, tenant_id=current_user.organization.id)]


@router.post(
    "/sources/{source_id}/refresh",
    response_model=IncentiveRefreshResponse,
    dependencies=[Depends(rate_limit_upload_requests)],
)
def refresh_official_source(
    source_id: UUID, session: DbSession, current_user: CurrentUser
) -> IncentiveRefreshResponse:
    _require_admin(current_user)
    source = session.get(IncentiveSource, source_id)
    if source is None or source.tenant_id not in (None, current_user.organization.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found.")
    try:
        outcome = refresh_source(session=session, source=source, created_by=current_user.user.email)
    except IncentiveSourceError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)) from error
    job = outcome.result.job if outcome.result else None
    return IncentiveRefreshResponse(
        source_id=str(source.id),
        status=source.last_status,
        message=outcome.message,
        records_seen=job.records_seen if job else 0,
        records_created=job.records_created if job else 0,
        records_updated=job.records_updated if job else 0,
    )


@router.get("/pending", response_model=list[IncentiveRateItem])
def pending_queue(session: DbSession, current_user: CurrentUser) -> list[IncentiveRateItem]:
    _require_admin(current_user)
    rows = session.scalars(
        select(IncentiveRate)
        .where(
            IncentiveRate.approval_status.in_(_PENDING_STATUSES),
            or_(
                IncentiveRate.tenant_id == current_user.organization.id,
                IncentiveRate.tenant_id.is_(None),
            ),
        )
        .order_by(IncentiveRate.created_at.desc())
        .limit(200)
    ).all()
    return [_row_item(IncentiveMatch(row=row, match_level="exact", evidence_count=0)) for row in rows]


@router.post("/anomaly-check", response_model=IncentiveAnomalyResponse)
def run_anomaly_check(session: DbSession, current_user: CurrentUser) -> IncentiveAnomalyResponse:
    _require_admin(current_user)
    rows = session.scalars(
        select(IncentiveRate).where(
            IncentiveRate.approval_status.in_(_PENDING_STATUSES),
            or_(
                IncentiveRate.tenant_id == current_user.organization.id,
                IncentiveRate.tenant_id.is_(None),
            ),
        )
    ).all()
    try:
        result = anomaly_check(session=session, rates=list(rows))
    except HsnLlmNotConfiguredError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
    except HsnLlmError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)) from error
    return IncentiveAnomalyResponse(**result)


@router.post("/{rate_id}/reject", response_model=IncentiveDetailResponse)
def reject(rate_id: UUID, session: DbSession, current_user: CurrentUser) -> IncentiveDetailResponse:
    _require_admin(current_user)
    row = session.get(IncentiveRate, rate_id)
    if row is None or row.tenant_id not in (None, current_user.organization.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incentive rate not found.")
    row.approval_status = "rejected"
    row.is_active = False
    row.verified_by = current_user.user.email
    row.verified_at = datetime.now(UTC)
    session.commit()
    session.refresh(row)
    return _detail_response(session, row)


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
