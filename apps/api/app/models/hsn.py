# ruff: noqa: E501
"""Standalone Indian HSN / ITC(HS) classification master.

This module is independent of incentive/rate lookup (RateTable). An HSN code can
exist here with full hierarchy and source evidence even when no incentive rate is
available for it.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.base import TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class HsnCode(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One HSN/ITC(HS) line. Global master — not tenant scoped."""

    __tablename__ = "hsn_codes"

    code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    # One authoritative row per HSN code; re-imports upsert in place (latest source wins).
    normalized_code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True, index=True)
    digit_level: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    chapter_code: Mapped[str | None] = mapped_column(String(2), nullable=True, index=True)
    heading_code: Mapped[str | None] = mapped_column(String(4), nullable=True, index=True)
    subheading_code: Mapped[str | None] = mapped_column(String(6), nullable=True, index=True)
    parent_code: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)

    unit_of_quantity: Mapped[str | None] = mapped_column(String(40), nullable=True)
    section_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    chapter_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    import_policy: Mapped[str | None] = mapped_column(String(120), nullable=True)
    export_policy: Mapped[str | None] = mapped_column(String(120), nullable=True)
    policy_condition: Mapped[str | None] = mapped_column(Text, nullable=True)

    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    source_document_title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source_document_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_version: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)

    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)


class HsnSourceEvidence(Base, UUIDPrimaryKeyMixin):
    """Audit-grade source evidence attached to an HSN code."""

    __tablename__ = "hsn_source_evidence"

    hsn_code_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("hsn_codes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    # master_description / import_policy / export_policy / gst_rate / duty / notification / manual_admin
    evidence_type: Mapped[str] = mapped_column(String(40), nullable=False)
    raw_text_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    document_title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    document_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
    )
    checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confidence_weight: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=50)


class HsnImportJob(Base, UUIDPrimaryKeyMixin):
    """Tracks one admin import of an official HSN snapshot file."""

    __tablename__ = "hsn_import_jobs"

    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    # csv / xlsx / pdf / html / json / manual
    import_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # pending / running / completed / failed
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    records_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_deactivated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(320), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
    )


class HsnClassificationQuery(Base, UUIDPrimaryKeyMixin):
    """A user classification search. Tenant/user nullable for anonymous/script use."""

    __tablename__ = "hsn_classification_queries"

    tenant_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("organizations.id"), nullable=True, index=True
    )
    user_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)
    query_text: Mapped[str] = mapped_column(String(512), nullable=False)
    normalized_query: Mapped[str] = mapped_column(String(512), nullable=False)
    selected_hsn_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    # searched / selected / sent_for_verification
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="searched")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
    )


class HsnVerificationRequest(Base, UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin):
    """A request for human (CHA/customs broker) verification of a classification."""

    __tablename__ = "hsn_verification_requests"

    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    product_description: Mapped[str] = mapped_column(Text, nullable=False)
    selected_hsn_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    alternative_hsn_codes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    user_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # draft / requested / reviewed / resolved
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="requested", index=True)
    reviewer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
