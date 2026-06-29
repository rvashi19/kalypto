# ruff: noqa: E501
"""Standalone HSN Finder API (/api/v1/hsn).

Classification only. Incentive/rate lookup lives under /api/v1/incentives and
/shipments/hsn-rates and is intentionally decoupled from this module.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession
from app.models import (
    HsnCode,
    HsnImportJob,
    HsnProductAlias,
    HsnSourceEvidence,
    HsnVerificationRequest,
    MembershipRole,
    RateTable,
)
from app.schemas.hsn import (
    HsnAiClassifyRequest,
    HsnAiClassifyResponse,
    HsnCodeAnnotateRequest,
    HsnCrossCheckSource,
    HsnDetailResponse,
    HsnEvidenceItem,
    HsnHierarchy,
    HsnImportError,
    HsnImportJobResponse,
    HsnImportResponse,
    HsnScrapeRequest,
    HsnSearchItem,
    HsnSearchResponse,
    HsnStatsResponse,
    HsnVerificationCreate,
    HsnVerificationResponse,
)
from app.services.hsn_cross_verify import cross_verify_code
from app.services.hsn_import import import_hsn_snapshot
from app.services.hsn_llm_verify import (
    HsnLlmError,
    HsnLlmNotConfiguredError,
    is_llm_configured,
    llm_classify,
)
from app.services.hsn_normalization import InvalidHsnCodeError, normalize_code, normalize_strict
from app.services.hsn_scraper import (
    HsnScrapeError,
    ScrapeOutcome,
    fetch_eximguru,
    fetch_official_file,
    fetch_ogd_records,
)
from app.services.hsn_search import HsnMatch, record_query, search_hsn
from app.services.hsn_verified import load_verified_aliases
from app.services.rate_limit import rate_limit_upload_requests

router = APIRouter(prefix="/hsn", tags=["hsn"])

_ALLOWED_IMPORT_TYPES = {"csv", "json", "xlsx"}


def _require_admin(current_user: CurrentUser) -> None:
    if current_user.membership.role != MembershipRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only organisation admins (owner role) can import or modify the HSN master.",
        )


def _evidence_items(session: DbSession, code_id: UUID) -> list[HsnEvidenceItem]:
    rows = session.scalars(
        select(HsnSourceEvidence)
        .where(HsnSourceEvidence.hsn_code_id == code_id)
        .order_by(HsnSourceEvidence.retrieved_at.desc())
    ).all()
    return [
        HsnEvidenceItem(
            source_name=row.source_name,
            source_url=row.source_url,
            evidence_type=row.evidence_type,
            document_title=row.document_title,
            document_date=row.document_date,
            retrieved_at=row.retrieved_at,
            raw_text_excerpt=row.raw_text_excerpt,
            confidence_weight=float(row.confidence_weight) if row.confidence_weight is not None else None,
        )
        for row in rows
    ]


def _match_to_item(session: DbSession, match: HsnMatch) -> HsnSearchItem:
    code = match.code
    return HsnSearchItem(
        code=code.code,
        normalized_code=code.normalized_code,
        description=code.description,
        digit_level=code.digit_level,
        hierarchy=HsnHierarchy(
            chapter_code=code.chapter_code,
            heading_code=code.heading_code,
            subheading_code=code.subheading_code,
            parent_code=code.parent_code,
        ),
        confidence_score=match.score,
        confidence_label=match.confidence_label,
        match_reason=match.match_reason,
        source_evidence=_evidence_items(session, code.id) if match.evidence_count else [],
        warning_flags=match.warning_flags,
        verification_recommended=match.verification_recommended,
        verified=match.verified,
    )


@router.get("/search", response_model=HsnSearchResponse)
def search(
    session: DbSession,
    current_user: CurrentUser,
    q: str = Query(min_length=1),
    limit: int = Query(default=20, ge=1, le=100),
    digit_level: int | None = Query(default=None),
    include_inactive: bool = Query(default=False),
) -> HsnSearchResponse:
    if digit_level is not None and digit_level not in (2, 4, 6, 8):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="digit_level must be one of 2, 4, 6, 8.",
        )
    if include_inactive and current_user.membership.role != MembershipRole.OWNER:
        include_inactive = False  # silently ignore for non-admins

    matches = search_hsn(
        session=session,
        query=q,
        limit=limit,
        digit_level_filter=digit_level,
        include_inactive=include_inactive,
    )
    items = [_match_to_item(session, match) for match in matches]
    record_query(
        session=session,
        query=q,
        tenant_id=current_user.organization.id,
        user_id=current_user.user.id,
        top=matches[0] if matches else None,
    )
    session.commit()
    return HsnSearchResponse(query=q, count=len(items), results=items)


@router.get("/stats", response_model=HsnStatsResponse)
def stats(session: DbSession, current_user: CurrentUser) -> HsnStatsResponse:
    def _count(level: int | None = None) -> int:
        query = select(func.count()).select_from(HsnCode).where(HsnCode.is_active.is_(True))
        if level is not None:
            query = query.where(HsnCode.digit_level == level)
        return int(session.scalar(query) or 0)

    return HsnStatsResponse(
        total_codes=_count(),
        chapters=_count(2),
        headings=_count(4),
        subheadings=_count(6),
        tariff_items=_count(8),
        verified_mappings=int(
            session.scalar(select(func.count()).select_from(HsnProductAlias)) or 0
        ),
    )


@router.get("/import/jobs", response_model=list[HsnImportJobResponse])
def list_import_jobs(session: DbSession, current_user: CurrentUser) -> list[HsnImportJobResponse]:
    _require_admin(current_user)
    rows = session.scalars(
        select(HsnImportJob).order_by(HsnImportJob.created_at.desc()).limit(100)
    ).all()
    return [
        HsnImportJobResponse(
            id=str(row.id),
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


@router.post("/import", response_model=HsnImportResponse, status_code=status.HTTP_201_CREATED)
async def import_snapshot(
    session: DbSession,
    current_user: CurrentUser,
    file: UploadFile,
    source_name: str = Form(...),
    source_url: str | None = Form(default=None),
    source_document_title: str | None = Form(default=None),
    source_document_date: str | None = Form(default=None),
    source_version: str | None = Form(default=None),
    import_type: str | None = Form(default=None),
) -> HsnImportResponse:
    _require_admin(current_user)

    filename = (file.filename or "").lower()
    resolved_type = (import_type or filename.rsplit(".", 1)[-1] if "." in filename else import_type or "").lower()
    if resolved_type not in _ALLOWED_IMPORT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported import type '{resolved_type}'. Use one of: {', '.join(sorted(_ALLOWED_IMPORT_TYPES))}.",
        )

    raw_bytes = await file.read()
    result = import_hsn_snapshot(
        session=session,
        raw_bytes=raw_bytes,
        import_type=resolved_type,
        source_name=source_name,
        source_url=source_url,
        source_document_title=source_document_title,
        source_document_date=source_document_date,
        source_version=source_version,
        created_by=current_user.user.email,
    )
    job = result.job
    return HsnImportResponse(
        job_id=str(job.id),
        status=job.status,
        import_type=job.import_type,
        source_name=job.source_name,
        source_version=source_version,
        checksum=job.checksum,
        records_seen=job.records_seen,
        records_created=job.records_created,
        records_updated=job.records_updated,
        records_deactivated=job.records_deactivated,
        error_message=job.error_message,
        errors=[HsnImportError(row=e["row"], message=e["message"]) for e in result.errors],
    )


def _scrape_response(outcome: ScrapeOutcome, source_version: str | None) -> HsnImportResponse:
    job = outcome.result.job
    return HsnImportResponse(
        job_id=str(job.id),
        status=job.status,
        import_type=job.import_type,
        source_name=job.source_name,
        source_version=source_version,
        checksum=job.checksum,
        records_seen=job.records_seen,
        records_created=job.records_created,
        records_updated=job.records_updated,
        records_deactivated=job.records_deactivated,
        error_message=job.error_message,
        errors=[HsnImportError(row=e["row"], message=e["message"]) for e in outcome.result.errors],
    )


@router.post(
    "/scrape",
    response_model=HsnImportResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit_upload_requests)],
)
def scrape_official_source(
    payload: HsnScrapeRequest,
    session: DbSession,
    current_user: CurrentUser,
) -> HsnImportResponse:
    """Admin-triggered fetch of an official HSN source into the master (data.gov.in or a snapshot file URL)."""
    _require_admin(current_user)
    try:
        if payload.source == "ogd":
            if not payload.resource_id:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="resource_id is required for the data.gov.in (ogd) source.",
                )
            outcome = fetch_ogd_records(
                session=session,
                resource_id=payload.resource_id,
                source_version=payload.source_version,
                api_key=payload.api_key,
                max_records=payload.max_records,
                source_name=payload.source_name
                or "data.gov.in (Open Government Data Platform, India)",
                source_document_title=payload.source_document_title,
                source_document_date=payload.source_document_date,
                created_by=current_user.user.email,
            )
        elif payload.source == "eximguru":
            outcome = fetch_eximguru(
                session=session,
                chapters=payload.chapters,
                source_version=payload.source_version,
                max_records=payload.max_records,
                created_by=current_user.user.email,
            )
        else:
            if not payload.url:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="url is required for the official file source.",
                )
            outcome = fetch_official_file(
                session=session,
                url=payload.url,
                source_name=payload.source_name or "Official HSN snapshot",
                source_version=payload.source_version,
                source_document_title=payload.source_document_title,
                source_document_date=payload.source_document_date,
                import_type=payload.import_type,
                created_by=current_user.user.email,
            )
    except HsnScrapeError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)) from error

    return _scrape_response(outcome, payload.source_version)


@router.post(
    "/classify-ai",
    response_model=HsnAiClassifyResponse,
    dependencies=[Depends(rate_limit_upload_requests)],
)
def classify_ai(
    payload: HsnAiClassifyRequest,
    session: DbSession,
    current_user: CurrentUser,
) -> HsnAiClassifyResponse:
    """LLM-verify the best HSN for a product, grounded in deterministic candidates."""
    if not is_llm_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI verification is not configured. Set OPENAI_API_KEY (or XAI_API_KEY) on the API.",
        )
    candidates = [
        (m.code.normalized_code, m.code.description)
        for m in search_hsn(session=session, query=payload.product, limit=12)
    ]
    try:
        verdict = llm_classify(session=session, product=payload.product, candidates=candidates)
    except HsnLlmNotConfiguredError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
    except HsnLlmError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)) from error

    code = verdict.get("hsn_code")

    # Cross-verify the LLM's code against authentic ITC-HS website data so the
    # answer never depends on the LLM alone.
    cross = (
        cross_verify_code(
            session=session,
            code=code,
            product=payload.product,
            llm_description=verdict.get("description"),
        )
        if code
        else None
    )
    cross_sources = (
        [HsnCrossCheckSource(source=s.source, description=s.description[:200], match=s.match) for s in cross.sources]
        if cross
        else []
    )
    verification = cross.status if cross else "unverified"

    stored = False
    if payload.store and code and verification != "unverified":
        # Store only codes confirmed by an authentic source. Cross-verified answers
        # become High-confidence verified mappings; weak matches are stored lower.
        description = (verdict.get("description") or "").replace('"', "'")
        model = verdict.get("model") or "llm"
        cross_verified = verification == "cross_verified"
        csv = (
            'term,code,description\n'
            f'"{payload.product.strip().lower()}",{code},"{description}"\n'
        ).encode()
        load_verified_aliases(
            session=session,
            raw_bytes=csv,
            source="llm_cross_verified" if cross_verified else "llm_verified",
            code_source_name=f"LLM ({model}) + authentic source cross-check",
            overwrite_description=False,
            confidence=92 if cross_verified else 70,
        )
        stored = True

    return HsnAiClassifyResponse(
        stored=stored,
        verification=verification,
        authentic_sources=cross.authentic_count if cross else 0,
        cross_check=cross_sources,
        **verdict,
    )


@router.post("/verify", response_model=HsnVerificationResponse, status_code=status.HTTP_201_CREATED)
def create_verification(
    payload: HsnVerificationCreate,
    session: DbSession,
    current_user: CurrentUser,
) -> HsnVerificationResponse:
    request = HsnVerificationRequest(
        tenant_id=current_user.organization.id,
        user_id=current_user.user.id,
        product_description=payload.product_description,
        selected_hsn_code=normalize_code(payload.selected_hsn_code) if payload.selected_hsn_code else None,
        alternative_hsn_codes=[normalize_code(c) for c in payload.alternative_hsn_codes if c],
        user_notes=payload.user_notes,
        status="requested",
    )
    session.add(request)
    session.commit()
    session.refresh(request)
    return HsnVerificationResponse(
        id=str(request.id),
        product_description=request.product_description,
        selected_hsn_code=request.selected_hsn_code,
        alternative_hsn_codes=request.alternative_hsn_codes,
        user_notes=request.user_notes,
        status=request.status,
        reviewer_notes=request.reviewer_notes,
        created_at=request.created_at,
    )


@router.post("/codes/{code_id}/annotate", response_model=HsnDetailResponse)
def annotate_code(
    code_id: UUID,
    payload: HsnCodeAnnotateRequest,
    session: DbSession,
    current_user: CurrentUser,
) -> HsnDetailResponse:
    _require_admin(current_user)
    code = session.get(HsnCode, code_id)
    if code is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="HSN code not found.")
    if payload.is_active is not None:
        code.is_active = payload.is_active
    if payload.notes:
        session.add(
            HsnSourceEvidence(
                hsn_code_id=code.id,
                source_name=current_user.user.email,
                evidence_type="manual_admin",
                raw_text_excerpt=payload.notes[:2000],
                document_title="Admin annotation",
                document_date=datetime.now(UTC),
                confidence_weight=0,
            )
        )
    session.commit()
    session.refresh(code)
    return _detail_response(session, code)


@router.get("/{code}", response_model=HsnDetailResponse)
def get_detail(code: str, session: DbSession, current_user: CurrentUser) -> HsnDetailResponse:
    try:
        normalized = normalize_strict(code)
    except InvalidHsnCodeError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        ) from error
    row = session.scalars(
        select(HsnCode)
        .where(HsnCode.normalized_code == normalized, HsnCode.is_active.is_(True))
        .order_by(HsnCode.updated_at.desc())
    ).first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No HSN match found in the imported HSN master data. This does not mean the HSN does not exist.",
        )
    return _detail_response(session, row)


def _detail_response(session: DbSession, row: HsnCode) -> HsnDetailResponse:
    incentive_available = (
        session.scalars(select(RateTable.id).where(RateTable.hsn == row.normalized_code).limit(1)).first()
        is not None
    )
    return HsnDetailResponse(
        code=row.code,
        normalized_code=row.normalized_code,
        description=row.description,
        digit_level=row.digit_level,
        hierarchy=HsnHierarchy(
            chapter_code=row.chapter_code,
            heading_code=row.heading_code,
            subheading_code=row.subheading_code,
            parent_code=row.parent_code,
        ),
        unit_of_quantity=row.unit_of_quantity,
        section_name=row.section_name,
        chapter_name=row.chapter_name,
        import_policy=row.import_policy,
        export_policy=row.export_policy,
        policy_condition=row.policy_condition,
        source_name=row.source_name,
        source_url=row.source_url,
        source_document_title=row.source_document_title,
        source_document_date=row.source_document_date,
        source_version=row.source_version,
        is_active=row.is_active,
        source_evidence=_evidence_items(session, row.id),
        incentive_rate_available=incentive_available,
    )
