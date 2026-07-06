# ruff: noqa: E501
"""Add admin workflow fields to compliance source registry

Revision ID: 0019_compliance_source_registry_admin_fields
Revises: 0018_compliance_snapshot_review_queue
Create Date: 2026-07-05 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0019_compliance_source_registry_admin_fields"
down_revision = "0018_compliance_snapshot_review_queue"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = inspector.get_table_names()
    if "compliance_source_registry" not in existing:
        return
    cols = {c["name"] for c in inspector.get_columns("compliance_source_registry")}
    if "authority_level" not in cols:
        op.add_column(
            "compliance_source_registry",
            sa.Column("authority_level", sa.String(40), nullable=False, server_default="official"),
        )
    if "notes" not in cols:
        op.add_column("compliance_source_registry", sa.Column("notes", sa.Text(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "compliance_source_registry" not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns("compliance_source_registry")}
    if "notes" in cols:
        op.drop_column("compliance_source_registry", "notes")
    if "authority_level" in cols:
        op.drop_column("compliance_source_registry", "authority_level")
