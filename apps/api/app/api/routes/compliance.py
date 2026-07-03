# ruff: noqa: E501
from __future__ import annotations

import secrets
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, OptionalCurrentUser
from app.core.settings import get_settings
from app.models import (
    ComplianceCheckSession,
    ComplianceRequirement,
    ComplianceRequirementEvidence,
    ComplianceRetrievalJob,
    ComplianceScrapeRun,
    ComplianceSourceRegistry,
    MembershipRole,
)
from app.schemas.compliance import (
    ComplianceCheckerRequest,
    ComplianceCheckerResponse,
    ComplianceCheckRequest,
    ComplianceCheckResponse,
    ComplianceCheckSessionResponse,
    ComplianceCoverageCell,
    ComplianceCoverageResponse,
    ComplianceOptionsResponse,
    ComplianceScrapeRunRequest,
    ComplianceScrapeRunResponse,
    ComplianceSourceChangeDetailResponse,
    ComplianceSourceChangeResponse,
    DueComplianceSourceResponse,
    ManualComplianceIngestRequest,
    ManualComplianceIngestResponse,
    RequirementReviewRequest,
    RequirementReviewResponse,
    RetrievalJobCreateRequest,
    RetrievalJobResponse,
    ReviewQueueItem,
    SourceChangeReviewRequest,
    SourceRegistryCreateRequest,
    SourceRegistryResponse,
)
from app.services.compliance_answer import CountryComplianceCheckerService
from app.services.compliance_check_service import ComplianceCheckService
from app.services.compliance_normalization import SUPPORTED_CATEGORIES, SUPPORTED_COUNTRIES
from app.services.compliance_queue import enqueue_retrieval_job, retry_job
from app.services.compliance_scraper import ComplianceScraperError, get_compliance_scraper
from app.services.compliance_store import (
    ComplianceKnowledgeStore,
    ComplianceStoreConfigurationError,
    StoredSourceChange,
    StoredSourceChangeDetail,
    get_compliance_knowledge_store,
)

router = APIRouter(prefix="/compliance", tags=["compliance"])


def require_editor(current_user: CurrentUser) -> None:
    if current_user.membership.role == MembershipRole.READ_ONLY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Read-only members cannot update compliance source data.",
        )


def require_admin(current_user: CurrentUser) -> None:
    """Admin actions (approve/reject requirements, manage sources) require OWNER role."""
    if current_user.membership.role != MembershipRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only organisation owners can review compliance requirements or sources.",
        )


def require_admin_or_cron(
    current_user: CurrentUser | None,
    cron_token: str | None,
    tenant_id: UUID | None,
) -> UUID:
    settings = get_settings()
    expected = settings.admin_cron_token
    if expected and cron_token and secrets.compare_digest(cron_token, expected):
        if current_user is None:
            if tenant_id is not None:
                return tenant_id
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="tenant_id is required when using ADMIN_CRON_TOKEN.",
            )
        return current_user.organization.id
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin authentication or ADMIN_CRON_TOKEN is required.",
        )
    require_admin(current_user)
    return current_user.organization.id


@router.get("/options", response_model=ComplianceOptionsResponse)
def get_compliance_options(current_user: CurrentUser) -> ComplianceOptionsResponse:
    settings = get_settings()
    return ComplianceOptionsResponse(
        countries=list(SUPPORTED_COUNTRIES),
        categories=list(SUPPORTED_CATEGORIES),
        recommended_scraping_stack=[
            "Tavily Search API for low-volume official-source discovery",
            "Firecrawl API for page/PDF extraction into markdown or JSON",
            "Manual review before any scraped evidence becomes approved",
        ],
        knowledge_store_backend=settings.compliance_store_backend,
        refresh_interval_days=settings.compliance_refresh_interval_days,
    )


@router.post("/checker/answer", response_model=ComplianceCheckerResponse)
def answer_country_compliance_checker(
    payload: ComplianceCheckerRequest,
    session: DbSession,
    current_user: CurrentUser,
) -> ComplianceCheckerResponse:
    service = CountryComplianceCheckerService(session)
    try:
        return service.answer(
            payload=payload,
            tenant_id=current_user.organization.id,
            user_id=current_user.user.id,
        )
    except ComplianceStoreConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)
        ) from error


