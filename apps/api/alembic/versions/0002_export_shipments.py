"""add export_shipments and shipment_documents tables

Revision ID: 0002_export_shipments
Revises: 0001_phase0_foundation
Create Date: 2026-06-19 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_export_shipments"
down_revision = "0001_phase0_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "export_shipments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("exporter_name", sa.String(255), nullable=False),
        sa.Column("product_name", sa.String(255), nullable=False),
        sa.Column("hsn_code", sa.String(20), nullable=False),
        sa.Column("destination_country", sa.String(120), nullable=False),
        sa.Column("buyer_country", sa.String(120), nullable=False),
        sa.Column("incoterm", sa.String(20), nullable=False),
        sa.Column("payment_term", sa.String(120), nullable=False),
        sa.Column("shipment_mode", sa.String(20), nullable=False),
        sa.Column("container_type", sa.String(80), nullable=True),
        sa.Column("shipment_stage", sa.String(20), nullable=False),
        sa.Column("fob_value", sa.Numeric(14, 2), nullable=True),
        sa.Column("invoice_currency", sa.String(10), nullable=False, server_default="USD"),
        sa.Column("shipping_bill_no", sa.String(120), nullable=True),
        sa.Column("port_of_loading", sa.String(120), nullable=True),
        sa.Column("shipment_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_export_shipments_tenant_id", "export_shipments", ["tenant_id"])

    op.create_table(
        "shipment_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("shipment_id", sa.Uuid(), nullable=False),
        sa.Column("document_type", sa.String(60), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_path", sa.String(512), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("mime_type", sa.String(120), nullable=True),
        sa.Column("extracted_fields", sa.JSON(), nullable=True),
        sa.Column("upload_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["shipment_id"], ["export_shipments.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shipment_documents_tenant_id", "shipment_documents", ["tenant_id"])
    op.create_index("ix_shipment_documents_shipment_id", "shipment_documents", ["shipment_id"])


def downgrade() -> None:
    op.drop_table("shipment_documents")
    op.drop_table("export_shipments")
