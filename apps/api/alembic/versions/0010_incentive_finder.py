"""incentive finder (IncentiveRate, evidence, import jobs)

Revision ID: 0010_incentive_finder
Revises: 0009_hsn_product_alias
Create Date: 2026-06-29 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0010_incentive_finder"
down_revision = "0009_hsn_product_alias"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "incentive_rates" in sa.inspect(op.get_bind()).get_table_names():
        return

    op.create_table(
        "incentive_rates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=True),
        sa.Column("scheme", sa.String(length=40), nullable=False),
        sa.Column("hsn_code", sa.String(length=20), nullable=False),
        sa.Column("normalized_hsn_code", sa.String(length=20), nullable=False),
        sa.Column("digit_level", sa.Integer(), nullable=False),
        sa.Column("product_description", sa.Text(), nullable=True),
        sa.Column("rate_type", sa.String(length=20), nullable=False),
        sa.Column("rate_value", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("cap_value", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("cap_unit", sa.String(length=40), nullable=True),
        sa.Column("unit_of_quantity", sa.String(length=40), nullable=True),
        sa.Column("condition_text", sa.Text(), nullable=True),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=True),
        sa.Column("source_document_title", sa.String(length=512), nullable=True),
        sa.Column("source_document_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_version", sa.String(length=80), nullable=True),
        sa.Column("approval_status", sa.String(length=20), nullable=False),
        sa.Column("verified_by", sa.String(length=320), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "scheme", "normalized_hsn_code", "effective_from",
            name="uq_incentive_rate_tenant_scheme_hsn_from",
        ),
    )
    op.create_index("ix_incentive_rates_tenant_id", "incentive_rates", ["tenant_id"])
    op.create_index("ix_incentive_rates_scheme", "incentive_rates", ["scheme"])
    op.create_index("ix_incentive_rates_normalized_hsn_code", "incentive_rates", ["normalized_hsn_code"])
    op.create_index("ix_incentive_rates_digit_level", "incentive_rates", ["digit_level"])
    op.create_index("ix_incentive_rates_source_version", "incentive_rates", ["source_version"])
    op.create_index("ix_incentive_rates_approval_status", "incentive_rates", ["approval_status"])
    op.create_index("ix_incentive_rates_is_active", "incentive_rates", ["is_active"])

    op.create_table(
        "incentive_source_evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("incentive_rate_id", sa.Uuid(), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=True),
        sa.Column("document_title", sa.String(length=512), nullable=True),
        sa.Column("document_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_text_excerpt", sa.Text(), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=True),
        sa.Column("evidence_type", sa.String(length=40), nullable=False),
        sa.Column("confidence_weight", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.ForeignKeyConstraint(["incentive_rate_id"], ["incentive_rates.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_incentive_source_evidence_incentive_rate_id", "incentive_source_evidence", ["incentive_rate_id"])

    op.create_table(
        "incentive_import_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scheme", sa.String(length=40), nullable=True),
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
    op.create_index("ix_incentive_import_jobs_status", "incentive_import_jobs", ["status"])


def downgrade() -> None:
    op.drop_table("incentive_import_jobs")
    op.drop_table("incentive_source_evidence")
    op.drop_table("incentive_rates")
