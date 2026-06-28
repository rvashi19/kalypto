"""one authoritative row per HSN code

Replaces the (normalized_code, source_version) uniqueness with a single unique
normalized_code, so re-imports from any source upsert in place instead of
creating duplicate rows for the same code.

Revision ID: 0008_hsn_unique_code
Revises: 0007_hsn_finder
Create Date: 2026-06-28 00:00:00.000000
"""

from __future__ import annotations

from alembic import op

revision = "0008_hsn_unique_code"
down_revision = "0007_hsn_finder"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Collapse any pre-existing duplicates (keep the most recently updated row).
    op.execute(
        """
        DELETE FROM hsn_codes a
        USING hsn_codes b
        WHERE a.normalized_code = b.normalized_code
          AND a.updated_at < b.updated_at
        """
    )
    with op.batch_alter_table("hsn_codes") as batch:
        batch.drop_constraint("uq_hsn_codes_norm_version", type_="unique")
    op.drop_index("ix_hsn_codes_normalized_code", table_name="hsn_codes")
    op.create_index(
        "ix_hsn_codes_normalized_code", "hsn_codes", ["normalized_code"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_hsn_codes_normalized_code", table_name="hsn_codes")
    op.create_index("ix_hsn_codes_normalized_code", "hsn_codes", ["normalized_code"])
    with op.batch_alter_table("hsn_codes") as batch:
        batch.create_unique_constraint(
            "uq_hsn_codes_norm_version", ["normalized_code", "source_version"]
        )
