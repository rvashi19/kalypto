from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy import Enum as SqlEnum
from sqlalchemy import JSON, Uuid, func
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

from app.db.base import Base


class MembershipRole(StrEnum):
    OWNER = "owner"
    STAFF = "staff"
    READ_ONLY = "read_only"


class InvoiceType(StrEnum):
    PROFORMA = "proforma"
    COMMERCIAL = "commercial"


class IncentiveScheme(StrEnum):
    RODTEP = "rodtep"
    DUTY_DRAWBACK = "duty_drawback"
    IGST_REFUND = "igst_refund"
    ROSCTL = "rosctl"


class IncentiveClaimStatus(StrEnum):
    ELIGIBLE = "eligible"
    FILED = "filed"
    SCROLL_GENERATED = "scroll_generated"
    SCRIP_ISSUED = "scrip_issued"
    UTILIZED = "utilized"


class DiscrepancySeverity(StrEnum):
    INFO = "info"
    WARN = "warn"
    CRITICAL = "critical"


class ComplianceStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    EXPIRING = "expiring"
    OVERDUE = "overdue"
    RESOLVED = "resolved"


class AlertSeverity(StrEnum):
    INFO = "info"
    WARN = "warn"
    CRITICAL = "critical"


class NotificationChannelType(StrEnum):
    IN_APP = "in_app"
    EMAIL = "email"
    WHATSAPP = "whatsapp"


class NotificationStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class ConsentStatus(StrEnum):
    GRANTED = "granted"
    REVOKED = "revoked"
    EXPIRED = "expired"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class UUIDPrimaryKeyMixin:
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)


class TenantScopedMixin:
    @declared_attr.directive
    def tenant_id(cls) -> Mapped[UUID]:
        return mapped_column(Uuid, ForeignKey("organizations.id"), nullable=False, index=True)


class Organization(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Membership(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("organization_id", "user_id", name="uq_membership_org_user"),)

    organization_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("organizations.id"), nullable=False)
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    role: Mapped[MembershipRole] = mapped_column(SqlEnum(MembershipRole), nullable=False)


class Buyer(Base, UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin):
    __tablename__ = "buyers"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_buyers_tenant_name"),)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    country: Mapped[str | None] = mapped_column(String(120), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class Product(Base, UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin):
    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("tenant_id", "sku", name="uq_products_tenant_sku"),)

    sku: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    hsn_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    unit_of_measure: Mapped[str | None] = mapped_column(String(30), nullable=True)


class Shipment(Base, UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin):
    __tablename__ = "shipments"
    __table_args__ = (UniqueConstraint("tenant_id", "shipping_bill_no", name="uq_shipments_tenant_bill"),)

    buyer_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("buyers.id"), nullable=True)
    shipping_bill_no: Mapped[str] = mapped_column(String(120), nullable=False)
    port: Mapped[str | None] = mapped_column(String(120), nullable=True)
    shipment_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    egm_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fob_value: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    incoterm: Mapped[str | None] = mapped_column(String(20), nullable=True)


class Invoice(Base, UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin):
    __tablename__ = "invoices"
    __table_args__ = (UniqueConstraint("tenant_id", "invoice_number", name="uq_invoices_tenant_number"),)

    shipment_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("shipments.id"), nullable=True)
    buyer_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("buyers.id"), nullable=True)
    invoice_number: Mapped[str] = mapped_column(String(120), nullable=False)
    type: Mapped[InvoiceType] = mapped_column(SqlEnum(InvoiceType), nullable=False)
    issue_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    total_amount: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)


class PackingList(Base, UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin):
    __tablename__ = "packing_lists"
    __table_args__ = (
        UniqueConstraint("tenant_id", "packing_list_number", name="uq_packing_lists_tenant_number"),
    )

    shipment_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("shipments.id"), nullable=True)
    packing_list_number: Mapped[str] = mapped_column(String(120), nullable=False)
    issue_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    package_count: Mapped[int | None] = mapped_column(nullable=True)
    gross_weight: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    net_weight: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)


class GstExportInvoice(Base, UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin):
    __tablename__ = "gst_export_invoices"

    shipment_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("shipments.id"), nullable=True)
    gst_invoice_number: Mapped[str] = mapped_column(String(120), nullable=False)
    gst_filing_period: Mapped[str | None] = mapped_column(String(20), nullable=True)
    taxable_value: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    igst_amount: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    export_type: Mapped[str | None] = mapped_column(String(50), nullable=True)


class BankRealization(Base, UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin):
    __tablename__ = "bank_realizations"

    shipment_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("shipments.id"), nullable=True)
    brc_number: Mapped[str] = mapped_column(String(120), nullable=False)
    bank_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    realized_amount: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    realization_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class IncentiveClaim(Base, UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin):
    __tablename__ = "incentive_claims"

    shipment_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("shipments.id"), nullable=True)
    scheme: Mapped[IncentiveScheme] = mapped_column(SqlEnum(IncentiveScheme), nullable=False)
    entitled_amount: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    claimed_amount: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    status: Mapped[IncentiveClaimStatus] = mapped_column(
        SqlEnum(IncentiveClaimStatus),
        nullable=False,
        default=IncentiveClaimStatus.ELIGIBLE,
    )
    scrip_no: Mapped[str | None] = mapped_column(String(120), nullable=True)