def _store_for_request(
    session: DbSession,
    current_user: CurrentUser,
) -> ComplianceKnowledgeStore:
    try:
        return get_compliance_knowledge_store(
            session=session,
            tenant_id=current_user.organization.id,
        )
    except ComplianceStoreConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error


def _source_change_response(change: StoredSourceChange) -> ComplianceSourceChangeResponse:
    return ComplianceSourceChangeResponse(
        id=change.id,
        source_url=change.source_url,
        country=change.country,
        category=change.category,
        previous_snapshot_id=change.previous_snapshot_id,
        current_snapshot_id=change.current_snapshot_id,
        previous_content_hash=change.previous_content_hash,
        current_content_hash=change.current_content_hash,
        status=change.status,
        reviewed_by=change.reviewed_by,
        reviewed_at=change.reviewed_at,
        notes=change.notes,
        created_at=change.created_at,
    )


def _source_change_detail_response(
    change: StoredSourceChangeDetail,
) -> ComplianceSourceChangeDetailResponse:
    return ComplianceSourceChangeDetailResponse(
        id=change.id,
        source_url=change.source_url,
        country=change.country,
        category=change.category,
        previous_snapshot_id=change.previous_snapshot_id,
        current_snapshot_id=change.current_snapshot_id,
        previous_content_hash=change.previous_content_hash,
        current_content_hash=change.current_content_hash,
        status=change.status,
        reviewed_by=change.reviewed_by,
        reviewed_at=change.reviewed_at,
        notes=change.notes,
        created_at=change.created_at,
        current_title=change.current_title,
        current_scraped_at=change.current_scraped_at,
        current_markdown_excerpt=change.current_markdown_excerpt,
        previous_title=change.previous_title,
        previous_scraped_at=change.previous_scraped_at,
        previous_markdown_excerpt=change.previous_markdown_excerpt,
        excerpt_notice=(
            "Review excerpts are for operator triage. Open the official source before approving "
            "or changing compliance requirements."
        ),
    )


@router.post("/scrape/ingest", response_model=ManualComplianceIngestResponse)
def ingest_compliance_records(
    payload: ManualComplianceIngestRequest,
    session: DbSession,
    current_user: CurrentUser,
) -> ManualComplianceIngestResponse:
    require_editor(current_user)
    store = _store_for_request(session, current_user)
    created, updated = store.ingest(payload.records)
    session.commit()
    return ManualComplianceIngestResponse(
        created=created, updated=updated, total=len(payload.records)
    )


@router.post("/scrape/run", response_model=ComplianceScrapeRunResponse)
def run_compliance_scrape(
    payload: ComplianceScrapeRunRequest,
    session: DbSession,
    current_user: CurrentUser,
) -> ComplianceScrapeRunResponse:
    require_editor(current_user)
    run = ComplianceScrapeRun(
        tenant_id=current_user.organization.id,
        source_url=payload.source_url,
        country=payload.country,
        category=payload.category,
        status="running",
        records_found=0,
        errors=None,
    )
    session.add(run)
    session.flush()
    scraper = get_compliance_scraper()
    try:
        store = _store_for_request(session, current_user)
        document = scraper.scrape(payload.source_url)
        snapshot = store.record_source_snapshot(
            source_url=document.source_url,
            country=payload.country,
            category=payload.category,
            title=document.title,
            markdown=document.markdown,
        )
    except (ComplianceScraperError, ComplianceStoreConfigurationError) as error:
        run.status = "failed"
        run.completed_at = datetime.now(UTC)
        run.errors = {"message": str(error)}
        session.commit()
        return ComplianceScrapeRunResponse(
            run_id=str(run.id),
            status=run.status,
            records_found=0,
            message=f"source={payload.source_url} error={error}",
        )

    run.status = snapshot.status
    run.completed_at = datetime.now(UTC)
    run.records_found = 0
    run.errors = None
    session.commit()
    return ComplianceScrapeRunResponse(
        run_id=str(run.id),
        status=run.status,
        records_found=0,
        message=snapshot.message,
    )


