# ruff: noqa: E501
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.base import TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class ComplianceCountry(Base, UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin):
    __tablename__ = "compliance_countries"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_compliance_countries_tenant_name"),
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    region: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ProductCategory(Base, UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin):
    __tablename__ = "product_categories"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_product_categories_tenant_name"),
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ComplianceRequirement(Base, UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin):
    __tablename__ = "compliance_requirements"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "content_hash", name="uq_compliance_requirements_tenant_hash"
        ),
    )

    country_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("compliance_countries.id"),
        nullable=False,
        index=True,
    )
    category_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("product_categories.id"),
        nullable=False,
        index=True,
    )
    hsn_code: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    # Origin country (India export side by default). Nullable for legacy rows.
    origin_country: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    product_keywords: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    requirement_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    requirement_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_authority_level: Mapped[str] = mapped_column(String(40), nullable=False)
    effective_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
    )
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confidence_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=70)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active", index=True)
    review_status: Mapped[str] = mapped_column(
        String(40), nullable=False, default="approved", index=True
    )
    reviewed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    unresolved_questions: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class ComplianceScrapeRun(Base, UUIDPrimaryKeyMixin, TenantScopedMixin):
    __tablename__ = "compliance_scrape_runs"

    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    country: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    records_found: Mapped[int] = mapped_column(default=0, nullable=False)
    errors: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ComplianceSourceSnapshot(Base, UUIDPrimaryKeyMixin, TenantScopedMixin):
    __tablename__ = "compliance_source_snapshots"

    source_url: Mapped[str] = mapped_column(String(2048), nullable=False, index=True)
    country: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    markdown: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    previous_content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    # Richer retrieval metadata (nullable for backward compatibility with older snapshots).
    source_registry_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("compliance_source_registry.id"), nullable=True, index=True
    )
    final_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(20), nullable=True)  # html/pdf/xlsx/csv/markdown/text
    http_status: Mapped[int | None] = mapped_column(nullable=True)
    parser_used: Mapped[str | None] = mapped_column(String(40), nullable=True)
    parser_status: Mapped[str | None] = mapped_column(String(40), nullable=True)  # ok/failed
    raw_storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    extracted_text_storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
        index=True,
    )


class ComplianceSourceChange(Base, UUIDPrimaryKeyMixin, TenantScopedMixin):
    __tablename__ = "compliance_source_changes"

    source_url: Mapped[str] = mapped_column(String(2048), nullable=False, index=True)
    country: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    previous_snapshot_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("compliance_source_snapshots.id"),
        nullable=True,
    )
    current_snapshot_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("compliance_source_snapshots.id"),
        nullable=False,
    )
    previous_content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    current_content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(40), nullable=False, default="needs_review", index=True
    )
    reviewed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
    )


class ComplianceChatSession(Base, UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin):
    __tablename__ = "compliance_chat_sessions"

    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    product: Mapped[str] = mapped_column(String(255), nullable=False)
    hsn_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    destination_country: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(120), nullable=False)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)


class ComplianceSourceRegistry(Base, UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin):
    """Curated official source per country/authority. Only these are fetched."""

    __tablename__ = "compliance_source_registry"

    country: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    authority_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    base_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    # Official domains this source is allowed to fetch from (merged into whitelist).
    allowed_domains_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False, default="mixed")  # html/pdf/xlsx/csv/mixed
    product_categories_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    refresh_frequency_days: Mapped[int] = mapped_column(default=30, nullable=False)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ComplianceRetrievalJob(Base, UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin):
    """Async official-source retrieval job. Never blocks the user request."""

    __tablename__ = "compliance_retrieval_jobs"

    requested_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=True
    )
    origin_country: Mapped[str | None] = mapped_column(String(120), nullable=True)
    destination_country: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    product_category: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    hsn_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    product_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # queued / running / completed / failed / needs_review
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="queued", index=True)
    source_registry_ids_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    pages_fetched: Mapped[int] = mapped_column(default=0, nullable=False)
    snapshots_created: Mapped[int] = mapped_column(default=0, nullable=False)
    requirements_extracted: Mapped[int] = mapped_column(default=0, nullable=False)
    retry_count: Mapped[int] = mapped_column(default=0, nullable=False)
    max_retries: Mapped[int] = mapped_column(default=3, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ComplianceCheckSession(Base, UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin):
    """Persisted result of a /compliance/check request (source-backed answer)."""

    __tablename__ = "compliance_check_sessions"

    user_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)
    origin_country: Mapped[str | None] = mapped_column(String(120), nullable=True)
    destination_country: Mapped[str] = mapped_column(String(120), nullable=False)
    hsn_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    product_description: Mapped[str] = mapped_column(Text, nullable=False)
    product_category: Mapped[str] = mapped_column(String(120), nullable=False)
    input_facts_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    missing_questions_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    answer_summary_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    source_ids_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    confidence_label: Mapped[str | None] = mapped_column(String(20), nullable=True)
    retrieval_job_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("compliance_retrieval_jobs.id"), nullable=True
    )
    # answered / needs_more_info / no_verified_source / retrieval_queued / pending_review
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="answered", index=True)


class ComplianceRequirementEvidence(Base, UUIDPrimaryKeyMixin, TenantScopedMixin):
    """Official-source excerpt backing an extracted requirement card."""

    __tablename__ = "compliance_requirement_evidence"

    requirement_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("compliance_requirements.id"), nullable=False, index=True
    )
    source_snapshot_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("compliance_source_snapshots.id"), nullable=True
    )
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    authority_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    evidence_excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[int | None] = mapped_column(nullable=True)
    table_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
    )


class ComplianceReviewQueue(Base, UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin):
    """Admin review item for an AI-extracted (pending_review) requirement card."""

    __tablename__ = "compliance_review_queue"

    requirement_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("compliance_requirements.id"), nullable=False, index=True
    )
    assigned_to: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)
    # pending / approved / rejected / needs_changes
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending", index=True)
    reviewer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class ComplianceChatMessage(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "compliance_chat_messages"

    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id"), nullable=False, index=True
    )
    session_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("compliance_chat_sessions.id"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(40), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    retrieved_requirement_ids: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
    )
