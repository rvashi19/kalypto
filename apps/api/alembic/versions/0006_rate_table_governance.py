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
    op.add_column("rate_tables", sa.Column("source_url", sa.String(length=2048), nullable=True))
    op.add_column(
        "rate_tables",
        sa.Column("review_status", sa.String(length=40), nullable=False, server_default="approved"),
    )
    op.add_column("rate_tables", sa.Column("reviewed_by", sa.String(length=320), nullable=True))
    op.add_column("rate_tables", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("rate_tables", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("rate_tables", sa.Column("notes", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("rate_tables", "notes")
    op.drop_column("rate_tables", "expires_at")
    op.drop_column("rate_tables", "reviewed_at")
    op.drop_column("rate_tables", "reviewed_by")
    op.drop_column("rate_tables", "review_status")
    op.drop_column("rate_tables", "source_url")