@router.get("/scrape/due", response_model=list[DueComplianceSourceResponse])
def list_due_compliance_sources(
    session: DbSession,
    current_user: CurrentUser,
    limit: int = 25,
) -> list[DueComplianceSourceResponse]:
    require_editor(current_user)
    store = _store_for_request(session, current_user)
    return [
        DueComplianceSourceResponse(
            source_url=source.source_url,
            country=source.country,
            category=source.category,
            last_checked_at=source.last_checked_at,
        )
        for source in store.due_sources(limit=max(1, min(limit, 100)))
    ]


@router.get("/scrape/changes", response_model=list[ComplianceSourceChangeResponse])
def list_source_changes(
    session: DbSession,
    current_user: CurrentUser,
    status_filter: str = "needs_review",
    limit: int = 50,
) -> list[ComplianceSourceChangeResponse]:
    require_editor(current_user)
    store = _store_for_request(session, current_user)
    return [
        _source_change_response(change)
        for change in store.list_source_changes(
            status=status_filter,
            limit=max(1, min(limit, 100)),
        )
    ]


@router.get(
    "/scrape/changes/{change_id}",
    response_model=ComplianceSourceChangeDetailResponse,
)
def get_source_change_detail(
    change_id: str,
    session: DbSession,
    current_user: CurrentUser,
) -> ComplianceSourceChangeDetailResponse:
    require_editor(current_user)
    store = _store_for_request(session, current_user)
    try:
        change = store.get_source_change_detail(change_id=change_id)
    except (ComplianceStoreConfigurationError, ValueError) as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return _source_change_detail_response(change)


@router.get("/coverage", response_model=ComplianceCoverageResponse)
def get_compliance_coverage(
    session: DbSession,
    current_user: CurrentUser,
) -> ComplianceCoverageResponse:
    require_editor(current_user)
    settings = get_settings()
    store = _store_for_request(session, current_user)
    countries = list(SUPPORTED_COUNTRIES)
    categories = list(SUPPORTED_CATEGORIES)
    cells = [
        ComplianceCoverageCell(
            country=cell.country,
            category=cell.category,
            total_records=cell.total_records,
            approved_fresh_records=cell.approved_fresh_records,
            pending_or_draft_records=cell.pending_or_draft_records,
            stale_records=cell.stale_records,
            official_sources=cell.official_sources,
            latest_checked_at=cell.latest_checked_at,
            status=cell.status,  # type: ignore[arg-type]
        )
        for cell in store.coverage_cells(countries=countries, categories=categories)
    ]
    due_sources_count = len(store.due_sources(limit=100))
    source_changes_needing_review = len(
        store.list_source_changes(status="needs_review", limit=100)
    )
    return ComplianceCoverageResponse(
        refresh_interval_days=settings.compliance_refresh_interval_days,
        supported_countries=countries,
        supported_categories=categories,
        cells=cells,
        due_sources_count=due_sources_count,
        source_changes_needing_review=source_changes_needing_review,
        disclaimer=(
            "Coverage status reports data governance health only. It does not certify that "
            "a country/category database is complete or legally authoritative."
        ),
    )


@router.post(
    "/scrape/changes/{change_id}/review",
    response_model=ComplianceSourceChangeResponse,
)
def review_source_change(
    change_id: str,
    payload: SourceChangeReviewRequest,
    session: DbSession,
    current_user: CurrentUser,
) -> ComplianceSourceChangeResponse:
    require_editor(current_user)
    store = _store_for_request(session, current_user)
    try:
        change = store.review_source_change(
            change_id=change_id,
            status=payload.status,
            reviewed_by=current_user.user.email,
            notes=payload.notes,
        )
    except (ComplianceStoreConfigurationError, ValueError) as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    session.commit()
    return _source_change_response(change)


# ── Country Compliance Checker v1 endpoints ───────────────────────────────────

def _retrieval_job_response(job: ComplianceRetrievalJob) -> RetrievalJobResponse:
    return RetrievalJobResponse(
        id=str(job.id),
        status=job.status,
        destination_country=job.destination_country,
        product_category=job.product_category,
        hsn_code=job.hsn_code,
        pages_fetched=job.pages_fetched,
        snapshots_created=job.snapshots_created,
        requirements_extracted=job.requirements_extracted,
        retry_count=job.retry_count,
        max_retries=job.max_retries,
        source_registry_ids=list(job.source_registry_ids_json or []),
        error_message=job.error_message,
        started_at=job.started_at,
        completed_at=job.completed_at,
        created_at=job.created_at,
        message={
            "queued": "Official-source retrieval is in progress. Results will require review before becoming approved guidance.",
            "running": "Official-source retrieval is running.",
            "needs_review": "Retrieval complete. Extracted requirements are pending admin review.",
            "completed": "Retrieval complete. No new pending requirements were extracted.",
            "failed": job.error_message or "Retrieval failed.",
        }.get(job.status, job.status),
    )


