from fastapi.testclient import TestClient

from app.core.settings import get_settings
from app.main import app


def test_login_sets_http_only_cookie_and_cookie_auth_works() -> None:
    client = TestClient(app)
    settings = get_settings()

    registered = client.post(
        "/api/v1/auth/register",
        json={
            "email": "cookie-session@example.com",
            "password": "StrongPassword123!",
            "organization_name": "Cookie Session Exports",
            "full_name": "Cookie Owner",
        },
    )

    assert registered.status_code == 201
    set_cookie = registered.headers["set-cookie"]
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
