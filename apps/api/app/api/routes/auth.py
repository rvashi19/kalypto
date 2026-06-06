from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import AuthProviderDep, CurrentUser, DbSession
from app.schemas.auth import (
    AuthResponse,
    CurrentUserResponse,
    LoginRequest,
    LogoutResponse,
    MembershipSummary,
    OrganizationSummary,
    RegisterRequest,
    UserSummary,
)
from app.services.auth_provider import AuthenticationError
from app.services.rate_limit import rate_limit_auth_requests

router = APIRouter(prefix="/auth", tags=["auth"], dependencies=[Depends(rate_limit_auth_requests)])


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    session: DbSession,
    auth_provider: AuthProviderDep,
) -> AuthResponse:
    try:
        return auth_provider.register(
            session=session,
            email=payload.email,
            password=payload.password,
            organization_name=payload.organization_name,
            organization_slug=payload.organization_slug,
            full_name=payload.full_name,
        )
    except AuthenticationError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.post("/login", response_model=AuthResponse)
def login(
    payload: LoginRequest,
    session: DbSession,
    auth_provider: AuthProviderDep,
) -> AuthResponse:
    try:
        return auth_provider.login(
            session=session,
            email=payload.email,
            password=payload.password,
            organization_id=payload.organization_id,
        )
    except AuthenticationError as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error)) from error


@router.post("/logout", response_model=LogoutResponse)
def logout(
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
    return LogoutResponse(success=True)


@router.get("/me", response_model=CurrentUserResponse)
def get_current_user(current_user: CurrentUser) -> CurrentUserResponse:
    return CurrentUserResponse(
        user=UserSummary(
            id=current_user.user.id,
            email=current_user.user.email,
            full_name=current_user.user.full_name,
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
