"""rate table governance fields

Revision ID: 0006_rate_table_governance
Revises: 0005_export_reconciliation
Create Date: 2026-06-27 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_rate_table_governance"
down_revision = "0005_export_reconciliation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    existing_columns = {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("rate_tables")
    }
    if "source_url" not in existing_columns:
        op.add_column("rate_tables", sa.Column("source_url", sa.String(length=2048), nullable=True))
    if "review_status" not in existing_columns:
        op.add_column(
            "rate_tables",
            sa.Column("review_status", sa.String(length=40), nullable=False, server_default="approved"),
        )
    if "reviewed_by" not in existing_columns:
        op.add_column("rate_tables", sa.Column("reviewed_by", sa.String(length=320), nullable=True))
    if "reviewed_at" not in existing_columns:
        op.add_column("rate_tables", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    if "expires_at" not in existing_columns:
        op.add_column("rate_tables", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
    if "notes" not in existing_columns:
        op.add_column("rate_tables", sa.Column("notes", sa.Text(), nullable=True))


def downgrade() -> None:
    existing_columns = {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("rate_tables")
    }
    for column_name in (
        "notes",
        "expires_at",
        "reviewed_at",
        "reviewed_by",
        "review_status",
        "source_url",
    ):
        if column_name in existing_columns:
            op.drop_column("rate_tables", column_name)
