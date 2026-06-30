"""incentive source registry + rate review fields

Revision ID: 0011_incentive_sources
Revises: 0010_incentive_finder
Create Date: 2026-06-29 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0011_incentive_sources"
down_revision = "0010_incentive_finder"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "incentive_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=True),
        sa.Column("scheme", sa.String(length=40), nullable=True),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=True),
        sa.Column("source_document_title", sa.String(length=512), nullable=True),
        sa.Column("source_type", sa.String(length=20), nullable=False),
        sa.Column("refresh_interval_days", sa.Integer(), nullable=True),
        sa.Column("last_fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_checksum", sa.String(length=64), nullable=True),
        sa.Column("last_source_version", sa.String(length=80), nullable=True),
        sa.Column("last_status", sa.String(length=20), nullable=False),
        sa.Column("last_records", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=320), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_incentive_sources_tenant_id", "incentive_sources", ["tenant_id"])

    op.add_column("incentive_rates", sa.Column("source_id", sa.Uuid(), nullable=True))
    op.add_column("incentive_rates", sa.Column("review_note", sa.Text(), nullable=True))
    op.create_index("ix_incentive_rates_source_id", "incentive_rates", ["source_id"])
    op.create_foreign_key(
        "fk_incentive_rates_source_id", "incentive_rates", "incentive_sources", ["source_id"], ["id"]
    )


def downgrade() -> None:
    op.drop_constraint("fk_incentive_rates_source_id", "incentive_rates", type_="foreignkey")
    op.drop_index("ix_incentive_rates_source_id", table_name="incentive_rates")
    op.drop_column("incentive_rates", "review_note")
    op.drop_column("incentive_rates", "source_id")
    op.drop_table("incentive_sources")
