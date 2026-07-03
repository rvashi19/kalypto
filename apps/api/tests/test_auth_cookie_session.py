from fastapi.testclient import TestClient

from app.core.settings import get_settings
from app.main import app
from app.services import auth_provider as auth_provider_module


def test_verification_sets_http_only_cookie_and_cookie_auth_works(monkeypatch) -> None:
    client = TestClient(app)
    settings = get_settings()
    sent_codes: list[str] = []

    def fake_send_auth_otp_email(*, email: str, otp_code: str, purpose) -> None:
        sent_codes.append(otp_code)

    monkeypatch.setattr(auth_provider_module, "send_auth_otp_email", fake_send_auth_otp_email)

    registered = client.post(
        "/api/v1/auth/register",
        json={
            "email": "cookie-session@example.com",
            "password": "StrongPassword123!",
            "full_name": "Cookie Owner",
            "company_name": "Cookie Session Exports",
        },
    )

    assert registered.status_code == 201
    verified = client.post(
        "/api/v1/auth/verify-email-otp",
        json={"email": "cookie-session@example.com", "otp": sent_codes[0]},
    )
    assert verified.status_code == 200
    set_cookie = verified.headers["set-cookie"]
    assert f"{settings.auth_cookie_name}=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "SameSite=lax" in set_cookie

    current_user = client.get("/api/v1/auth/me")
    assert current_user.status_code == 200
    assert current_user.json()["user"]["email"] == "cookie-session@example.com"

    logged_out = client.post("/api/v1/auth/logout")
    assert logged_out.status_code == 200
    assert f"{settings.auth_cookie_name}=" in logged_out.headers["set-cookie"]
    assert "Max-Age=0" in logged_out.headers["set-cookie"]

    after_logout = client.get("/api/v1/auth/me")
    assert after_logout.status_code == 401
