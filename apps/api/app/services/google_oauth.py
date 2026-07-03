from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import jwt

from app.core.settings import get_settings

GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}


class GoogleOAuthError(ValueError):
    """Raised when a Google login token is missing, disabled, or invalid."""


@dataclass(slots=True)
class GoogleProfile:
    provider_user_id: str
    email: str
    email_verified: bool
    full_name: str | None
    avatar_url: str | None
    raw_profile: dict[str, Any]


def verify_google_id_token(id_token: str) -> GoogleProfile:
    settings = get_settings()
    if not settings.enable_google_login or not settings.google_client_id:
        raise GoogleOAuthError("Google login is not configured yet.")

    try:
        signing_key = jwt.PyJWKClient(GOOGLE_JWKS_URL).get_signing_key_from_jwt(id_token)
        payload = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.google_client_id,
            options={"require": ["exp", "iss", "aud", "sub", "email"]},
        )
    except jwt.PyJWTError as error:
        raise GoogleOAuthError("Google login could not be verified.") from error

    if payload.get("iss") not in GOOGLE_ISSUERS:
        raise GoogleOAuthError("Google login could not be verified.")

    email = str(payload.get("email") or "").strip().lower()
    email_verified = payload.get("email_verified") is True
    if not email or not email_verified:
        raise GoogleOAuthError("Google account email is not verified.")

    return GoogleProfile(
        provider_user_id=str(payload["sub"]),
        email=email,
        email_verified=email_verified,
        full_name=str(payload["name"]) if payload.get("name") else None,
        avatar_url=str(payload["picture"]) if payload.get("picture") else None,
        raw_profile=dict(payload),
    )