@router.post("/check", response_model=ComplianceCheckResponse)
def run_compliance_check(
    payload: ComplianceCheckRequest,
    background_tasks: BackgroundTasks,
    session: DbSession,
    current_user: CurrentUser,
) -> ComplianceCheckResponse:
    service = ComplianceCheckService(session)
    response = service.check(
        payload=payload,
        tenant_id=current_user.organization.id,
        user_id=current_user.user.id,
    )
    # Non-blocking: kick off the queued retrieval job after the response returns.
    if response.retrieval_job_id:
        enqueue_retrieval_job(
            background_tasks,
            job_id=UUID(response.retrieval_job_id),
            tenant_id=current_user.organization.id,
        )
    return response


@router.get("/sessions/{session_id}", response_model=ComplianceCheckSessionResponse)
def get_compliance_check_session(
    session_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
) -> ComplianceCheckSessionResponse:
    from app.schemas.compliance import ComplianceRequirementCard, ComplianceSourceReference
    from app.services.compliance_answer import DISCLAIMER
    from app.services.compliance_check_service import WARNINGS

    row = session.get(ComplianceCheckSession, session_id)
    if row is None or row.tenant_id != current_user.organization.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
    summary = row.answer_summary_json or {}
    groups = summary.get("groups", {}) if isinstance(summary, dict) else {}
    requirements = {
        key: [ComplianceRequirementCard(**card) for card in cards]
        for key, cards in groups.items()
    }
    sources: list[ComplianceSourceReference] = []
    for cards in requirements.values():
        for card in cards:
            if card.source_url:
                sources.append(
                    ComplianceSourceReference(
                        source_name=card.source_name or "",
                        source_url=card.source_url,
                        last_checked_date=card.last_checked_date,
                        expires_at=None,
                        source_authority_level="official",
                    )
                )
    return ComplianceCheckSessionResponse(
        session_id=str(row.id),
        status=row.status,
        answer_summary=summary.get("summary", "") if isinstance(summary, dict) else "",
        requirements=requirements,
        missing_questions=list(row.missing_questions_json or []),
        buyer_questions=[],
        cha_questions=[],
        confidence_label=row.confidence_label or "Low",  # type: ignore[arg-type]
        confidence_score=0.0,
        sources=sources,
        warnings=list(WARNINGS),
        retrieval_job_id=str(row.retrieval_job_id) if row.retrieval_job_id else None,
        disclaimer=DISCLAIMER,
        origin_country=row.origin_country,
        destination_country=row.destination_country,
        product_category=row.product_category,
        hsn_code=row.hsn_code,
        created_at=row.created_at,
    )


@router.post("/retrieval-jobs", response_model=RetrievalJobResponse)
def create_retrieval_job(
    payload: RetrievalJobCreateRequest,
    background_tasks: BackgroundTasks,
    session: DbSession,
    current_user: CurrentUser,
) -> RetrievalJobResponse:
    require_editor(current_user)
    job = ComplianceRetrievalJob(
        tenant_id=current_user.organization.id,
        requested_by_user_id=current_user.user.id,
        origin_country=payload.origin_country,
        destination_country=payload.destination_country,
        product_category=payload.product_category,
        hsn_code=payload.hsn_code,
        product_description=payload.product_description,
        status="queued",
        max_retries=max(0, get_settings().compliance_max_retries),
    )
    session.add(job)
    session.commit()
    enqueue_retrieval_job(
        background_tasks, job_id=job.id, tenant_id=current_user.organization.id
    )
    return _retrieval_job_response(job)


@router.get("/retrieval-jobs/{job_id}", response_model=RetrievalJobResponse)
def get_retrieval_job(
    job_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
) -> RetrievalJobResponse:
    job = session.get(ComplianceRetrievalJob, job_id)
    if job is None or job.tenant_id != current_user.organization.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Retrieval job not found.")
    return _retrieval_job_response(job)


