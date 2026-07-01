"""standalone HSN finder master

Revision ID: 0007_hsn_finder
Revises: 0006_rate_table_governance
Create Date: 2026-06-27 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007_hsn_finder"
down_revision = "0006_rate_table_governance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "hsn_codes" in sa.inspect(op.get_bind()).get_table_names():
        return

    op.create_table(
        "hsn_codes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("normalized_code", sa.String(length=20), nullable=False),
        sa.Column("digit_level", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("chapter_code", sa.String(length=2), nullable=True),
        sa.Column("heading_code", sa.String(length=4), nullable=True),
        sa.Column("subheading_code", sa.String(length=6), nullable=True),
        sa.Column("parent_code", sa.String(length=20), nullable=True),
        sa.Column("unit_of_quantity", sa.String(length=40), nullable=True),
        sa.Column("section_name", sa.String(length=255), nullable=True),
        sa.Column("chapter_name", sa.String(length=255), nullable=True),
        sa.Column("import_policy", sa.String(length=120), nullable=True),
        sa.Column("export_policy", sa.String(length=120), nullable=True),
        sa.Column("policy_condition", sa.Text(), nullable=True),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=True),
        sa.Column("source_document_title", sa.String(length=512), nullable=True),
        sa.Column("source_document_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_version", sa.String(length=80), nullable=True),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("normalized_code", "source_version", name="uq_hsn_codes_norm_version"),
    )
    op.create_index("ix_hsn_codes_code", "hsn_codes", ["code"])
    op.create_index("ix_hsn_codes_normalized_code", "hsn_codes", ["normalized_code"])
    op.create_index("ix_hsn_codes_digit_level", "hsn_codes", ["digit_level"])
    op.create_index("ix_hsn_codes_chapter_code", "hsn_codes", ["chapter_code"])
    op.create_index("ix_hsn_codes_heading_code", "hsn_codes", ["heading_code"])
    op.create_index("ix_hsn_codes_subheading_code", "hsn_codes", ["subheading_code"])
    op.create_index("ix_hsn_codes_parent_code", "hsn_codes", ["parent_code"])
    op.create_index("ix_hsn_codes_source_version", "hsn_codes", ["source_version"])
    op.create_index("ix_hsn_codes_is_active", "hsn_codes", ["is_active"])

    op.create_table(
        "hsn_source_evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("hsn_code_id", sa.Uuid(), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=True),
        sa.Column("evidence_type", sa.String(length=40), nullable=False),
        sa.Column("raw_text_excerpt", sa.Text(), nullable=True),
        sa.Column("document_title", sa.String(length=512), nullable=True),
        sa.Column("document_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=True),
        sa.Column("confidence_weight", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.ForeignKeyConstraint(["hsn_code_id"], ["hsn_codes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_hsn_source_evidence_hsn_code_id", "hsn_source_evidence", ["hsn_code_id"])

    op.create_table(
        "hsn_import_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=True),
        sa.Column("import_type", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("records_seen", sa.Integer(), nullable=False),
        sa.Column("records_created", sa.Integer(), nullable=False),
        sa.Column("records_updated", sa.Integer(), nullable=False),
        sa.Column("records_deactivated", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("checksum", sa.String(length=64), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(length=320), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_hsn_import_jobs_status", "hsn_import_jobs", ["status"])

    op.create_table(
        "hsn_classification_queries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("query_text", sa.String(length=512), nullable=False),
        sa.Column("normalized_query", sa.String(length=512), nullable=False),
        sa.Column("selected_hsn_code", sa.String(length=20), nullable=True),
        sa.Column("confidence", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_hsn_classification_queries_tenant_id", "hsn_classification_queries", ["tenant_id"])

    op.create_table(
        "hsn_verification_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("product_description", sa.Text(), nullable=False),
        sa.Column("selected_hsn_code", sa.String(length=20), nullable=True),
        sa.Column("alternative_hsn_codes", sa.JSON(), nullable=False),
        sa.Column("user_notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("reviewer_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_hsn_verification_requests_tenant_id", "hsn_verification_requests", ["tenant_id"])
    op.create_index("ix_hsn_verification_requests_user_id", "hsn_verification_requests", ["user_id"])
    op.create_index("ix_hsn_verification_requests_status", "hsn_verification_requests", ["status"])


def downgrade() -> None:
    op.drop_table("hsn_verification_requests")
    op.drop_table("hsn_classification_queries")
    op.drop_table("hsn_import_jobs")
    op.drop_table("hsn_source_evidence")
    op.drop_table("hsn_codes")
