from functools import lru_cache
from typing import Self

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Export Incentive Assurance API"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"
    frontend_url: str = "http://localhost:5173"
    cors_allow_origin_regex: str = r"https://.*\.(onrender\.com|vercel\.app)"
    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/export_assurance",
        alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    jwt_secret_key: str = Field(default="change-me-in-production", alias="JWT_SECRET_KEY")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-5.4-mini", alias="OPENAI_MODEL")
    groq_api_key: str | None = Field(default=None, alias="GROQ_API_KEY")
    groq_model: str = Field(default="llama-3.3-70b-versatile", alias="GROQ_MODEL")
    xai_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("XAI_API_KEY", "OPENAI_API_KEY"),
    )
    xai_model: str = Field(
        default="grok-4.3",
        validation_alias=AliasChoices("XAI_MODEL", "OPENAI_MODEL"),
    )
    xai_base_url: str = Field(default="https://api.x.ai/v1", alias="XAI_BASE_URL")
    upload_dir: str = Field(default="/tmp/kalypto_uploads", alias="UPLOAD_DIR")
    compliance_scraper_provider: str = Field(default="http", alias="COMPLIANCE_SCRAPER_PROVIDER")
    compliance_allow_private_scrape: bool = Field(
        default=False,
        alias="COMPLIANCE_ALLOW_PRIVATE_SCRAPE",
    )
    compliance_scraper_user_agent: str = Field(
        default="KalyptoComplianceBot/0.1 (+https://kalypto.local; review-only)",
        alias="COMPLIANCE_SCRAPER_USER_AGENT",
    )
    compliance_store_backend: str = Field(default="postgres", alias="COMPLIANCE_STORE_BACKEND")
    mongodb_url: str | None = Field(default=None, alias="MONGODB_URL")
    mongodb_database: str = Field(default="kalypto", alias="MONGODB_DATABASE")
    mongodb_requirements_collection: str = Field(
        default="compliance_requirements",
        alias="MONGODB_REQUIREMENTS_COLLECTION",
    )
    mongodb_source_snapshots_collection: str = Field(
        default="compliance_source_snapshots",
        alias="MONGODB_SOURCE_SNAPSHOTS_COLLECTION",
    )
    mongodb_source_changes_collection: str = Field(
        default="compliance_source_changes",
        alias="MONGODB_SOURCE_CHANGES_COLLECTION",
    )
    compliance_refresh_interval_days: int = Field(
        default=3,
        alias="COMPLIANCE_REFRESH_INTERVAL_DAYS",
    )
    # Country Compliance Checker (retrieval + AI extraction controls).
    # AI_PROVIDER selects which LLM the compliance extractor uses; "auto" falls back
    # through groq -> openai -> xai based on whichever key is configured.
    ai_provider: str = Field(default="auto", alias="AI_PROVIDER")
    # Comma-separated official domains appended to the built-in whitelist
    # (see compliance_whitelist.py). Only whitelisted domains are ever fetched.
    compliance_allowed_domains: str = Field(default="", alias="COMPLIANCE_ALLOWED_DOMAINS")
    compliance_max_pages_per_job: int = Field(default=10, alias="COMPLIANCE_MAX_PAGES_PER_JOB")
    compliance_max_pdf_mb: int = Field(default=15, alias="COMPLIANCE_MAX_PDF_MB")
    # Storage abstraction for raw snapshots + extracted text.
    # local now; maps to S3/Cloudflare R2 in production (see services/storage.py).
    compliance_storage_backend: str = Field(default="local", alias="COMPLIANCE_STORAGE_BACKEND")
    compliance_storage_path: str = Field(
        default="./.compliance_storage", alias="COMPLIANCE_STORAGE_PATH"
    )
    firecrawl_api_key: str | None = Field(default=None, alias="FIRECRAWL_API_KEY")
    # HSN master scraper (admin-triggered, rate-limited, source-versioned).
    data_gov_in_api_key: str | None = Field(default=None, alias="DATA_GOV_IN_API_KEY")
    hsn_scrape_user_agent: str = Field(
        default="KalyptoHsnBot/1.0 (+https://kalypto.local; admin-triggered, review-only)",
        alias="HSN_SCRAPE_USER_AGENT",
    )
    hsn_scrape_max_records: int = Field(default=20000, alias="HSN_SCRAPE_MAX_RECORDS")
    hsn_scrape_min_interval_seconds: int = Field(
        default=2, alias="HSN_SCRAPE_MIN_INTERVAL_SECONDS"
    )
    hsn_scrape_allow_private: bool = Field(default=False, alias="HSN_SCRAPE_ALLOW_PRIVATE")
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

    @model_validator(mode="after")
    def validate_production_secrets(self) -> Self:
        if self.environment.lower() == "production":
            if self.jwt_secret_key == "change-me-in-production" or len(self.jwt_secret_key) < 32:
                raise ValueError(
                    "Production JWT_SECRET_KEY must be a unique value of 32+ characters."
                )
            if not self.frontend_url.startswith("https://"):
                raise ValueError("Production FRONTEND_URL must use HTTPS.")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
