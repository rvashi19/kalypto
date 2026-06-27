# ruff: noqa: E501
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.core.settings import get_settings
from app.models import ComplianceScrapeRun, MembershipRole
from app.schemas.compliance import (
    ComplianceCheckerRequest,
    ComplianceCheckerResponse,
    ComplianceCoverageCell,
    ComplianceCoverageResponse,
    ComplianceOptionsResponse,
    ComplianceScrapeRunRequest,
    ComplianceScrapeRunResponse,
    ComplianceSourceChangeResponse,
    DueComplianceSourceResponse,
    ManualComplianceIngestRequest,
    ManualComplianceIngestResponse,
    SourceChangeReviewRequest,
)
from app.services.compliance_answer import CountryComplianceCheckerService
from app.services.compliance_normalization import SUPPORTED_CATEGORIES, SUPPORTED_COUNTRIES
from app.services.compliance_scraper import ComplianceScraperError, get_compliance_scraper
from app.services.compliance_store import (
    ComplianceKnowledgeStore,
    ComplianceStoreConfigurationError,
    StoredSourceChange,
    get_compliance_knowledge_store,
)

router = APIRouter(prefix="/compliance", tags=["compliance"])


def require_editor(current_user: CurrentUser) -> None:
    if current_user.membership.role == MembershipRole.READ_ONLY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Read-only members cannot update compliance source data.",
        )


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
