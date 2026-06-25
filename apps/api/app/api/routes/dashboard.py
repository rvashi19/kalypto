from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.models import DiscrepancySeverity, ExportDiscrepancy
from app.repositories.base import TenantRepository
from app.schemas.dashboard import (
    DashboardDiscrepancyItem,
    DashboardOverview,
    DiscrepancyDashboardResponse,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/overview", response_model=DashboardOverview)
def get_dashboard_overview(current_user: CurrentUser) -> DashboardOverview:
    return DashboardOverview(
        organization_id=current_user.organization.id,
        organization_name=current_user.organization.name,
        role=current_user.membership.role,
        message="Your tenant-scoped export incentive workspace is ready for Phase 1 data flows.",
    )


@router.get("/discrepancies", response_model=DiscrepancyDashboardResponse)
def get_discrepancy_dashboard(
    session: DbSession,
    current_user: CurrentUser,
) -> DiscrepancyDashboardResponse:
    repository = TenantRepository(
        session=session,
        model=ExportDiscrepancy,
        tenant_id=current_user.organization.id,
        actor_user_id=current_user.user.id,
    )
    discrepancies = repository.list()
    potential_amount = sum(
        float(discrepancy.potential_amount or 0) for discrepancy in discrepancies
    )
    return DiscrepancyDashboardResponse(
        total=len(discrepancies),
        critical=sum(
            discrepancy.severity == DiscrepancySeverity.CRITICAL
            for discrepancy in discrepancies
        ),
        warning=sum(
            discrepancy.severity == DiscrepancySeverity.WARN
            for discrepancy in discrepancies
        ),
        lock_risk=sum(discrepancy.lock_risk for discrepancy in discrepancies),
        potential_amount=potential_amount,
        items=[
            DashboardDiscrepancyItem.model_validate(discrepancy)
            for discrepancy in discrepancies
        ],
        disclaimer=(
            "Potential amount is a decision-support estimate from verified rates. "
            "It is not a confirmed under-claim or receivable."
        ),
    )
