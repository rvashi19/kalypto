from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import (
    create_access_token,
    generate_otp_code,
    generate_refresh_token,
    hash_password,
    hash_token,
    validate_password_policy,
    verify_password,
    verify_totp_code,
)
from app.core.settings import get_settings
from app.models import (
    AuthOtp,
    AuthOtpPurpose,
    AuthProviderPrimary,
    Membership,
    MembershipRole,
    OAuthAccount,
    OAuthProvider,
    Organization,
    RefreshToken,
    RevokedToken,
    User,
    UserStatus,
)
from app.schemas.auth import AuthResponse, MembershipSummary, OrganizationSummary, UserSummary
from app.services.audit import AuditLogger
from app.services.email import send_auth_otp_email
from app.services.google_oauth import verify_google_id_token

OTP_EXPIRES_MINUTES = 10
OTP_RESEND_COOLDOWN_SECONDS = 60


class AuthenticationError(ValueError):
    """Raised when authentication fails."""


class EmailNotVerifiedError(AuthenticationError):
    """Raised when a password login is blocked by email verification."""


class DisabledUserError(AuthenticationError):
    """Raised when a disabled user tries to authenticate."""


class OtpRateLimitError(AuthenticationError):
    """Raised when OTP resend cooldown is still active."""


@dataclass(slots=True)
class RegisterResult:
    email: str
    message: str = "We sent a verification code to your email. Enter it to activate your account."


@dataclass(slots=True)
class AuthSessionBundle:
    auth_response: AuthResponse
    refresh_token: str


class AuthProvider(Protocol):
    def register(
        self,
        *,
        session: Session,
        email: str,
        password: str,
        full_name: str,
        organization_name: str | None,
        organization_slug: str | None,
        company_name: str | None,
        country: str | None,
    ) -> RegisterResult: ...

    def verify_email_otp(self, *, session: Session, email: str, otp: str) -> AuthSessionBundle: ...

    def resend_otp(
        self,
        *,
        session: Session,
        email: str,
        purpose: AuthOtpPurpose,
    ) -> None: ...

    def login(
        self,
        *,
        session: Session,
        email: str,
        password: str,
        organization_id: UUID | None,
        otp_code: str | None = None,
    ) -> AuthSessionBundle: ...

    def google_login(self, *, session: Session, id_token: str) -> AuthSessionBundle: ...

    def refresh(self, *, session: Session, refresh_token: str) -> AuthSessionBundle: ...

    def logout(
        self,
        *,
        session: Session,
        user_id: UUID,
        tenant_id: UUID,
        jti: str,
        expires_at: datetime,
        refresh_token: str | None,
    ) -> None: ...

    def forgot_password(self, *, session: Session, email: str) -> None: ...

    def reset_password(
        self,
        *,
        session: Session,
        email: str,
        otp: str,
        new_password: str,
    ) -> None: ...


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def slugify_organization(name: str) -> str:
    normalized = "".join(character.lower() if character.isalnum() else "-" for character in name)
    collapsed = "-".join(part for part in normalized.split("-") if part)
    return collapsed[:120] or "organization"


def _build_user_summary(user: User) -> UserSummary:
    return UserSummary(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        company_name=user.company_name,
        country=user.country,
        avatar_url=user.avatar_url,
        role=user.role,
        status=user.status,
        auth_provider_primary=user.auth_provider_primary,
        email_verified_at=user.email_verified_at,
        two_factor_enabled=user.two_factor_enabled,
    )


