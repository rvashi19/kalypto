"""Add persisted compliance retrieval retry counters.

Revision ID: 0017_compliance_job_retries
Revises: 0016_full_auth_system
Create Date: 2026-07-03 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0017_compliance_job_retries"
down_revision = "0016_full_auth_system"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "compliance_retrieval_jobs" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("compliance_retrieval_jobs")}
    with op.batch_alter_table("compliance_retrieval_jobs") as batch_op:
        if "retry_count" not in columns:
            batch_op.add_column(
                sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0")
            )
        if "max_retries" not in columns:
            batch_op.add_column(
                sa.Column("max_retries", sa.Integer(), nullable=False, server_default="3")
            )

    if "retry_count" not in columns:
        op.alter_column("compliance_retrieval_jobs", "retry_count", server_default=None)
    if "max_retries" not in columns:
        op.alter_column("compliance_retrieval_jobs", "max_retries", server_default=None)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "compliance_retrieval_jobs" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("compliance_retrieval_jobs")}
    with op.batch_alter_table("compliance_retrieval_jobs") as batch_op:
        if "max_retries" in columns:
            batch_op.drop_column("max_retries")
        if "retry_count" in columns:
            batch_op.drop_column("retry_count")
