from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from app.models import MembershipRole


class DashboardOverview(BaseModel):
    organization_id: UUID
    organization_name: str
    role: MembershipRole
    message: str
