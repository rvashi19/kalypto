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
    ComplianceOptionsResponse,
    ComplianceScrapeRunRequest,
    ComplianceScrapeRunResponse,
    ManualComplianceIngestRequest,
    ManualComplianceIngestResponse,
)
from app.services.compliance_answer import CountryComplianceCheckerService
from app.services.compliance_normalization import SUPPORTED_CATEGORIES, SUPPORTED_COUNTRIES
from app.services.compliance_scraper import ComplianceScraperError, get_compliance_scraper
from app.services.compliance_store import (
    ComplianceStoreConfigurationError,
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


@router.post("/scrape/ingest", response_model=ManualComplianceIngestResponse)
def ingest_compliance_records(
    payload: ManualComplianceIngestRequest,
    session: DbSession,
    current_user: CurrentUser,
) -> ManualComplianceIngestResponse:
    require_editor(current_user)
    try:
        store = get_compliance_knowledge_store(
            session=session, tenant_id=current_user.organization.id
        )
    except ComplianceStoreConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)
        ) from error
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
        store = get_compliance_knowledge_store(
            session=session, tenant_id=current_user.organization.id
        )
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
