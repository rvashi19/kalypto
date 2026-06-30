# ruff: noqa: E501
"""Export incentive / rate records (RoDTEP, Drawback, RoSCTL, …).

Standalone from HSN classification: an IncentiveRate is looked up for an already
selected HSN code. Only approved, active, non-expired records are shown to normal
users. Kept separate from the legacy RateTable so /shipments/hsn-rates keeps working.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class IncentiveRate(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "incentive_rates"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "scheme",
            "normalized_hsn_code",
            "effective_from",
            name="uq_incentive_rate_tenant_scheme_hsn_from",
        ),
    )

    # Nullable for global/source-provided rows not tied to a tenant.
    tenant_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("organizations.id"), nullable=True, index=True
    )
    scheme: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    hsn_code: Mapped[str] = mapped_column(String(20), nullable=False)
    normalized_hsn_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    digit_level: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    product_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    rate_type: Mapped[str] = mapped_column(String(20), nullable=False, default="percentage")
    rate_value: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    cap_value: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    cap_unit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    unit_of_quantity: Mapped[str | None] = mapped_column(String(40), nullable=True)
    condition_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    source_document_title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source_document_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_version: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)

    # pending / approved / rejected / expired
    approval_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    verified_by: Mapped[str | None] = mapped_column(String(320), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)


class IncentiveSourceEvidence(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "incentive_source_evidence"

    incentive_rate_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("incentive_rates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    document_title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    document_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    raw_text_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
    )
    checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # rodtep_schedule / drawback_schedule / rosctl_schedule / notification / manual_admin
    evidence_type: Mapped[str] = mapped_column(String(40), nullable=False)
    confidence_weight: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=50)


class IncentiveImportJob(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "incentive_import_jobs"

    scheme: Mapped[str | None] = mapped_column(String(40), nullable=True)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    import_type: Mapped[str] = mapped_column(String(20), nullable=False)
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
