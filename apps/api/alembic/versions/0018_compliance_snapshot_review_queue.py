# ruff: noqa: E501
"""Richer snapshot metadata + dedicated compliance review queue

Revision ID: 0018_compliance_snapshot_review_queue
Revises: 0017_compliance_job_retries
Create Date: 2026-07-05 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0018_compliance_snapshot_review_queue"
down_revision = "0017_compliance_job_retries"
branch_labels = None
depends_on = None


_SNAPSHOT_COLUMNS = [
    ("source_registry_id", sa.Uuid(), True),
    ("final_url", sa.String(2048), True),
    ("source_type", sa.String(20), True),
    ("http_status", sa.Integer(), True),
    ("parser_used", sa.String(40), True),
    ("parser_status", sa.String(40), True),
    ("raw_storage_key", sa.String(512), True),
    ("extracted_text_storage_key", sa.String(512), True),
    ("error_message", sa.Text(), True),
]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = inspector.get_table_names()

    if "compliance_source_snapshots" in existing:
        cols = {c["name"] for c in inspector.get_columns("compliance_source_snapshots")}
        for name, col_type, nullable in _SNAPSHOT_COLUMNS:
            if name not in cols:
                op.add_column(
                    "compliance_source_snapshots",
                    sa.Column(name, col_type, nullable=nullable),
                )
        if "source_registry_id" not in cols:
            op.create_index(
                "ix_compliance_source_snapshots_source_registry_id",
                "compliance_source_snapshots",
                ["source_registry_id"],
            )

    if "compliance_review_queue" not in existing:
        op.create_table(
            "compliance_review_queue",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("tenant_id", sa.Uuid(), nullable=False),
            sa.Column("requirement_id", sa.Uuid(), nullable=False),
            sa.Column("assigned_to", sa.Uuid(), nullable=True),
            sa.Column("status", sa.String(40), nullable=False, server_default="pending"),
            sa.Column("reviewer_notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["tenant_id"], ["organizations.id"]),
            sa.ForeignKeyConstraint(["requirement_id"], ["compliance_requirements.id"]),
            sa.ForeignKeyConstraint(["assigned_to"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_compliance_review_queue_tenant_id", "compliance_review_queue", ["tenant_id"])
        op.create_index("ix_compliance_review_queue_requirement_id", "compliance_review_queue", ["requirement_id"])
        op.create_index("ix_compliance_review_queue_status", "compliance_review_queue", ["status"])


def downgrade() -> None:
    bind = op.get_bind()
    existing = sa.inspect(bind).get_table_names()
    if "compliance_review_queue" in existing:
        op.drop_table("compliance_review_queue")
    if "compliance_source_snapshots" in existing:
        cols = {c["name"] for c in sa.inspect(bind).get_columns("compliance_source_snapshots")}
        for name, _type, _nullable in reversed(_SNAPSHOT_COLUMNS):
            if name in cols:
                op.drop_column("compliance_source_snapshots", name)
