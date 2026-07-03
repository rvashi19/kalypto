from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.api.deps import AuthProviderDep, CurrentUser, DbSession
from app.core.security import generate_totp_secret, totp_otpauth_uri, verify_totp_code
from app.core.settings import get_settings
from app.models import User
from app.schemas.auth import (
    AuthMessageResponse,
    AuthResponse,
    CurrentUserResponse,
    ForgotPasswordRequest,
    GoogleOAuthRequest,
    LoginRequest,
    LogoutResponse,
    MembershipSummary,
    OrganizationSummary,
    RegisterRequest,
    RegisterResponse,
    ResendOtpRequest,
    ResetPasswordRequest,
    TwoFactorEnableRequest,
    TwoFactorSetupResponse,
    UserSummary,
    VerifyEmailOtpRequest,
)
from app.services.auth_provider import (
    AuthenticationError,
    DisabledUserError,
    EmailNotVerifiedError,
    OtpRateLimitError,
)
from app.services.email import EmailDeliveryError
from app.services.google_oauth import GoogleOAuthError
from app.services.rate_limit import rate_limit_auth_identity, rate_limit_auth_requests

router = APIRouter(prefix="/auth", tags=["auth"], dependencies=[Depends(rate_limit_auth_requests)])


def _cookie_secure() -> bool:
    return get_settings().environment.lower() == "production"


def _set_session_cookies(
    response: Response,
    auth_response: AuthResponse,
    refresh_token: str,
) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=auth_response.access_token,
        max_age=settings.access_token_ttl_minutes * 60,
        httponly=True,
        secure=_cookie_secure(),
        samesite=settings.auth_cookie_samesite,
        path="/",
        domain=settings.auth_cookie_domain,
    )
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=refresh_token,
        max_age=settings.refresh_token_ttl_days * 24 * 60 * 60,
        httponly=True,
        secure=_cookie_secure(),
        samesite=settings.auth_cookie_samesite,
        path="/api/v1/auth",
        domain=settings.auth_cookie_domain,
    )


def _clear_session_cookies(response: Response) -> None:
    settings = get_settings()
    cookie_args = {
        "domain": settings.auth_cookie_domain,
        "secure": _cookie_secure(),
        "samesite": settings.auth_cookie_samesite,
    }
    response.delete_cookie(key=settings.auth_cookie_name, path="/", **cookie_args)
    response.delete_cookie(key=settings.refresh_cookie_name, path="/api/v1/auth", **cookie_args)


def _user_summary(user: User) -> UserSummary:
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


def _current_user_response(current_user: CurrentUser) -> CurrentUserResponse:
    return CurrentUserResponse(
        user=_user_summary(current_user.user),
        organization=OrganizationSummary(
            id=current_user.organization.id,
            name=current_user.organization.name,
            slug=current_user.organization.slug,
        ),
        membership=MembershipSummary(
            organization_id=current_user.organization.id,
            role=current_user.membership.role,
        ),
    )


def _raise_auth_error(error: Exception, *, default_status: int) -> None:
    if isinstance(error, OtpRateLimitError):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(error))
    if isinstance(error, EmailNotVerifiedError | DisabledUserError):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error))
    if isinstance(error, EmailDeliveryError):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error))
    if isinstance(error, GoogleOAuthError) and str(error) == "Google login is not configured yet.":
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error))
    raise HTTPException(status_code=default_status, detail=str(error))


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    request: Request,
    session: DbSession,
    auth_provider: AuthProviderDep,
) -> RegisterResponse:
    rate_limit_auth_identity(request=request, email=payload.email)
    try:
        result = auth_provider.register(
            session=session,
            email=payload.email,
            password=payload.password,
            full_name=payload.full_name,
            organization_name=payload.organization_name,
            organization_slug=payload.organization_slug,
            company_name=payload.company_name,
            country=payload.country,
        )
        return RegisterResponse(
            message=result.message,
            email=result.email,
            verification_required=True,
        )
    except (AuthenticationError, EmailDeliveryError) as error:
        _raise_auth_error(error, default_status=status.HTTP_400_BAD_REQUEST)


@router.post("/verify-email-otp", response_model=AuthResponse)
def verify_email_otp(
    payload: VerifyEmailOtpRequest,
    request: Request,
    response: Response,
    session: DbSession,
    auth_provider: AuthProviderDep,
) -> AuthResponse:
    rate_limit_auth_identity(request=request, email=payload.email)
    try:
        bundle = auth_provider.verify_email_otp(
            session=session,
            email=payload.email,
            otp=payload.otp,
        )
        _set_session_cookies(response, bundle.auth_response, bundle.refresh_token)
        return bundle.auth_response
    except AuthenticationError as error:
        _raise_auth_error(error, default_status=status.HTTP_400_BAD_REQUEST)


@router.post("/resend-otp", response_model=AuthMessageResponse)
def resend_otp(
    payload: ResendOtpRequest,
    request: Request,
    session: DbSession,
    auth_provider: AuthProviderDep,
) -> AuthMessageResponse:
    rate_limit_auth_identity(request=request, email=payload.email)
    try:
        auth_provider.resend_otp(
            session=session,
            email=payload.email,
            purpose=payload.purpose,
        )
        return AuthMessageResponse(
            message="If this account can receive codes, a new code has been sent."
        )
    except (AuthenticationError, EmailDeliveryError) as error:
        _raise_auth_error(error, default_status=status.HTTP_400_BAD_REQUEST)


