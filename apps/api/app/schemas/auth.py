from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints

from app.models import AuthOtpPurpose, AuthProviderPrimary, MembershipRole, UserRole, UserStatus

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
    company_name: str | None = None
    country: str | None = None
    avatar_url: str | None = None
    role: UserRole = UserRole.USER
    status: UserStatus = UserStatus.ACTIVE
    auth_provider_primary: AuthProviderPrimary = AuthProviderPrimary.PASSWORD
    email_verified_at: datetime | None = None
    two_factor_enabled: bool = False


class RegisterRequest(BaseModel):
    email: EmailValue
    password: str = Field(min_length=12, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)
    organization_name: str | None = Field(default=None, min_length=2, max_length=255)
    organization_slug: str | None = Field(default=None, min_length=2, max_length=120)
    company_name: str | None = Field(default=None, max_length=255)
    country: str | None = Field(default=None, max_length=120)


class LoginRequest(BaseModel):
    email: EmailValue
    password: str = Field(min_length=12, max_length=128)
    organization_id: UUID | None = None
    otp_code: str | None = Field(default=None, min_length=6, max_length=8)


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    refresh_expires_at: datetime | None = None
    user: UserSummary
    organization: OrganizationSummary
    membership: MembershipSummary


class RegisterResponse(BaseModel):
    message: str
    email: EmailValue
    verification_required: bool
    access_token: str | None = None
    token_type: str = "bearer"
    expires_at: datetime | None = None
    refresh_expires_at: datetime | None = None
    user: UserSummary | None = None
    organization: OrganizationSummary | None = None
    membership: MembershipSummary | None = None


class VerifyEmailOtpRequest(BaseModel):
    email: EmailValue
    otp: str = Field(pattern=r"^\d{6}$")


class ResendOtpRequest(BaseModel):
    email: EmailValue
    purpose: AuthOtpPurpose = AuthOtpPurpose.EMAIL_VERIFICATION


class GoogleOAuthRequest(BaseModel):
    id_token: str = Field(min_length=20)


class ForgotPasswordRequest(BaseModel):
    email: EmailValue


class ResetPasswordRequest(BaseModel):
    email: EmailValue
    otp: str = Field(pattern=r"^\d{6}$")
    new_password: str = Field(min_length=12, max_length=128)


class AuthMessageResponse(BaseModel):
    message: str


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
