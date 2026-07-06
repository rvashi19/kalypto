"""Add auth hardening fields for verification and TOTP

Revision ID: 0015_auth_hardening
Revises: 0014_country_compliance_checker
Create Date: 2026-07-02 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0015_auth_hardening"
down_revision = "0014_country_compliance_checker"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "users" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("users")}
    if "email_verified_at" not in columns:
        op.add_column(
            "users",
            sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.execute(
            "UPDATE users SET email_verified_at = CURRENT_TIMESTAMP "
            "WHERE email_verified_at IS NULL"
        )
    if "two_factor_secret" not in columns:
        op.add_column("users", sa.Column("two_factor_secret", sa.String(64), nullable=True))
    if "two_factor_enabled" not in columns:
        op.add_column(
            "users",
            sa.Column(
                "two_factor_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )
        if bind.dialect.name != "sqlite":
            op.alter_column("users", "two_factor_enabled", server_default=None)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "users" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("users")}
    for column_name in ("two_factor_enabled", "two_factor_secret", "email_verified_at"):
        if column_name in columns:
            op.drop_column("users", column_name)