@router.post("/login", response_model=AuthResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: DbSession,
    auth_provider: AuthProviderDep,
) -> AuthResponse:
    rate_limit_auth_identity(request=request, email=payload.email)
    try:
        bundle = auth_provider.login(
            session=session,
            email=payload.email,
            password=payload.password,
            organization_id=payload.organization_id,
            otp_code=payload.otp_code,
        )
        _set_session_cookies(response, bundle.auth_response, bundle.refresh_token)
        return bundle.auth_response
    except AuthenticationError as error:
        _raise_auth_error(error, default_status=status.HTTP_401_UNAUTHORIZED)


@router.post("/oauth/google", response_model=AuthResponse)
def google_login(
    payload: GoogleOAuthRequest,
    request: Request,
    response: Response,
    session: DbSession,
    auth_provider: AuthProviderDep,
) -> AuthResponse:
    rate_limit_auth_identity(request=request, email="google")
    try:
        bundle = auth_provider.google_login(session=session, id_token=payload.id_token)
        _set_session_cookies(response, bundle.auth_response, bundle.refresh_token)
        return bundle.auth_response
    except (AuthenticationError, GoogleOAuthError) as error:
        _raise_auth_error(error, default_status=status.HTTP_401_UNAUTHORIZED)


@router.post("/refresh", response_model=AuthResponse)
def refresh(
    request: Request,
    response: Response,
    session: DbSession,
    auth_provider: AuthProviderDep,
) -> AuthResponse:
    settings = get_settings()
    refresh_token = request.cookies.get(settings.refresh_cookie_name)
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated.")
    try:
        bundle = auth_provider.refresh(session=session, refresh_token=refresh_token)
        _set_session_cookies(response, bundle.auth_response, bundle.refresh_token)
        return bundle.auth_response
    except AuthenticationError as error:
        _clear_session_cookies(response)
        _raise_auth_error(error, default_status=status.HTTP_401_UNAUTHORIZED)


@router.post("/logout", response_model=LogoutResponse)
def logout(
    request: Request,
    response: Response,
    session: DbSession,
    current_user: CurrentUser,
    auth_provider: AuthProviderDep,
) -> LogoutResponse:
    settings = get_settings()
    auth_provider.logout(
        session=session,
        user_id=current_user.user.id,
        tenant_id=current_user.organization.id,
        jti=current_user.token.jti,
        expires_at=current_user.token.exp,
        refresh_token=request.cookies.get(settings.refresh_cookie_name),
    )
    _clear_session_cookies(response)
    return LogoutResponse(success=True)


@router.post("/forgot-password", response_model=AuthMessageResponse)
def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    session: DbSession,
    auth_provider: AuthProviderDep,
) -> AuthMessageResponse:
    rate_limit_auth_identity(request=request, email=payload.email)
    try:
        auth_provider.forgot_password(session=session, email=payload.email)
        return AuthMessageResponse(
            message="If an account exists for this email, a reset code has been sent."
        )
    except EmailDeliveryError:
        return AuthMessageResponse(
            message="If an account exists for this email, a reset code has been sent."
        )


@router.post("/reset-password", response_model=AuthMessageResponse)
def reset_password(
    payload: ResetPasswordRequest,
    request: Request,
    session: DbSession,
    auth_provider: AuthProviderDep,
) -> AuthMessageResponse:
    rate_limit_auth_identity(request=request, email=payload.email)
    try:
        auth_provider.reset_password(
            session=session,
            email=payload.email,
            otp=payload.otp,
            new_password=payload.new_password,
        )
        return AuthMessageResponse(message="Your password has been reset. You can sign in now.")
    except AuthenticationError as error:
        _raise_auth_error(error, default_status=status.HTTP_400_BAD_REQUEST)


@router.get("/me", response_model=CurrentUserResponse)
def get_current_user(current_user: CurrentUser) -> CurrentUserResponse:
    return _current_user_response(current_user)


@router.get("/2fa/setup", response_model=TwoFactorSetupResponse)
def setup_two_factor(session: DbSession, current_user: CurrentUser) -> TwoFactorSetupResponse:
    if not current_user.user.two_factor_secret:
        current_user.user.two_factor_secret = generate_totp_secret()
        session.add(current_user.user)
        session.commit()
        session.refresh(current_user.user)

    return TwoFactorSetupResponse(
        secret=current_user.user.two_factor_secret,
        otpauth_uri=totp_otpauth_uri(
            secret=current_user.user.two_factor_secret,
            email=current_user.user.email,
        ),
    )


@router.post("/2fa/enable", response_model=CurrentUserResponse)
def enable_two_factor(
    payload: TwoFactorEnableRequest,
    session: DbSession,
    current_user: CurrentUser,
) -> CurrentUserResponse:
    if not current_user.user.two_factor_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Start two-factor setup before enabling it.",
        )
    if not verify_totp_code(current_user.user.two_factor_secret, payload.otp_code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid two-factor authentication code.",
        )

    current_user.user.two_factor_enabled = True
    session.add(current_user.user)
    session.commit()
    session.refresh(current_user.user)
    return _current_user_response(current_user)


@router.post("/2fa/disable", response_model=CurrentUserResponse)
def disable_two_factor(
    payload: TwoFactorEnableRequest,
    session: DbSession,
    current_user: CurrentUser,
) -> CurrentUserResponse:
    if current_user.user.two_factor_secret and not verify_totp_code(
        current_user.user.two_factor_secret,
        payload.otp_code,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid two-factor authentication code.",
        )

    current_user.user.two_factor_enabled = False
    current_user.user.two_factor_secret = None
    session.add(current_user.user)
    session.commit()
    session.refresh(current_user.user)
    return _current_user_response(current_user)
