from fastapi import APIRouter

from app.api.deps import CurrentUser
from app.schemas.dashboard import DashboardOverview

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/overview", response_model=DashboardOverview)
def get_dashboard_overview(current_user: CurrentUser) -> DashboardOverview:
    return DashboardOverview(
        organization_id=current_user.organization.id,
        organization_name=current_user.organization.name,
        role=current_user.membership.role,
        message="Your tenant-scoped export incentive workspace is ready for Phase 1 data flows.",
    )