class Discrepancy(Base, UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin):
    __tablename__ = "discrepancies"

    shipment_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("shipments.id"), nullable=False)
    type: Mapped[str] = mapped_column(String(120), nullable=False)
    severity: Mapped[DiscrepancySeverity] = mapped_column(SqlEnum(DiscrepancySeverity), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_fix: Mapped[str | None] = mapped_column(Text, nullable=True)
    lock_risk_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lock_risk: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class ComplianceItem(Base, UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin):
    __tablename__ = "compliance_items"

    item_type: Mapped[str] = mapped_column(String(120), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expiry_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[ComplianceStatus] = mapped_column(SqlEnum(ComplianceStatus), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class Alert(Base, UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin):
    __tablename__ = "alerts"

    user_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)
    type: Mapped[str] = mapped_column(String(120), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[AlertSeverity] = mapped_column(SqlEnum(AlertSeverity), nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Notification(Base, UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin):
    __tablename__ = "notifications"

    alert_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("alerts.id"), nullable=True)
    channel: Mapped[NotificationChannelType] = mapped_column(
        SqlEnum(NotificationChannelType),
        nullable=False,
    )
    status: Mapped[NotificationStatus] = mapped_column(SqlEnum(NotificationStatus), nullable=False)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RateTable(Base, UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin):
    __tablename__ = "rate_tables"

    scheme: Mapped[str] = mapped_column(String(120), nullable=False)
    hsn: Mapped[str] = mapped_column(String(20), nullable=False)
    rate: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    effective_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    version_stamp: Mapped[str] = mapped_column(String(80), nullable=False)
    confidence: Mapped[str | None] = mapped_column(String(40), nullable=True)


class RuleDefinition(Base, UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin):
    __tablename__ = "rule_definitions"

    code: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity_default: Mapped[DiscrepancySeverity] = mapped_column(
        SqlEnum(DiscrepancySeverity),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    version: Mapped[str] = mapped_column(String(40), nullable=False)


class AuditLog(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "audit_logs"

    tenant_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("organizations.id"),
        nullable=True,
        index=True,
    )
    actor_user_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    route: Mapped[str | None] = mapped_column(String(255), nullable=True)
    method: Mapped[str | None] = mapped_column(String(16), nullable=True)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
    )


class ConsentRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin):
    __tablename__ = "consent_records"

    provider: Mapped[str] = mapped_column(String(120), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[ConsentStatus] = mapped_column(SqlEnum(ConsentStatus), nullable=False)
    granted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class RevokedToken(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "revoked_tokens"

    tenant_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("organizations.id"), nullable=True)
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    jti: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
    )


class ShipmentMode(StrEnum):
    SEA = "sea"
    AIR = "air"
    COURIER = "courier"


class ShipmentStage(StrEnum):
    PRE_SHIPMENT = "pre_shipment"
    POST_SHIPMENT = "post_shipment"


class DocumentType(StrEnum):
    PROFORMA_INVOICE = "proforma_invoice"
    COMMERCIAL_INVOICE = "commercial_invoice"
    PACKING_LIST = "packing_list"
    PURCHASE_ORDER = "purchase_order"
    BL_AWB = "bl_awb"
    SHIPPING_BILL = "shipping_bill"
    CERTIFICATE_OF_ORIGIN = "certificate_of_origin"
    INSURANCE = "insurance"
    INSPECTION_CERTIFICATE = "inspection_certificate"
    PHYTOSANITARY_CERTIFICATE = "phytosanitary_certificate"
    FUMIGATION_CERTIFICATE = "fumigation_certificate"
    EBRC = "ebrc"
    OTHER = "other"


class DocumentUploadStatus(StrEnum):
    PENDING = "pending"
    EXTRACTED = "extracted"
    FAILED = "failed"


class ExportShipment(Base, UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin):
    """Core shipment profile — the entry point for every audit workflow."""

    __tablename__ = "export_shipments"

    exporter_name: Mapped[str] = mapped_column(String(255), nullable=False)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    hsn_code: Mapped[str] = mapped_column(String(20), nullable=False)
    destination_country: Mapped[str] = mapped_column(String(120), nullable=False)
    buyer_country: Mapped[str] = mapped_column(String(120), nullable=False)
    incoterm: Mapped[str] = mapped_column(String(20), nullable=False)
    payment_term: Mapped[str] = mapped_column(String(120), nullable=False)
    shipment_mode: Mapped[ShipmentMode] = mapped_column(SqlEnum(ShipmentMode), nullable=False)
    container_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    shipment_stage: Mapped[ShipmentStage] = mapped_column(SqlEnum(ShipmentStage), nullable=False)
    fob_value: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    invoice_currency: Mapped[str] = mapped_column(String(10), nullable=False, default="USD")
    shipping_bill_no: Mapped[str | None] = mapped_column(String(120), nullable=True)
    port_of_loading: Mapped[str | None] = mapped_column(String(120), nullable=True)
    shipment_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ShipmentDocument(Base, UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin):
    """Tracks every document uploaded against a shipment."""

    __tablename__ = "shipment_documents"

    shipment_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("export_shipments.id"), nullable=False, index=True)
    document_type: Mapped[DocumentType] = mapped_column(SqlEnum(DocumentType), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    file_size_bytes: Mapped[int | None] = mapped_column(nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    extracted_fields: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    upload_status: Mapped[DocumentUploadStatus] = mapped_column(
        SqlEnum(DocumentUploadStatus),
        nullable=False,
        default=DocumentUploadStatus.PENDING,
    )
