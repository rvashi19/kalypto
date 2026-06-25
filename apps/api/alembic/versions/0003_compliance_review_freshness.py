"""compliance review and freshness fields

Revision ID: 0003_compliance_review_freshness
Revises: 0003_country_compliance_checker
Create Date: 2026-06-23 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_compliance_review_freshness"
down_revision = "0003_country_compliance_checker"
branch_labels = None
depends_on = None

TABLE_NAME = "compliance_requirements"


def _existing_columns() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {column["name"] for column in inspector.get_columns(TABLE_NAME)}


def _add_column_if_missing(name: str, column: sa.Column) -> None:
    if name not in _existing_columns():
        op.add_column(TABLE_NAME, column)


def upgrade() -> None:
    _add_column_if_missing("last_checked_at", sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True))
    _add_column_if_missing("expires_at", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
    _add_column_if_missing(
        "review_status",
        sa.Column("review_status", sa.String(length=40), nullable=False, server_default="approved"),
    )
    _add_column_if_missing("reviewed_by", sa.Column("reviewed_by", sa.String(length=255), nullable=True))
    _add_column_if_missing("reviewed_at", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    _add_column_if_missing("notes", sa.Column("notes", sa.Text(), nullable=True))
    _add_column_if_missing(
        "unresolved_questions",
        sa.Column("unresolved_questions", sa.JSON(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    existing = _existing_columns()
    for name in [
        "unresolved_questions",
        "notes",
        "reviewed_at",
        "reviewed_by",
        "review_status",
        "expires_at",
        "last_checked_at",
    ]:
        if name in existing:
            op.drop_column(TABLE_NAME, name)
