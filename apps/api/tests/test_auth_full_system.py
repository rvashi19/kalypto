from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import hash_password, verify_password
from app.core.settings import get_settings
from app.main import app
from app.models import (
    AuthOtp,
    AuthOtpPurpose,
    Membership,
    MembershipRole,
    OAuthAccount,
    Organization,
    RefreshToken,
    User,
    UserStatus,
)
from app.services import auth_provider as auth_provider_module
from app.services.google_oauth import GoogleProfile


def _email(prefix: str = "auth") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}@example.com"


def _install_email_capture(monkeypatch):
    sent: list[tuple[str, str, AuthOtpPurpose]] = []

    def fake_send_auth_otp_email(*, email: str, otp_code: str, purpose: AuthOtpPurpose) -> None:
        sent.append((email, otp_code, purpose))

    monkeypatch.setattr(auth_provider_module, "send_auth_otp_email", fake_send_auth_otp_email)
    return sent


def _register(client: TestClient, email: str) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Auth Owner",
            "email": email,
            "password": "StrongPassword123!",
            "company_name": "Auth Exports",
            "country": "India",
        },
    )
    assert response.status_code == 201, response.text


def _create_verified_user(session, email: str, password: str = "StrongPassword123!") -> User:
    organization = Organization(
        name=f"Org {uuid.uuid4().hex[:8]}",
        slug=f"org-{uuid.uuid4().hex[:8]}",
    )
    user = User(
        email=email,
        password_hash=hash_password(password),
        full_name="Verified Owner",
        email_verified_at=datetime.now(UTC),
        status=UserStatus.ACTIVE,
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
    session.commit()
    return user


def test_register_creates_pending_user_hashed_otp_and_sends_email(session, monkeypatch) -> None:
    client = TestClient(app)
    sent = _install_email_capture(monkeypatch)
    email = _email("pending")

    _register(client, email)

    user = session.scalars(select(User).where(User.email == email)).one()
    otp = session.scalars(select(AuthOtp).where(AuthOtp.email == email)).one()
    assert user.status == UserStatus.PENDING_VERIFICATION
    assert user.email_verified_at is None
    assert otp.otp_hash != sent[0][1]
    assert verify_password(sent[0][1], otp.otp_hash)
    assert sent == [(email, sent[0][1], AuthOtpPurpose.EMAIL_VERIFICATION)]


def test_verify_otp_activates_user_and_sets_cookies(session, monkeypatch) -> None:
    client = TestClient(app)
    sent = _install_email_capture(monkeypatch)
    settings = get_settings()
    email = _email("verify")
    _register(client, email)

    response = client.post(
        "/api/v1/auth/verify-email-otp",
        json={"email": email, "otp": sent[0][1]},
    )

    assert response.status_code == 200, response.text
    assert settings.auth_cookie_name in response.headers["set-cookie"]
    assert settings.refresh_cookie_name in response.headers["set-cookie"]
    user = session.scalars(select(User).where(User.email == email)).one()
    assert user.status == UserStatus.ACTIVE
    assert user.email_verified_at is not None


def test_wrong_otp_increments_attempts(session, monkeypatch) -> None:
    client = TestClient(app)
    _install_email_capture(monkeypatch)
    email = _email("wrong")
    _register(client, email)

    response = client.post(
        "/api/v1/auth/verify-email-otp",
        json={"email": email, "otp": "000000"},
    )

    assert response.status_code == 400
    otp = session.scalars(select(AuthOtp).where(AuthOtp.email == email)).one()
    assert otp.attempts == 1


def test_expired_otp_is_rejected(session, monkeypatch) -> None:
    client = TestClient(app)
    sent = _install_email_capture(monkeypatch)
    email = _email("expired")
    _register(client, email)
    otp = session.scalars(select(AuthOtp).where(AuthOtp.email == email)).one()
    otp.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    session.commit()

    response = client.post(
        "/api/v1/auth/verify-email-otp",
        json={"email": email, "otp": sent[0][1]},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "This code has expired. Request a new code."


def test_resend_otp_expires_old_otp(session, monkeypatch) -> None:
    client = TestClient(app)
    sent = _install_email_capture(monkeypatch)
    email = _email("resend")
    _register(client, email)
    first = session.scalars(select(AuthOtp).where(AuthOtp.email == email)).one()
    first.created_at = datetime.now(UTC) - timedelta(seconds=61)
    session.commit()

    response = client.post(
        "/api/v1/auth/resend-otp",
        json={"email": email, "purpose": "email_verification"},
    )

    assert response.status_code == 200
    otps = session.scalars(select(AuthOtp).where(AuthOtp.email == email)).all()
    assert len(otps) == 2
    assert any(record.consumed_at is not None for record in otps)
    assert len(sent) == 2


def test_login_rejects_unverified_user(monkeypatch) -> None:
    client = TestClient(app)
    _install_email_capture(monkeypatch)
    email = _email("unverified")
    _register(client, email)

    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "StrongPassword123!"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Your email is not verified. Verify your email or resend the code."
    )


def test_login_succeeds_for_verified_user(session) -> None:
    client = TestClient(app)
    email = _email("login")
    _create_verified_user(session, email)

    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "StrongPassword123!"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["user"]["email"] == email
    assert get_settings().auth_cookie_name in response.headers["set-cookie"]


def test_google_oauth_creates_user_with_mocked_provider(session, monkeypatch) -> None:
    client = TestClient(app)
    profile = GoogleProfile(
        provider_user_id="google-user-1",
        email=_email("google"),
        email_verified=True,
        full_name="Google Owner",
        avatar_url="https://example.com/avatar.png",
        raw_profile={"sub": "google-user-1"},
    )
    monkeypatch.setattr(auth_provider_module, "verify_google_id_token", lambda _token: profile)

    response = client.post("/api/v1/auth/oauth/google", json={"id_token": "x" * 32})

    assert response.status_code == 200, response.text
    user = session.scalars(select(User).where(User.email == profile.email)).one()
    account = session.scalars(select(OAuthAccount).where(OAuthAccount.user_id == user.id)).one()
    assert user.email_verified_at is not None
    assert account.provider_user_id == "google-user-1"


def test_google_oauth_disabled_returns_clear_response(monkeypatch) -> None:
    client = TestClient(app)
    monkeypatch.setattr(get_settings(), "enable_google_login", False)
    monkeypatch.setattr(get_settings(), "google_client_id", None)

    response = client.post("/api/v1/auth/oauth/google", json={"id_token": "x" * 32})

    assert response.status_code == 503
    assert response.json()["detail"] == "Google login is not configured yet."


def test_refresh_token_rotates_and_issues_new_access(session) -> None:
    client = TestClient(app)
    email = _email("refresh")
    _create_verified_user(session, email)
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "StrongPassword123!"},
    )
    assert login.status_code == 200

    response = client.post("/api/v1/auth/refresh")

    assert response.status_code == 200, response.text
    tokens = session.scalars(select(RefreshToken)).all()
    assert len(tokens) == 2
    assert sum(token.revoked_at is not None for token in tokens) == 1


