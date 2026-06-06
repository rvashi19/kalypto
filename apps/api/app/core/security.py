from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt

from app.core.settings import get_settings


@dataclass(slots=True)
class TokenPayload:
    sub: UUID
    tenant_id: UUID
    role: str
    jti: str
    exp: datetime


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return f"{base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, password_hash: str) -> bool:
    encoded_salt, encoded_digest = password_hash.split("$", maxsplit=1)
    salt = base64.b64decode(encoded_salt.encode())
    expected_digest = base64.b64decode(encoded_digest.encode())
    actual_digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return hmac.compare_digest(actual_digest, expected_digest)


def create_access_token(*, user_id: UUID, tenant_id: UUID, role: str) -> tuple[str, datetime, str]:
    settings = get_settings()
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.access_token_ttl_minutes)
    jti = str(uuid4())
    token = jwt.encode(
        {
            "sub": str(user_id),
            "tenant_id": str(tenant_id),
            "role": role,
            "jti": jti,
            "exp": expires_at,
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return token, expires_at, jti


def decode_access_token(token: str) -> TokenPayload:
    settings = get_settings()
    payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    return TokenPayload(
        sub=UUID(payload["sub"]),
        tenant_id=UUID(payload["tenant_id"]),
        role=str(payload["role"]),
        jti=str(payload["jti"]),
        exp=datetime.fromtimestamp(payload["exp"], tz=UTC),
    )
