"""landed cost / export quote calculations

Revision ID: 0012_export_quote
Revises: 0011_incentive_sources
Create Date: 2026-06-30 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0012_export_quote"
down_revision = "0011_incentive_sources"
branch_labels = None
depends_on = None

_M = sa.Numeric(16, 2)
_R = sa.Numeric(12, 4)
_MONEY_COLS = [
    "loading_charges", "local_transportation", "packaging_cost", "cfs_charges",
    "terminal_handling_charges", "customs_clearance_charges", "local_transit_charges",
    "seal_charges", "bill_of_lading_charges", "cha_charges", "phytosanitary_certificate_charges",
    "fumigation_charges", "vgm_charges", "misc_origin_charges", "ecgc_premium",
    "general_insurance", "bank_transaction_charges", "onsite_inspection_charges", "freight_cost",
    "destination_handling_charges", "other_destination_charges", "commission",
    "exporter_cost_of_goods", "exporter_overheads", "incentive_amount", "fob_value",
    "cfr_value", "cif_value", "total_landed_cost", "gross_exporter_realization",
    "net_exporter_realization", "exporter_margin_amount",
]
_RATE_COLS = [
    "fob_per_unit", "cfr_per_unit", "cif_per_unit", "landed_cost_per_unit",
    "net_realization_per_unit", "exporter_margin_percent",
]


def upgrade() -> None:
    columns = [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("quote_number", sa.String(length=80), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("buyer_name", sa.String(length=255), nullable=True),
        sa.Column("buyer_country", sa.String(length=120), nullable=True),
        sa.Column("seller_country", sa.String(length=120), nullable=True),
        sa.Column("origin_city_or_place", sa.String(length=160), nullable=True),
        sa.Column("port_of_loading", sa.String(length=160), nullable=True),
        sa.Column("port_of_discharge", sa.String(length=160), nullable=True),
        sa.Column("final_destination", sa.String(length=160), nullable=True),
        sa.Column("incoterm", sa.String(length=8), nullable=False),
        sa.Column("incoterms_version", sa.String(length=12), nullable=False),
        sa.Column("quote_currency", sa.String(length=10), nullable=False),
        sa.Column("hsn_code", sa.String(length=20), nullable=True),
        sa.Column("product_description", sa.Text(), nullable=True),
        sa.Column("packaging_description", sa.String(length=255), nullable=True),
        sa.Column("quantity", sa.Numeric(16, 4), nullable=False),
        sa.Column("unit", sa.String(length=30), nullable=True),
        sa.Column("unit_price", _R, nullable=False),
        sa.Column("product_value", _M, nullable=True),
        sa.Column("target_profit_per_unit", _R, nullable=True),
        sa.Column("target_profit_total", _M, nullable=True),
        sa.Column("import_duty_rate", _R, nullable=False),
        sa.Column("import_duty_amount", _M, nullable=True),
        sa.Column("destination_tax_rate", _R, nullable=False),
        sa.Column("destination_tax_amount", _M, nullable=True),
        sa.Column("fx_rate_to_inr", _R, nullable=True),
        sa.Column("incentive_details_json", sa.JSON(), nullable=True),
        sa.Column("assumptions_json", sa.JSON(), nullable=True),
        sa.Column("warnings_json", sa.JSON(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("calculation_version", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]
    columns += [sa.Column(name, _M, nullable=False, server_default="0") for name in _MONEY_COLS]
    columns += [sa.Column(name, _R, nullable=False, server_default="0") for name in _RATE_COLS]
    op.create_table(
        "export_quote_calculations",
        *columns,
        sa.ForeignKeyConstraint(["tenant_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_export_quote_calculations_tenant_id", "export_quote_calculations", ["tenant_id"])
    op.create_index("ix_export_quote_calculations_user_id", "export_quote_calculations", ["user_id"])


def downgrade() -> None:
    op.drop_table("export_quote_calculations")
