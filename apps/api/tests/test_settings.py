from pydantic import ValidationError

from app.core.settings import Settings


def test_render_postgres_url_is_normalized_for_sqlalchemy() -> None:
    settings = Settings(DATABASE_URL="postgresql://user:pass@db.example.com:5432/kalypto")

    assert settings.database_url == "postgresql+psycopg://user:pass@db.example.com:5432/kalypto"


def test_production_rejects_default_jwt_secret() -> None:
    try:
        Settings(
            environment="production",
            frontend_url="https://app.example.com",
            JWT_SECRET_KEY="change-me-in-production",
        )
    except ValidationError as error:
        assert "JWT_SECRET_KEY" in str(error)
    else:
        raise AssertionError("Expected production settings to reject the default JWT secret.")
