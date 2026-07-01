"""verified product -> HSN alias layer

Stores human/agent/LLM-verified product-phrase -> HSN code mappings that search
consults first, so common product searches return the correct code with clean
descriptions even when a scraped source's wording is wrong.

Revision ID: 0009_hsn_product_alias
Revises: 0008_hsn_unique_code
Create Date: 2026-06-28 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0009_hsn_product_alias"
down_revision = "0008_hsn_unique_code"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "hsn_product_aliases" in sa.inspect(op.get_bind()).get_table_names():
        return

    op.create_table(
        "hsn_product_aliases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("term", sa.String(length=160), nullable=False),
        sa.Column("normalized_code", sa.String(length=20), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("confidence", sa.Integer(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("term", name="uq_hsn_product_aliases_term"),
    )
    op.create_index("ix_hsn_product_aliases_term", "hsn_product_aliases", ["term"], unique=True)
    op.create_index(
        "ix_hsn_product_aliases_normalized_code", "hsn_product_aliases", ["normalized_code"]
    )


def downgrade() -> None:
    op.drop_table("hsn_product_aliases")
