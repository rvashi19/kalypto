"""persist export shipment reconciliation discrepancies

Revision ID: 0005_export_reconciliation
Revises: 0004_compliance_source_monitoring
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005_export_reconciliation"
down_revision = "0004_compliance_source_monitoring"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "export_discrepancies" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "export_discrepancies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("shipment_id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.String(120), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("suggested_fix", sa.Text(), nullable=True),
        sa.Column("lock_risk", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("potential_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["shipment_id"], ["export_shipments.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_export_discrepancies_tenant_id", "export_discrepancies", ["tenant_id"])
    op.create_index(
        "ix_export_discrepancies_shipment_id",
        "export_discrepancies",
        ["shipment_id"],
    )


def downgrade() -> None:
    op.drop_table("export_discrepancies")
