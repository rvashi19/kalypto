# ruff: noqa: E501
"""document verifier tables

Revision ID: 0020_document_verifier
Revises: 0019_compliance_source_registry_admin_fields
Create Date: 2026-07-06 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0020_document_verifier"
down_revision = "0019_compliance_source_registry_admin_fields"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    if not _has_table("document_verification_runs"):
        op.create_table(
            "document_verification_runs",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("tenant_id", sa.Uuid(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=True),
            sa.Column("shipment_id", sa.Uuid(), nullable=True),
            sa.Column("quote_id", sa.Uuid(), nullable=True),
            sa.Column("status", sa.String(length=40), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("reference_number", sa.String(length=120), nullable=True),
            sa.Column("origin_country", sa.String(length=120), nullable=True),
            sa.Column("destination_country", sa.String(length=120), nullable=True),
            sa.Column("hsn_code", sa.String(length=40), nullable=True),
            sa.Column("product_description", sa.Text(), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["tenant_id"], ["organizations.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_document_verification_runs_tenant_id", "document_verification_runs", ["tenant_id"])
        op.create_index("ix_document_verification_runs_user_id", "document_verification_runs", ["user_id"])
        op.create_index("ix_document_verification_runs_shipment_id", "document_verification_runs", ["shipment_id"])
        op.create_index("ix_document_verification_runs_quote_id", "document_verification_runs", ["quote_id"])
        op.create_index("ix_document_verification_runs_status", "document_verification_runs", ["status"])

    if not _has_table("verification_documents"):
        op.create_table(
            "verification_documents",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("verification_run_id", sa.Uuid(), nullable=False),
            sa.Column("file_name", sa.String(length=255), nullable=False),
            sa.Column("file_type", sa.String(length=20), nullable=False),
            sa.Column("mime_type", sa.String(length=120), nullable=True),
            sa.Column("storage_key", sa.String(length=512), nullable=False),
            sa.Column("document_type", sa.String(length=80), nullable=True),
            sa.Column("parser_used", sa.String(length=80), nullable=False),
            sa.Column("extraction_status", sa.String(length=40), nullable=False),
            sa.Column("extraction_error", sa.Text(), nullable=True),
            sa.Column(
                "uploaded_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["verification_run_id"],
                ["document_verification_runs.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_verification_documents_verification_run_id", "verification_documents", ["verification_run_id"])
        op.create_index("ix_verification_documents_document_type", "verification_documents", ["document_type"])

    if not _has_table("document_extracted_fields"):
        op.create_table(
            "document_extracted_fields",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("verification_run_id", sa.Uuid(), nullable=False),
            sa.Column("document_id", sa.Uuid(), nullable=False),
            sa.Column("document_type", sa.String(length=80), nullable=False),
            sa.Column("field_key", sa.String(length=120), nullable=False),
            sa.Column("field_label", sa.String(length=180), nullable=False),
            sa.Column("raw_value", sa.Text(), nullable=True),
            sa.Column("normalized_value", sa.Text(), nullable=True),
            sa.Column("confidence_score", sa.Float(), nullable=False),
            sa.Column("page_number", sa.Integer(), nullable=True),
            sa.Column("table_reference", sa.String(length=120), nullable=True),
            sa.Column("evidence_excerpt", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["verification_run_id"],
                ["document_verification_runs.id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["document_id"],
                ["verification_documents.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_document_extracted_fields_verification_run_id", "document_extracted_fields", ["verification_run_id"])
        op.create_index("ix_document_extracted_fields_document_id", "document_extracted_fields", ["document_id"])
        op.create_index("ix_document_extracted_fields_field_key", "document_extracted_fields", ["field_key"])

    if not _has_table("document_verification_issues"):
        op.create_table(
            "document_verification_issues",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("verification_run_id", sa.Uuid(), nullable=False),
            sa.Column("issue_type", sa.String(length=60), nullable=False),
            sa.Column("severity", sa.String(length=20), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("field_key", sa.String(length=120), nullable=True),
            sa.Column("expected_value", sa.Text(), nullable=True),
            sa.Column("actual_values_json", sa.JSON(), nullable=True),
            sa.Column("related_document_ids_json", sa.JSON(), nullable=True),
            sa.Column("evidence_json", sa.JSON(), nullable=True),
            sa.Column("confidence_score", sa.Float(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["verification_run_id"],
                ["document_verification_runs.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_document_verification_issues_verification_run_id", "document_verification_issues", ["verification_run_id"])
        op.create_index("ix_document_verification_issues_issue_type", "document_verification_issues", ["issue_type"])
        op.create_index("ix_document_verification_issues_severity", "document_verification_issues", ["severity"])
        op.create_index("ix_document_verification_issues_status", "document_verification_issues", ["status"])
        op.create_index("ix_document_verification_issues_field_key", "document_verification_issues", ["field_key"])

    if not _has_table("document_verification_reports"):
        op.create_table(
            "document_verification_reports",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("verification_run_id", sa.Uuid(), nullable=False),
            sa.Column("summary_json", sa.JSON(), nullable=False),
            sa.Column("issues_count", sa.Integer(), nullable=False),
            sa.Column("critical_count", sa.Integer(), nullable=False),
            sa.Column("high_count", sa.Integer(), nullable=False),
            sa.Column("medium_count", sa.Integer(), nullable=False),
            sa.Column("low_count", sa.Integer(), nullable=False),
            sa.Column("report_storage_key", sa.String(length=512), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["verification_run_id"],
                ["document_verification_runs.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_document_verification_reports_verification_run_id", "document_verification_reports", ["verification_run_id"])


def downgrade() -> None:
    for table in (
        "document_verification_reports",
        "document_verification_issues",
        "document_extracted_fields",
        "verification_documents",
        "document_verification_runs",
    ):
        if _has_table(table):
            op.drop_table(table)
