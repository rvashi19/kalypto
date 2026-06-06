from app.core.settings import Settings


def test_render_postgres_url_is_normalized_for_sqlalchemy() -> None:
    settings = Settings(DATABASE_URL="postgresql://user:pass@db.example.com:5432/kalypto")

    assert settings.database_url == "postgresql+psycopg://user:pass@db.example.com:5432/kalypto"
