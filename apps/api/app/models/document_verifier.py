# ruff: noqa: E501
"""AI Document Verifier persistence models."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON as SAJSON
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class DocumentVerificationRun(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "document_verification_runs"

    tenant_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("organizations.id"), nullable=False, index=True)
    user_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True, index=True)
    shipment_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    quote_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="uploaded", index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    reference_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    origin_country: Mapped[str | None] = mapped_column(String(120), nullable=True)
    destination_country: Mapped[str | None] = mapped_column(String(120), nullable=True)
    hsn_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    product_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class VerificationDocument(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "verification_documents"

    verification_run_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("document_verification_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(20), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    document_type: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    parser_used: Mapped[str] = mapped_column(String(80), nullable=False, default="pending")
    extraction_status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending")
    extraction_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
    )


class DocumentExtractedField(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "document_extracted_fields"

    verification_run_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("document_verification_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("verification_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_type: Mapped[str] = mapped_column(String(80), nullable=False)
    field_key: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    field_label: Mapped[str] = mapped_column(String(180), nullable=False)
    raw_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    normalized_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[float] = mapped_column(nullable=False, default=0)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    table_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    evidence_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
    )


class DocumentVerificationIssue(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "document_verification_issues"

    verification_run_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("document_verification_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    issue_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open", index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    field_key: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    expected_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    actual_values_json: Mapped[list[dict[str, Any]] | None] = mapped_column(SAJSON, nullable=True)
    related_document_ids_json: Mapped[list[str] | None] = mapped_column(SAJSON, nullable=True)
    evidence_json: Mapped[list[dict[str, Any]] | None] = mapped_column(SAJSON, nullable=True)
    confidence_score: Mapped[float] = mapped_column(nullable=False, default=0)


class DocumentVerificationReport(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "document_verification_reports"

    verification_run_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("document_verification_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    summary_json: Mapped[dict[str, Any]] = mapped_column(SAJSON, nullable=False, default=dict)
    issues_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    critical_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    high_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    medium_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    low_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    report_storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
    )
