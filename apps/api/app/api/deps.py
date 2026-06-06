from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import TokenPayload, decode_access_token
from app.db.session import get_db_session
from app.models import Membership, Organization, RevokedToken, User
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
    session: Annotated[Session, Depends(get_db_session)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> CurrentUserContext:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated.")

    try:
        token = decode_access_token(credentials.credentials)
    except Exception as error:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
        ) from error

    revoked_token = session.scalars(select(RevokedToken).where(RevokedToken.jti == token.jti)).first()
    if revoked_token is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked.")

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

    return CurrentUserContext(user=user, organization=organization, membership=membership, token=token)


DbSession = Annotated[Session, Depends(get_db_session)]
CurrentUser = Annotated[CurrentUserContext, Depends(get_current_user_context)]
AuthProviderDep = Annotated[AuthProvider, Depends(get_auth_provider)]
