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
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_compliance_countries_tenant_name"),)

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    region: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ProductCategory(Base, UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin):
    __tablename__ = "product_categories"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_product_categories_tenant_name"),)

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ComplianceRequirement(Base, UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin):
    __tablename__ = "compliance_requirements"
    __table_args__ = (
        UniqueConstraint("tenant_id", "content_hash", name="uq_compliance_requirements_tenant_hash"),
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
    confidence_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=70)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active", index=True)
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


class ComplianceChatSession(Base, UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin):
    __tablename__ = "compliance_chat_sessions"

    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    product: Mapped[str] = mapped_column(String(255), nullable=False)
    hsn_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    destination_country: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(120), nullable=False)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)


class ComplianceChatMessage(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "compliance_chat_messages"

    tenant_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("organizations.id"), nullable=False, index=True)
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