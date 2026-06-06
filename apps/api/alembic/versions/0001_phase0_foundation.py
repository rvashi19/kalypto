"""phase 0 foundation schema

Revision ID: 0001_phase0_foundation
Revises:
Create Date: 2026-06-06 00:00:00.000000
"""

from __future__ import annotations

from alembic import op

import app.models  # noqa: F401
from app.db.base import Base

# revision identifiers, used by Alembic.
revision = "0001_phase0_foundation"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
