from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.api.deps import AuthProviderDep, CurrentUser, DbSession
from app.core.security import generate_totp_secret, totp_otpauth_uri, verify_totp_code
from app.core.settings import get_settings
from app.schemas.auth import (
    AuthResponse,
    CurrentUserResponse,
    LoginRequest,
    LogoutResponse,
    MembershipSummary,
    OrganizationSummary,
    RegisterRequest,
    TwoFactorEnableRequest,
    TwoFactorSetupResponse,
    UserSummary,
)
from app.services.auth_provider import AuthenticationError
from app.services.rate_limit import rate_limit_auth_identity, rate_limit_auth_requests

router = APIRouter(prefix="/auth", tags=["auth"], dependencies=[Depends(rate_limit_auth_requests)])


def _set_session_cookie(response: Response, auth_response: AuthResponse) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=auth_response.access_token,
        max_age=settings.access_token_ttl_minutes * 60,
        httponly=True,
        secure=settings.environment.lower() == "production",
        samesite=settings.auth_cookie_samesite,
        path="/",
        domain=settings.auth_cookie_domain,
    )


def _clear_session_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        key=settings.auth_cookie_name,
        path="/",
        domain=settings.auth_cookie_domain,
        secure=settings.environment.lower() == "production",
        samesite=settings.auth_cookie_samesite,
    )


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    session: DbSession,
    auth_provider: AuthProviderDep,
) -> AuthResponse:
    rate_limit_auth_identity(request=request, email=payload.email)
    try:
        auth_response = auth_provider.register(
            session=session,
            email=payload.email,
            password=payload.password,
            organization_name=payload.organization_name,
            organization_slug=payload.organization_slug,
            full_name=payload.full_name,
        )
        _set_session_cookie(response, auth_response)
        return auth_response
    except AuthenticationError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


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
        auth_response = auth_provider.login(
            session=session,
            email=payload.email,
            password=payload.password,
            organization_id=payload.organization_id,
            otp_code=payload.otp_code,
        )
        _set_session_cookie(response, auth_response)
        return auth_response
    except AuthenticationError as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error)) from error


@router.post("/logout", response_model=LogoutResponse)
def logout(
    response: Response,
    session: DbSession,
    current_user: CurrentUser,
    auth_provider: AuthProviderDep,
) -> LogoutResponse:
    auth_provider.logout(
        session=session,
        user_id=current_user.user.id,
        tenant_id=current_user.organization.id,
        jti=current_user.token.jti,
        expires_at=current_user.token.exp,
    )
    _clear_session_cookie(response)
    return LogoutResponse(success=True)


@router.get("/me", response_model=CurrentUserResponse)
def get_current_user(current_user: CurrentUser) -> CurrentUserResponse:
    return CurrentUserResponse(
        user=UserSummary(
            id=current_user.user.id,
            email=current_user.user.email,
            full_name=current_user.user.full_name,
            email_verified_at=current_user.user.email_verified_at,
            two_factor_enabled=current_user.user.two_factor_enabled,
        ),
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
    return get_current_user(current_user)


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
    return get_current_user(current_user)
