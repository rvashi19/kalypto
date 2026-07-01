from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models import MembershipRole


class DashboardOverview(BaseModel):
    organization_id: UUID
    organization_name: str
    role: MembershipRole
    message: str


class DashboardDiscrepancyItem(BaseModel):
    id: UUID
    shipment_id: UUID
    type: str
    severity: str
    message: str
    suggested_fix: str | None
    lock_risk: bool
    potential_amount: float | None
    created_at: datetime

    model_config = {"from_attributes": True}


class DiscrepancyDashboardResponse(BaseModel):
    total: int
    critical: int
    warning: int
    lock_risk: int
    potential_amount: float
    items: list[DashboardDiscrepancyItem]
    disclaimer: str