def test_logout_revokes_refresh_token(session) -> None:
    client = TestClient(app)
    email = _email("logout")
    _create_verified_user(session, email)
    assert client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "StrongPassword123!"},
    ).status_code == 200

    response = client.post("/api/v1/auth/logout")

    assert response.status_code == 200
    token = session.scalars(select(RefreshToken)).one()
    assert token.revoked_at is not None


def test_forgot_password_returns_generic_response(monkeypatch) -> None:
    client = TestClient(app)
    sent = _install_email_capture(monkeypatch)

    response = client.post("/api/v1/auth/forgot-password", json={"email": _email("missing")})

    assert response.status_code == 200
    assert response.json()["message"] == (
        "If an account exists for this email, a reset code has been sent."
    )
    assert sent == []


def test_reset_password_updates_password_and_revokes_refresh_tokens(session, monkeypatch) -> None:
    client = TestClient(app)
    sent = _install_email_capture(monkeypatch)
    email = _email("reset")
    user = _create_verified_user(session, email)
    assert client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "StrongPassword123!"},
    ).status_code == 200
    assert session.scalars(select(RefreshToken).where(RefreshToken.user_id == user.id)).one()

    forgot = client.post("/api/v1/auth/forgot-password", json={"email": email})
    assert forgot.status_code == 200
    reset_code = sent[-1][1]
    response = client.post(
        "/api/v1/auth/reset-password",
        json={
            "email": email,
            "otp": reset_code,
            "new_password": "NewStrongPassword123!",
        },
    )

    assert response.status_code == 200, response.text
    session.refresh(user)
    assert verify_password("NewStrongPassword123!", user.password_hash)
    tokens = session.scalars(select(RefreshToken).where(RefreshToken.user_id == user.id)).all()
    assert tokens
    assert all(token.revoked_at is not None for token in tokens)