@router.post("/retrieval-jobs/{job_id}/retry", response_model=RetrievalJobResponse)
def retry_retrieval_job(
    job_id: UUID,
    background_tasks: BackgroundTasks,
    session: DbSession,
    current_user: CurrentUser,
) -> RetrievalJobResponse:
    require_editor(current_user)
    job = retry_job(
        background_tasks, session, job_id=job_id, tenant_id=current_user.organization.id
    )
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Retrieval job not found.")
    session.commit()
    return _retrieval_job_response(job)


@router.get("/review-queue", response_model=list[ReviewQueueItem])
def list_review_queue(
    session: DbSession,
    current_user: CurrentUser,
    limit: int = 50,
) -> list[ReviewQueueItem]:
    require_admin(current_user)
    from app.models import ComplianceCountry, ProductCategory

    rows = session.execute(
        select(ComplianceRequirement, ComplianceCountry, ProductCategory)
        .join(ComplianceCountry, ComplianceRequirement.country_id == ComplianceCountry.id)
        .join(ProductCategory, ComplianceRequirement.category_id == ProductCategory.id)
        .where(
            ComplianceRequirement.tenant_id == current_user.organization.id,
            ComplianceRequirement.review_status == "pending",
        )
        .order_by(ComplianceRequirement.created_at.desc())
        .limit(max(1, min(limit, 200)))
    ).all()
    items: list[ReviewQueueItem] = []
    for requirement, country, category in rows:
        evidence = session.scalars(
            select(ComplianceRequirementEvidence).where(
                ComplianceRequirementEvidence.requirement_id == requirement.id
            )
        ).all()
        items.append(
            ReviewQueueItem(
                requirement_id=str(requirement.id),
                country=country.name,
                category=category.name,
                hsn_code=requirement.hsn_code,
                requirement_type=requirement.requirement_type,
                title=requirement.requirement_text[:120],
                detail=requirement.requirement_text,
                confidence_score=float(requirement.confidence_score),
                review_status=requirement.review_status,
                source_name=requirement.source_name,
                source_url=requirement.source_url,
                evidence_excerpts=[e.evidence_excerpt for e in evidence],
                created_at=requirement.created_at,
            )
        )
    return items


@router.post("/requirements/{requirement_id}/approve", response_model=RequirementReviewResponse)
def approve_requirement(
    requirement_id: UUID,
    payload: RequirementReviewRequest,
    session: DbSession,
    current_user: CurrentUser,
) -> RequirementReviewResponse:
    require_admin(current_user)
    requirement = session.get(ComplianceRequirement, requirement_id)
    if requirement is None or requirement.tenant_id != current_user.organization.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requirement not found.")
    requirement.review_status = "approved"
    requirement.status = "active"  # now eligible to appear in answers
    requirement.reviewed_by = current_user.user.email
    requirement.reviewed_at = datetime.now(UTC)
    if payload.notes:
        requirement.notes = payload.notes
    session.commit()
    return RequirementReviewResponse(
        requirement_id=str(requirement.id),
        review_status=requirement.review_status,
        status=requirement.status,
        reviewed_by=requirement.reviewed_by,
    )


@router.post("/requirements/{requirement_id}/reject", response_model=RequirementReviewResponse)
def reject_requirement(
    requirement_id: UUID,
    payload: RequirementReviewRequest,
    session: DbSession,
    current_user: CurrentUser,
) -> RequirementReviewResponse:
    require_admin(current_user)
    requirement = session.get(ComplianceRequirement, requirement_id)
    if requirement is None or requirement.tenant_id != current_user.organization.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requirement not found.")
    requirement.review_status = "rejected"
    requirement.status = "archived"
    requirement.reviewed_by = current_user.user.email
    requirement.reviewed_at = datetime.now(UTC)
    if payload.notes:
        requirement.notes = payload.notes
    session.commit()
    return RequirementReviewResponse(
        requirement_id=str(requirement.id),
        review_status=requirement.review_status,
        status=requirement.status,
        reviewed_by=requirement.reviewed_by,
    )


