"""compliance source monitoring tables

Revision ID: 0004_compliance_source_monitoring
Revises: 0003_compliance_review_freshness
Create Date: 2026-06-23 00:00:00.000000
"""

from __future__ import annotations

import app.models  # noqa: F401
from alembic import op
from app.db.base import Base

revision = "0004_compliance_source_monitoring"
down_revision = "0003_compliance_review_freshness"
branch_labels = None
depends_on = None

TABLES = [
    "compliance_source_snapshots",
    "compliance_source_changes",
]


def upgrade() -> None:
    bind = op.get_bind()
    for table_name in TABLES:
        Base.metadata.tables[table_name].create(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    for table_name in reversed(TABLES):
        Base.metadata.tables[table_name].drop(bind=bind, checkfirst=True)
