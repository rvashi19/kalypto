from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import TokenPayload, decode_access_token
from app.core.settings import get_settings
from app.db.session import get_db_session
from app.models import Membership, Organization, RevokedToken, User, UserStatus
from app.services.auth_provider import AuthProvider, LocalAuthProvider

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(slots=True)
class CurrentUserContext:
    user: User
    organization: Organization
    membership: Membership
    token: TokenPayload


def get_auth_provider() -> AuthProvider:
    return LocalAuthProvider()


def get_current_user_context(
    request: Request,
    session: Annotated[Session, Depends(get_db_session)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> CurrentUserContext:
    settings = get_settings()
    raw_token = request.cookies.get(settings.auth_cookie_name)
    if raw_token is None and credentials is not None:
        raw_token = credentials.credentials

    if raw_token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated.")

    try:
        token = decode_access_token(raw_token)
    except Exception as error:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
        ) from error

    revoked_token = session.scalars(
        select(RevokedToken).where(RevokedToken.jti == token.jti)
    ).first()
    if revoked_token is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked."
        )

    user = session.get(User, token.sub)
    organization = session.get(Organization, token.tenant_id)
    membership = session.scalars(
        select(Membership).where(
            Membership.user_id == token.sub,
            Membership.organization_id == token.tenant_id,
        ),
    ).first()

    if user is None or organization is None or membership is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The authenticated membership is no longer valid.",
        )
    if not user.is_active or user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is not active.",
        )

    return CurrentUserContext(
        user=user, organization=organization, membership=membership, token=token
    )


DbSession = Annotated[Session, Depends(get_db_session)]
CurrentUser = Annotated[CurrentUserContext, Depends(get_current_user_context)]
AuthProviderDep = Annotated[AuthProvider, Depends(get_auth_provider)]
