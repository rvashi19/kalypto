"""Document Builder — import sessions, document packs, generated files

Revision ID: 0013_document_builder
Revises: 0012_export_quote
Create Date: 2026-07-01 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0013_document_builder"
down_revision = "0012_export_quote"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = sa.inspect(bind).get_table_names()

    if "document_import_sessions" not in existing:
        op.create_table(
            "document_import_sessions",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("tenant_id", sa.Uuid(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("original_filename", sa.String(255), nullable=False),
            sa.Column("file_type", sa.String(10), nullable=False),
            sa.Column("sheet_name", sa.String(120), nullable=True),
            sa.Column("detected_columns_json", sa.JSON(), nullable=True),
            sa.Column("suggested_mapping_json", sa.JSON(), nullable=True),
            sa.Column("parsed_preview_json", sa.JSON(), nullable=True),
            sa.Column("raw_file_storage_key", sa.String(512), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="uploaded"),
            sa.Column("warnings_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["tenant_id"], ["organizations.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_document_import_sessions_tenant_id", "document_import_sessions", ["tenant_id"])
        op.create_index("ix_document_import_sessions_user_id", "document_import_sessions", ["user_id"])

    if "export_document_packs" not in existing:
        op.create_table(
            "export_document_packs",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("tenant_id", sa.Uuid(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("pack_number", sa.String(80), nullable=True),
            sa.Column("shipment_reference", sa.String(120), nullable=True),
            sa.Column("invoice_number", sa.String(120), nullable=True),
            sa.Column("buyer_name", sa.String(255), nullable=True),
            sa.Column("consignee_name", sa.String(255), nullable=True),
            sa.Column("destination_country", sa.String(120), nullable=True),
            sa.Column("incoterm", sa.String(20), nullable=True),
            sa.Column("currency", sa.String(10), nullable=True),
            sa.Column("total_invoice_value", sa.Numeric(16, 2), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
            sa.Column("source_import_session_id", sa.Uuid(), nullable=True),
            sa.Column("shipment_data_json", sa.JSON(), nullable=True),
            sa.Column("validation_warnings_json", sa.JSON(), nullable=True),
            sa.Column("generated_documents_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["tenant_id"], ["organizations.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_export_document_packs_tenant_id", "export_document_packs", ["tenant_id"])
        op.create_index("ix_export_document_packs_user_id", "export_document_packs", ["user_id"])
        op.create_index("ix_export_document_packs_pack_number", "export_document_packs", ["pack_number"])

    if "generated_export_documents" not in existing:
        op.create_table(
            "generated_export_documents",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("tenant_id", sa.Uuid(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("pack_id", sa.Uuid(), nullable=False),
            sa.Column("document_type", sa.String(60), nullable=False),
            sa.Column("file_name", sa.String(255), nullable=False),
            sa.Column("file_format", sa.String(10), nullable=False, server_default="pdf"),
            sa.Column("storage_key", sa.String(512), nullable=False),
            sa.Column("file_size", sa.Integer(), nullable=True),
            sa.Column("checksum", sa.String(64), nullable=True),
            sa.Column("version_number", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["tenant_id"], ["organizations.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["pack_id"], ["export_document_packs.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_generated_export_documents_tenant_id", "generated_export_documents", ["tenant_id"])
        op.create_index("ix_generated_export_documents_pack_id", "generated_export_documents", ["pack_id"])


def downgrade() -> None:
    op.drop_table("generated_export_documents")
    op.drop_table("export_document_packs")
    op.drop_table("document_import_sessions")
