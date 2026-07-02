# ruff: noqa: E501
"""Document Builder models — import sessions, document packs, and generated files."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Uuid, func
from sqlalchemy import JSON as SAJSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class DocumentImportSession(Base, UUIDPrimaryKeyMixin):
    """Temporary session created when a user uploads a spreadsheet for parsing."""

    __tablename__ = "document_import_sessions"

    tenant_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("organizations.id"), nullable=False, index=True)
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)

    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(10), nullable=False)  # xlsx / csv
    sheet_name: Mapped[str | None] = mapped_column(String(120), nullable=True)

    detected_columns_json: Mapped[list | None] = mapped_column(SAJSON, nullable=True)
    suggested_mapping_json: Mapped[dict | None] = mapped_column(SAJSON, nullable=True)
    parsed_preview_json: Mapped[list | None] = mapped_column(SAJSON, nullable=True)
    raw_file_storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # uploaded / mapped / validated / expired
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="uploaded")
    warnings_json: Mapped[list | None] = mapped_column(SAJSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), default=lambda: datetime.now(UTC)
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ExportDocumentPack(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A saved set of export documents generated from a single shipment dataset."""

    __tablename__ = "export_document_packs"

    tenant_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("organizations.id"), nullable=False, index=True)
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)

    pack_number: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    shipment_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    invoice_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    buyer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    consignee_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    destination_country: Mapped[str | None] = mapped_column(String(120), nullable=True)
    incoterm: Mapped[str | None] = mapped_column(String(20), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    total_invoice_value: Mapped[float | None] = mapped_column(nullable=True)

    # draft / generated / finalized / archived
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")

    source_import_session_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)

    shipment_data_json: Mapped[dict | None] = mapped_column(SAJSON, nullable=True)
    validation_warnings_json: Mapped[list | None] = mapped_column(SAJSON, nullable=True)
    generated_documents_json: Mapped[list | None] = mapped_column(SAJSON, nullable=True)


class GeneratedExportDocument(Base, UUIDPrimaryKeyMixin):
    """One generated file within a document pack."""

    __tablename__ = "generated_export_documents"

    tenant_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("organizations.id"), nullable=False, index=True)
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    pack_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("export_document_packs.id", ondelete="CASCADE"), nullable=False, index=True)

    document_type: Mapped[str] = mapped_column(String(60), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_format: Mapped[str] = mapped_column(String(10), nullable=False, default="pdf")
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), default=lambda: datetime.now(UTC)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), default=lambda: datetime.now(UTC)
    )
