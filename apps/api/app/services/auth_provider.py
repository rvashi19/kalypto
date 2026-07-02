from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import (
    create_access_token,
    hash_password,
    validate_password_policy,
    verify_password,
    verify_totp_code,
)
from app.core.settings import get_settings
from app.models import Membership, MembershipRole, Organization, RevokedToken, User
from app.schemas.auth import AuthResponse, MembershipSummary, OrganizationSummary, UserSummary
from app.services.audit import AuditLogger


class AuthenticationError(ValueError):
    """Raised when authentication fails."""


class AuthProvider(Protocol):
    def register(
        self,
        *,
        session: Session,
        email: str,
        password: str,
        organization_name: str,
        organization_slug: str | None,
        full_name: str | None,
    ) -> AuthResponse: ...

    def login(
        self,
        *,
        session: Session,
        email: str,
        password: str,
        organization_id: UUID | None,
        otp_code: str | None = None,
    ) -> AuthResponse: ...

    def logout(
        self,
        *,
        session: Session,
        user_id: UUID,
        tenant_id: UUID,
        jti: str,
        expires_at: datetime,
    ) -> None: ...


def slugify_organization(name: str) -> str:
    normalized = "".join(character.lower() if character.isalnum() else "-" for character in name)
    collapsed = "-".join(part for part in normalized.split("-") if part)
    return collapsed[:120] or "organization"


def build_auth_response(
    *, user: User, organization: Organization, membership: Membership
) -> AuthResponse:
    access_token, expires_at, _ = create_access_token(
        user_id=user.id,
        tenant_id=organization.id,
        role=membership.role.value,
    )
    return AuthResponse(
        access_token=access_token,
        expires_at=expires_at,
        user=UserSummary.model_validate(user, from_attributes=True),
        organization=OrganizationSummary.model_validate(organization, from_attributes=True),
        membership=MembershipSummary(organization_id=organization.id, role=membership.role),
    )


class LocalAuthProvider:
    def register(
        self,
        *,
        session: Session,
        email: str,
        password: str,
        organization_name: str,
        organization_slug: str | None,
        full_name: str | None,
    ) -> AuthResponse:
        audit = AuditLogger(session)
        existing_user = session.scalars(select(User).where(User.email == email.lower())).first()
        if existing_user is not None:
            raise AuthenticationError("An account with that email already exists.")
        try:
            validate_password_policy(password)
        except ValueError as error:
            raise AuthenticationError(str(error)) from error

        slug = organization_slug or slugify_organization(organization_name)
        existing_org = session.scalars(
            select(Organization).where(Organization.slug == slug)
        ).first()
        if existing_org is not None:
            raise AuthenticationError("That organization slug is already in use.")

        organization = Organization(name=organization_name, slug=slug)
        settings = get_settings()
        user = User(
            email=email.lower(),
            password_hash=hash_password(password),
            full_name=full_name,
            email_verified_at=None
            if settings.require_email_verification
            else datetime.now(UTC),
        )

        session.add_all([organization, user])
        session.flush()

        membership = Membership(
            organization_id=organization.id,
            user_id=user.id,
            role=MembershipRole.OWNER,
        )
        session.add(membership)
        audit.log(
            action="auth.register",
            entity_type="organization",
            entity_id=str(organization.id),
            tenant_id=organization.id,
            actor_user_id=user.id,
            details={"email": user.email},
        )
        session.commit()
        session.refresh(organization)
        session.refresh(user)
        session.refresh(membership)
        return build_auth_response(user=user, organization=organization, membership=membership)

    def login(
        self,
        *,
        session: Session,
        email: str,
        password: str,
        organization_id: UUID | None,
        otp_code: str | None = None,
    ) -> AuthResponse:
        audit = AuditLogger(session)
        user = session.scalars(select(User).where(User.email == email.lower())).first()
        if user is None or not verify_password(password, user.password_hash):
            raise AuthenticationError("Invalid email or password.")
        if not user.is_active:
            raise AuthenticationError("This account is disabled.")
        settings = get_settings()
        if settings.require_email_verification and user.email_verified_at is None:
            raise AuthenticationError("Please verify your email before signing in.")
        if user.two_factor_enabled:
            if not otp_code:
                raise AuthenticationError("Two-factor authentication code required.")
            if not user.two_factor_secret or not verify_totp_code(user.two_factor_secret, otp_code):
                raise AuthenticationError("Invalid two-factor authentication code.")

        membership_query = select(Membership).where(Membership.user_id == user.id)
        if organization_id is not None:
            membership_query = membership_query.where(Membership.organization_id == organization_id)

        membership = session.scalars(membership_query).first()
        if membership is None:
            raise AuthenticationError("No organization membership is available for that login.")

        organization = session.get(Organization, membership.organization_id)
        if organization is None:
            raise AuthenticationError("Organization membership is invalid.")

        audit.log(
            action="auth.login",
            entity_type="user",
            entity_id=str(user.id),
            tenant_id=organization.id,
            actor_user_id=user.id,
        )
        session.commit()
        return build_auth_response(user=user, organization=organization, membership=membership)

    def logout(
        self,
        *,
        session: Session,
        user_id: UUID,
        tenant_id: UUID,
        jti: str,
        expires_at: datetime,
    ) -> None:
        audit = AuditLogger(session)
        revoked = RevokedToken(user_id=user_id, tenant_id=tenant_id, jti=jti, expires_at=expires_at)
        session.add(revoked)
        audit.log(
            action="auth.logout",
            entity_type="token",
            entity_id=jti,
            tenant_id=tenant_id,
            actor_user_id=user_id,
        )
        session.commit()
