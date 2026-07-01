from app.core.settings import Settings


def test_default_cors_regex_supports_render_and_vercel_domains() -> None:
    settings = Settings()

    assert settings.cors_allow_origin_regex == r"https://.*\.(onrender\.com|vercel\.app)"
