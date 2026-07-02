from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from time import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
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


def validate_password_policy(password: str) -> None:
    errors: list[str] = []
    if len(password) < 12:
        errors.append("at least 12 characters")
    if not any(character.islower() for character in password):
        errors.append("a lowercase letter")
    if not any(character.isupper() for character in password):
        errors.append("an uppercase letter")
    if not any(character.isdigit() for character in password):
        errors.append("a number")
    if not any(not character.isalnum() for character in password):
        errors.append("a symbol")

    normalized = password.lower()
    common_breached_passwords = {
        "password123!",
        "password1234!",
        "qwerty123456!",
        "letmein12345!",
        "adminpassword1!",
        "welcome12345!",
    }
    if normalized in common_breached_passwords:
        errors.append("a password that is not known to be commonly breached")

    settings = get_settings()
    if settings.password_breach_check_enabled and _password_seen_in_breach_corpus(password):
        errors.append("a password that has not appeared in known breach corpuses")

    if errors:
        raise ValueError("Password must include " + ", ".join(errors) + ".")


def _password_seen_in_breach_corpus(password: str) -> bool:
    password_hash = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()
    prefix = password_hash[:5]
    suffix = password_hash[5:]
    request = Request(
        f"https://api.pwnedpasswords.com/range/{prefix}",
        headers={"User-Agent": "ExportPilotAI password breach check"},
    )
    try:
        with urlopen(request, timeout=2) as response:
            body = response.read().decode("utf-8")
    except (HTTPError, URLError, TimeoutError) as error:
        raise ValueError("Password breach check is temporarily unavailable.") from error

    for line in body.splitlines():
        candidate, _, count = line.partition(":")
        if candidate == suffix and int(count or "0") > 0:
            return True
    return False


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


def generate_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def totp_otpauth_uri(*, secret: str, email: str, issuer: str = "ExportPilotAI") -> str:
    label = quote(f"{issuer}:{email}")
    issuer_name = quote(issuer)
    return f"otpauth://totp/{label}?secret={secret}&issuer={issuer_name}&algorithm=SHA1&digits=6&period=30"


def _totp_code(secret: str, *, for_time: float, period: int = 30, digits: int = 6) -> str:
    padded_secret = secret.upper() + ("=" * ((8 - len(secret) % 8) % 8))
    key = base64.b32decode(padded_secret.encode("ascii"), casefold=True)
    counter = int(for_time // period)
    digest = hmac.new(key, counter.to_bytes(8, "big"), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = int.from_bytes(digest[offset : offset + 4], "big") & 0x7FFFFFFF
    return str(code % (10**digits)).zfill(digits)


def verify_totp_code(secret: str, code: str, *, window: int = 1) -> bool:
    normalized = "".join(character for character in code if character.isdigit())
    if len(normalized) != 6:
        return False

    now = time()
    for offset in range(-window, window + 1):
        expected = _totp_code(secret, for_time=now + (offset * 30))
        if hmac.compare_digest(expected, normalized):
            return True
    return False
