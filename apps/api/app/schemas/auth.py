from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints

from app.models import MembershipRole

EmailValue = Annotated[
    str, StringConstraints(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=320)
]


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
    email_verified_at: datetime | None = None
    two_factor_enabled: bool = False


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
    otp_code: str | None = Field(default=None, min_length=6, max_length=8)


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


class TwoFactorSetupResponse(BaseModel):
    secret: str
    otpauth_uri: str


class TwoFactorEnableRequest(BaseModel):
    otp_code: str = Field(min_length=6, max_length=8)