def _source_registry_response(row: ComplianceSourceRegistry) -> SourceRegistryResponse:
    return SourceRegistryResponse(
        id=str(row.id),
        country=row.country,
        authority_name=row.authority_name,
        source_name=row.source_name,
        base_url=row.base_url,
        allowed_domains=list(row.allowed_domains_json or []),
        source_type=row.source_type,
        product_categories=list(row.product_categories_json or []),
        is_active=row.is_active,
        refresh_frequency_days=row.refresh_frequency_days,
        last_checked_at=row.last_checked_at,
        created_at=row.created_at,
    )


@router.get("/sources", response_model=list[SourceRegistryResponse])
def list_sources(
    session: DbSession,
    current_user: CurrentUser,
) -> list[SourceRegistryResponse]:
    require_admin(current_user)
    rows = session.scalars(
        select(ComplianceSourceRegistry)
        .where(ComplianceSourceRegistry.tenant_id == current_user.organization.id)
        .order_by(ComplianceSourceRegistry.country, ComplianceSourceRegistry.source_name)
    ).all()
    return [_source_registry_response(r) for r in rows]


@router.post("/sources", response_model=SourceRegistryResponse, status_code=status.HTTP_201_CREATED)
def create_source(
    payload: SourceRegistryCreateRequest,
    session: DbSession,
    current_user: CurrentUser,
) -> SourceRegistryResponse:
    require_admin(current_user)
    # Enforce whitelist: base_url host must be officially allowed (builtin/env/its own domains).
    from app.services.compliance_whitelist import DomainNotWhitelistedError, assert_domain_allowed

    try:
        assert_domain_allowed(payload.base_url, payload.allowed_domains)
    except DomainNotWhitelistedError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    row = ComplianceSourceRegistry(
        tenant_id=current_user.organization.id,
        country=payload.country,
        authority_name=payload.authority_name,
        source_name=payload.source_name,
        base_url=payload.base_url,
        allowed_domains_json=payload.allowed_domains,
        source_type=payload.source_type,
        product_categories_json=payload.product_categories,
        refresh_frequency_days=payload.refresh_frequency_days,
        is_active=True,
    )
    session.add(row)
    session.commit()
    return _source_registry_response(row)


@router.post("/sources/seed")
def seed_sources(
    session: DbSession,
    current_user: CurrentUser,
) -> dict[str, int]:
    """Idempotently register the curated official sources for this org (admin)."""
    require_admin(current_user)
    from app.services.compliance_source_seed import seed_official_sources

    result = seed_official_sources(session, current_user.organization.id)
    session.commit()
    return result


@router.post("/refresh-due")
def refresh_due(
    session: DbSession,
    current_user: OptionalCurrentUser,
    x_admin_cron_token: str | None = Header(default=None, alias="X-Admin-Cron-Token"),
    tenant_id: UUID | None = None,
    limit: int = 25,
) -> dict:
    """Re-crawl all due official sources for this org (admin / scheduler entrypoint)."""
    tenant_id = require_admin_or_cron(current_user, x_admin_cron_token, tenant_id)
    from app.services.compliance_refresh import refresh_due_sources

    result = refresh_due_sources(
        session, tenant_id=tenant_id, limit=max(1, min(limit, 100))
    )
    session.commit()
    return result


@router.post("/sources/{source_id}/refresh", response_model=RetrievalJobResponse)
def refresh_source(
    source_id: UUID,
    background_tasks: BackgroundTasks,
    session: DbSession,
    current_user: CurrentUser,
) -> RetrievalJobResponse:
    require_admin(current_user)
    source = session.get(ComplianceSourceRegistry, source_id)
    if source is None or source.tenant_id != current_user.organization.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found.")
    category = (source.product_categories_json or ["food/agri"])[0]
    job = ComplianceRetrievalJob(
        tenant_id=current_user.organization.id,
        requested_by_user_id=current_user.user.id,
        destination_country=source.country,
        product_category=category,
        status="queued",
        source_registry_ids_json=[str(source.id)],
        max_retries=max(0, get_settings().compliance_max_retries),
    )
    session.add(job)
    session.commit()
    enqueue_retrieval_job(
        background_tasks, job_id=job.id, tenant_id=current_user.organization.id, force=True
    )
    return _retrieval_job_response(job)