def build_auth_response(
    *,
    user: User,
    organization: Organization,
    membership: Membership,
    refresh_expires_at: datetime | None = None,
) -> AuthResponse:
    access_token, expires_at, _ = create_access_token(
        user_id=user.id,
        tenant_id=organization.id,
        role=membership.role.value,
    )
    return AuthResponse(
        access_token=access_token,
        expires_at=expires_at,
        refresh_expires_at=refresh_expires_at,
        user=_build_user_summary(user),
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
        full_name: str,
        organization_name: str | None,
        organization_slug: str | None,
        company_name: str | None,
        country: str | None,
    ) -> RegisterResult:
        audit = AuditLogger(session)
        normalized_email = _normalize_email(email)
        existing_user = session.scalars(select(User).where(User.email == normalized_email)).first()
        if existing_user is not None:
            raise AuthenticationError("An account with that email already exists.")
        try:
            validate_password_policy(password)
        except ValueError as error:
            raise AuthenticationError(str(error)) from error

        resolved_org_name = (organization_name or company_name or f"{full_name} Workspace").strip()
        slug = self._resolve_organization_slug(
            session=session,
            organization_name=resolved_org_name,
            requested_slug=organization_slug,
        )

        organization = Organization(name=resolved_org_name, slug=slug)
        user = User(
            email=normalized_email,
            password_hash=hash_password(password),
            full_name=full_name.strip(),
            company_name=company_name.strip() if company_name else None,
            country=country.strip() if country else None,
            is_active=True,
            status=UserStatus.PENDING_VERIFICATION,
            email_verified_at=None,
            auth_provider_primary=AuthProviderPrimary.PASSWORD,
        )
        session.add_all([organization, user])
        session.flush()

        membership = Membership(
            organization_id=organization.id,
            user_id=user.id,
            role=MembershipRole.OWNER,
        )
        session.add(membership)
        self._create_and_send_otp(
            session=session,
            user=user,
            email=normalized_email,
            purpose=AuthOtpPurpose.EMAIL_VERIFICATION,
        )
        audit.log(
            action="auth.register",
            entity_type="organization",
            entity_id=str(organization.id),
            tenant_id=organization.id,
            actor_user_id=user.id,
            details={"email": user.email},
        )
        session.commit()
        return RegisterResult(email=normalized_email)

    def verify_email_otp(self, *, session: Session, email: str, otp: str) -> AuthSessionBundle:
        audit = AuditLogger(session)
        normalized_email = _normalize_email(email)
        user = self._get_user_by_email(session=session, email=normalized_email)
        self._verify_otp(
            session=session,
            email=normalized_email,
            purpose=AuthOtpPurpose.EMAIL_VERIFICATION,
            otp=otp,
        )
        user.email_verified_at = user.email_verified_at or _now()
        user.status = UserStatus.ACTIVE
        user.is_active = True
        session.add(user)
        organization, membership = self._get_login_membership(session=session, user=user)
        audit.log(
            action="auth.verify_email",
            entity_type="user",
            entity_id=str(user.id),
            tenant_id=organization.id,
            actor_user_id=user.id,
        )
        bundle = self._issue_session(
            session=session,
            user=user,
            organization=organization,
            membership=membership,
        )
        session.commit()
        return bundle

    def resend_otp(
        self,
        *,
        session: Session,
        email: str,
        purpose: AuthOtpPurpose,
    ) -> None:
        normalized_email = _normalize_email(email)
        user = session.scalars(select(User).where(User.email == normalized_email)).first()
        if user is None:
            return
        if purpose == AuthOtpPurpose.EMAIL_VERIFICATION and user.email_verified_at is not None:
            return
        if self._latest_active_otp(session=session, email=normalized_email, purpose=purpose):
            latest = self._latest_active_otp(
                session=session,
                email=normalized_email,
                purpose=purpose,
            )
            if latest is not None and _aware(latest.created_at) + timedelta(
                seconds=OTP_RESEND_COOLDOWN_SECONDS
            ) > _now():
                raise OtpRateLimitError("Please wait before requesting another code.")
        self._create_and_send_otp(
            session=session,
            user=user,
            email=normalized_email,
            purpose=purpose,
        )
        session.commit()

    def login(
        self,
        *,
        session: Session,
        email: str,
        password: str,
        organization_id: UUID | None,
        otp_code: str | None = None,
    ) -> AuthSessionBundle:
        audit = AuditLogger(session)
        normalized_email = _normalize_email(email)
        user = session.scalars(select(User).where(User.email == normalized_email)).first()
        if user is None or not verify_password(password, user.password_hash):
            raise AuthenticationError("Invalid email or password.")
        self._ensure_user_can_login(user)
        if user.email_verified_at is None or user.status == UserStatus.PENDING_VERIFICATION:
            raise EmailNotVerifiedError(
                "Your email is not verified. Verify your email or resend the code."
            )
        if user.two_factor_enabled:
            if not otp_code:
                raise AuthenticationError("Two-factor authentication code required.")
            if not user.two_factor_secret or not verify_totp_code(user.two_factor_secret, otp_code):
                raise AuthenticationError("Invalid two-factor authentication code.")

        organization, membership = self._get_login_membership(
            session=session,
            user=user,
            organization_id=organization_id,
        )
        audit.log(
            action="auth.login",
            entity_type="user",
            entity_id=str(user.id),
            tenant_id=organization.id,
            actor_user_id=user.id,
        )
        bundle = self._issue_session(
            session=session,
            user=user,
            organization=organization,
            membership=membership,
        )
        session.commit()
        return bundle

    def google_login(self, *, session: Session, id_token: str) -> AuthSessionBundle:
        profile = verify_google_id_token(id_token)
        audit = AuditLogger(session)
        now = _now()
        oauth_account = session.scalars(
            select(OAuthAccount).where(
                OAuthAccount.provider == OAuthProvider.GOOGLE,
                OAuthAccount.provider_user_id == profile.provider_user_id,
            )
        ).first()

        if oauth_account is not None:
            user = session.get(User, oauth_account.user_id)
            if user is None:
                raise AuthenticationError("Google account link is invalid.")
            self._ensure_user_can_login(user)
        else:
            user = session.scalars(select(User).where(User.email == profile.email)).first()
            if user is None:
                user = User(
                    email=profile.email,
                    password_hash=None,
                    full_name=profile.full_name,
                    avatar_url=profile.avatar_url,
                    status=UserStatus.ACTIVE,
                    is_active=True,
                    email_verified_at=now,
                    auth_provider_primary=AuthProviderPrimary.GOOGLE,
                )
                organization = Organization(
                    name=f"{profile.full_name or profile.email} Workspace",
                    slug=self._resolve_organization_slug(
                        session=session,
                        organization_name=profile.full_name or profile.email,
                        requested_slug=None,
                    ),
                )
                session.add_all([organization, user])
                session.flush()
                session.add(
                    Membership(
                        organization_id=organization.id,
                        user_id=user.id,
                        role=MembershipRole.OWNER,
                    )
                )
                session.flush()
            else:
                self._ensure_user_can_login(user)
                user.auth_provider_primary = (
                    AuthProviderPrimary.MIXED
                    if user.password_hash
                    else AuthProviderPrimary.GOOGLE
                )
                user.email_verified_at = user.email_verified_at or now
                user.status = UserStatus.ACTIVE

            oauth_account = OAuthAccount(
                user_id=user.id,
                provider=OAuthProvider.GOOGLE,
                provider_user_id=profile.provider_user_id,
                provider_email=profile.email,
                email_verified=profile.email_verified,
                raw_profile_json=profile.raw_profile,
                linked_at=now,
            )
            session.add(oauth_account)

        user.full_name = user.full_name or profile.full_name
        user.avatar_url = profile.avatar_url or user.avatar_url
        user.email_verified_at = user.email_verified_at or now
        user.status = UserStatus.ACTIVE
        oauth_account.last_login_at = now
        oauth_account.provider_email = profile.email
        oauth_account.email_verified = profile.email_verified
        oauth_account.raw_profile_json = profile.raw_profile
        session.add_all([user, oauth_account])

        organization, membership = self._get_login_membership(session=session, user=user)
        audit.log(
            action="auth.google_login",
            entity_type="user",
            entity_id=str(user.id),
            tenant_id=organization.id,
            actor_user_id=user.id,
        )
        bundle = self._issue_session(
            session=session,
            user=user,
            organization=organization,
            membership=membership,
        )
        session.commit()
        return bundle

    def refresh(self, *, session: Session, refresh_token: str) -> AuthSessionBundle:
        token_hash = hash_token(refresh_token)
        stored = session.scalars(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        ).first()
        if stored is None or stored.revoked_at is not None or _aware(stored.expires_at) <= _now():
            raise AuthenticationError("Invalid or expired refresh token.")

        user = session.get(User, stored.user_id)
        if user is None:
            raise AuthenticationError("Invalid refresh token.")
        self._ensure_user_can_login(user)
        stored.revoked_at = _now()
        session.add(stored)

        organization, membership = self._get_login_membership(
            session=session,
            user=user,
            organization_id=stored.tenant_id,
        )
        bundle = self._issue_session(
            session=session,
            user=user,
            organization=organization,
            membership=membership,
        )
        session.commit()
        return bundle

    def logout(
        self,
        *,
        session: Session,
        user_id: UUID,
        tenant_id: UUID,
        jti: str,
        expires_at: datetime,
        refresh_token: str | None,
    ) -> None:
        audit = AuditLogger(session)
        revoked = RevokedToken(user_id=user_id, tenant_id=tenant_id, jti=jti, expires_at=expires_at)
        session.add(revoked)
        if refresh_token:
            stored_refresh = session.scalars(
                select(RefreshToken).where(RefreshToken.token_hash == hash_token(refresh_token))
            ).first()
            if stored_refresh is not None and stored_refresh.revoked_at is None:
                stored_refresh.revoked_at = _now()
                session.add(stored_refresh)
        audit.log(
            action="auth.logout",
            entity_type="token",
            entity_id=jti,
            tenant_id=tenant_id,
            actor_user_id=user_id,
        )
        session.commit()

    def forgot_password(self, *, session: Session, email: str) -> None:
        normalized_email = _normalize_email(email)
        user = session.scalars(select(User).where(User.email == normalized_email)).first()
        if user is None or user.status == UserStatus.DISABLED or not user.is_active:
            return
        self._create_and_send_otp(
            session=session,
            user=user,
            email=normalized_email,
            purpose=AuthOtpPurpose.PASSWORD_RESET,
        )
        session.commit()

    def reset_password(
        self,
        *,
        session: Session,
        email: str,
        otp: str,
        new_password: str,
    ) -> None:
        normalized_email = _normalize_email(email)
        user = self._get_user_by_email(session=session, email=normalized_email)
        self._ensure_user_not_disabled(user)
        try:
            validate_password_policy(new_password)
        except ValueError as error:
            raise AuthenticationError(str(error)) from error
        self._verify_otp(
            session=session,
            email=normalized_email,
            purpose=AuthOtpPurpose.PASSWORD_RESET,
            otp=otp,
        )
        user.password_hash = hash_password(new_password)
        user.email_verified_at = user.email_verified_at or _now()
        user.status = UserStatus.ACTIVE
        user.is_active = True
        if user.auth_provider_primary == AuthProviderPrimary.GOOGLE:
            user.auth_provider_primary = AuthProviderPrimary.MIXED
        session.add(user)

        active_refresh_tokens = session.scalars(
            select(RefreshToken).where(
                RefreshToken.user_id == user.id,
                RefreshToken.revoked_at.is_(None),
            )
        ).all()
        for token in active_refresh_tokens:
            token.revoked_at = _now()
            session.add(token)
        session.commit()

    def _resolve_organization_slug(
        self,
        *,
        session: Session,
        organization_name: str,
        requested_slug: str | None,
    ) -> str:
        base_slug = slugify_organization(requested_slug or organization_name)
        if requested_slug is not None:
            exists = session.scalars(
                select(Organization).where(Organization.slug == base_slug)
            ).first()
            if exists is not None:
                raise AuthenticationError("That organization slug is already in use.")
            return base_slug

        slug = base_slug
        suffix = 2
        while session.scalars(select(Organization).where(Organization.slug == slug)).first():
            slug = f"{base_slug[:110]}-{suffix}"
            suffix += 1
        return slug

    def _create_and_send_otp(
        self,
        *,
        session: Session,
        user: User,
        email: str,
        purpose: AuthOtpPurpose,
    ) -> None:
        now = _now()
        active_codes = session.scalars(
            select(AuthOtp).where(
                AuthOtp.email == email,
                AuthOtp.purpose == purpose,
                AuthOtp.consumed_at.is_(None),
            )
        ).all()
        for otp_record in active_codes:
            otp_record.consumed_at = now
            session.add(otp_record)

        otp_code = generate_otp_code()
        session.add(
            AuthOtp(
                user_id=user.id,
                email=email,
                purpose=purpose,
                otp_hash=hash_password(otp_code),
                expires_at=now + timedelta(minutes=OTP_EXPIRES_MINUTES),
                attempts=0,
                max_attempts=5,
            )
        )
        send_auth_otp_email(email=email, otp_code=otp_code, purpose=purpose)

    def _verify_otp(
        self,
        *,
        session: Session,
        email: str,
        purpose: AuthOtpPurpose,
        otp: str,
    ) -> AuthOtp:
        otp_record = self._latest_active_otp(session=session, email=email, purpose=purpose)
        if otp_record is None:
            raise AuthenticationError("This code has expired. Request a new code.")
        if _aware(otp_record.expires_at) <= _now():
            otp_record.consumed_at = _now()
            session.add(otp_record)
            session.commit()
            raise AuthenticationError("This code has expired. Request a new code.")
        if otp_record.attempts >= otp_record.max_attempts:
            otp_record.consumed_at = _now()
            session.add(otp_record)
            session.commit()
            raise AuthenticationError("Too many invalid code attempts. Request a new code.")
        if not verify_password(otp, otp_record.otp_hash):
            otp_record.attempts += 1
            if otp_record.attempts >= otp_record.max_attempts:
                otp_record.consumed_at = _now()
            session.add(otp_record)
            session.commit()
            raise AuthenticationError("Invalid verification code.")

        otp_record.consumed_at = _now()
        session.add(otp_record)
        return otp_record

    def _latest_active_otp(
        self,
        *,
        session: Session,
        email: str,
        purpose: AuthOtpPurpose,
    ) -> AuthOtp | None:
        return session.scalars(
            select(AuthOtp)
            .where(
                AuthOtp.email == email,
                AuthOtp.purpose == purpose,
                AuthOtp.consumed_at.is_(None),
            )
            .order_by(AuthOtp.created_at.desc())
        ).first()

    def _issue_session(
        self,
        *,
        session: Session,
        user: User,
        organization: Organization,
        membership: Membership,
    ) -> AuthSessionBundle:
        settings = get_settings()
        raw_refresh_token = generate_refresh_token()
        refresh_expires_at = _now() + timedelta(days=settings.refresh_token_ttl_days)
        session.add(
            RefreshToken(
                user_id=user.id,
                tenant_id=organization.id,
                token_hash=hash_token(raw_refresh_token),
                expires_at=refresh_expires_at,
            )
        )
        return AuthSessionBundle(
            auth_response=build_auth_response(
                user=user,
                organization=organization,
                membership=membership,
                refresh_expires_at=refresh_expires_at,
            ),
            refresh_token=raw_refresh_token,
        )

    def _get_user_by_email(self, *, session: Session, email: str) -> User:
        user = session.scalars(select(User).where(User.email == email)).first()
        if user is None:
            raise AuthenticationError("Invalid account or verification code.")
        return user

    def _ensure_user_not_disabled(self, user: User) -> None:
        if not user.is_active or user.status == UserStatus.DISABLED:
            raise DisabledUserError("This account is disabled.")

    def _ensure_user_can_login(self, user: User) -> None:
        self._ensure_user_not_disabled(user)

    def _get_login_membership(
        self,
        *,
        session: Session,
        user: User,
        organization_id: UUID | None = None,
    ) -> tuple[Organization, Membership]:
        membership_query = select(Membership).where(Membership.user_id == user.id)
        if organization_id is not None:
            membership_query = membership_query.where(Membership.organization_id == organization_id)

        membership = session.scalars(membership_query).first()
        if membership is None:
            raise AuthenticationError("No organization membership is available for that login.")

        organization = session.get(Organization, membership.organization_id)
        if organization is None:
            raise AuthenticationError("Organization membership is invalid.")
        return organization, membership
