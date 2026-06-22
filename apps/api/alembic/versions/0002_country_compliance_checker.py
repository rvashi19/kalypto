"""country compliance checker schema

Revision ID: 0002_country_compliance_checker
Revises: 0001_phase0_foundation
Create Date: 2026-06-22 00:00:00.000000
"""

from __future__ import annotations

import app.models  # noqa: F401
from alembic import op
from app.db.base import Base

revision = "0002_country_compliance_checker"
down_revision = "0001_phase0_foundation"
branch_labels = None
depends_on = None

TABLES = [
    "compliance_countries",
    "product_categories",
    "compliance_requirements",
    "compliance_scrape_runs",
    "compliance_chat_sessions",
    "compliance_chat_messages",
]


def upgrade() -> None:
    bind = op.get_bind()
    for table_name in TABLES:
        Base.metadata.tables[table_name].create(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    for table_name in reversed(TABLES):
        Base.metadata.tables[table_name].drop(bind=bind, checkfirst=True)