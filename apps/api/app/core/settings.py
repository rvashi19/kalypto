from functools import lru_cache

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Export Incentive Assurance API"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"
    frontend_url: str = "http://localhost:5173"
    cors_allow_origin_regex: str = r"https://.*\.onrender\.com"
    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/export_assurance",
        alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    jwt_secret_key: str = Field(default="change-me-in-production", alias="JWT_SECRET_KEY")
    xai_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("XAI_API_KEY", "OPENAI_API_KEY"),
    )
    xai_model: str = Field(
        default="grok-4.3",
        validation_alias=AliasChoices("XAI_MODEL", "OPENAI_MODEL"),
    )
    xai_base_url: str = Field(
        default="https://api.x.ai/v1",
        alias="XAI_BASE_URL",
    )
    compliance_scraper_provider: str = Field(
        default="manual",
        alias="COMPLIANCE_SCRAPER_PROVIDER",
    )
    firecrawl_api_key: str | None = Field(default=None, alias="FIRECRAWL_API_KEY")
    tavily_api_key: str | None = Field(default=None, alias="TAVILY_API_KEY")
    bright_data_api_key: str | None = Field(default=None, alias="BRIGHT_DATA_API_KEY")
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 60
    audit_logging_enabled: bool = True
    rate_limit_auth_per_minute: int = 20
    rate_limit_uploads_per_minute: int = 10

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+psycopg://", 1)
        if value.startswith("postgresql://") and "+psycopg" not in value:
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
