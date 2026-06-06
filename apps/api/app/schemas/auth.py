from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints

from app.models import MembershipRole

EmailValue = Annotated[str, StringConstraints(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=320)]


class OrganizationSummary(BaseModel):
    id: UUID
    name: str
    slug: str


class MembershipSummary(BaseModel):
    organization_id: UUID
    role: MembershipRole


class UserSummary(BaseModel):
    id: UUID
    email: EmailValue
    full_name: str | None


class RegisterRequest(BaseModel):
    email: EmailValue
    password: str = Field(min_length=12, max_length=128)
    organization_name: str = Field(min_length=2, max_length=255)
    organization_slug: str | None = Field(default=None, min_length=2, max_length=120)
    full_name: str | None = Field(default=None, max_length=255)


class LoginRequest(BaseModel):
    email: EmailValue
    password: str = Field(min_length=12, max_length=128)
    organization_id: UUID | None = None


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserSummary
    organization: OrganizationSummary
    membership: MembershipSummary


class LogoutResponse(BaseModel):
    success: bool


class CurrentUserResponse(BaseModel):
    user: UserSummary
    organization: OrganizationSummary
    membership: MembershipSummary
