"""Add OTP, refresh token, and OAuth account auth tables.

Revision ID: 0016_full_auth_system
Revises: 0015_auth_hardening
Create Date: 2026-07-02 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0016_full_auth_system"
down_revision = "0015_auth_hardening"
branch_labels = None
depends_on = None


USER_ROLE = postgresql.ENUM("USER", "ADMIN", name="userrole", create_type=False)
USER_STATUS = postgresql.ENUM(
    "PENDING_VERIFICATION",
    "ACTIVE",
    "DISABLED",
    name="userstatus",
    create_type=False,
)
AUTH_PROVIDER_PRIMARY = postgresql.ENUM(
    "PASSWORD",
    "GOOGLE",
    "MIXED",
    name="authproviderprimary",
    create_type=False,
)
AUTH_OTP_PURPOSE = postgresql.ENUM(
    "EMAIL_VERIFICATION",
    "PASSWORD_RESET",
    "LOGIN_OTP",
    name="authotppurpose",
    create_type=False,
)
OAUTH_PROVIDER = postgresql.ENUM("GOOGLE", name="oauthprovider", create_type=False)


def _create_enums(bind: sa.Connection) -> None:
    if bind.dialect.name == "postgresql":
        for enum in (
            USER_ROLE,
            USER_STATUS,
            AUTH_PROVIDER_PRIMARY,
            AUTH_OTP_PURPOSE,
            OAUTH_PROVIDER,
        ):
            enum.create(bind, checkfirst=True)


def _drop_enums(bind: sa.Connection) -> None:
    if bind.dialect.name == "postgresql":
        for enum in (
            OAUTH_PROVIDER,
            AUTH_OTP_PURPOSE,
            AUTH_PROVIDER_PRIMARY,
            USER_STATUS,
            USER_ROLE,
        ):
            enum.drop(bind, checkfirst=True)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    _create_enums(bind)

    if "users" in tables:
        columns = {column["name"] for column in inspector.get_columns("users")}
        with op.batch_alter_table("users") as batch_op:
            if "password_hash" in columns:
                batch_op.alter_column(
                    "password_hash",
                    existing_type=sa.String(length=512),
                    nullable=True,
                )
            if "company_name" not in columns:
                batch_op.add_column(sa.Column("company_name", sa.String(length=255), nullable=True))
            if "country" not in columns:
                batch_op.add_column(sa.Column("country", sa.String(length=120), nullable=True))
            if "avatar_url" not in columns:
                batch_op.add_column(sa.Column("avatar_url", sa.String(length=2048), nullable=True))
            if "role" not in columns:
                batch_op.add_column(
                    sa.Column("role", USER_ROLE, nullable=False, server_default="USER")
                )
            if "status" not in columns:
                batch_op.add_column(
                    sa.Column("status", USER_STATUS, nullable=False, server_default="ACTIVE")
                )
            if "auth_provider_primary" not in columns:
                batch_op.add_column(
                    sa.Column(
                        "auth_provider_primary",
                        AUTH_PROVIDER_PRIMARY,
                        nullable=False,
                        server_default="PASSWORD",
                    )
                )

        inspector = sa.inspect(bind)
        columns = {column["name"] for column in inspector.get_columns("users")}
        if bind.dialect.name != "sqlite" and "role" in columns:
            op.alter_column("users", "role", server_default=None)
        if bind.dialect.name != "sqlite" and "status" in columns:
            op.alter_column("users", "status", server_default=None)
        if bind.dialect.name != "sqlite" and "auth_provider_primary" in columns:
            op.alter_column("users", "auth_provider_primary", server_default=None)

    tables = set(sa.inspect(bind).get_table_names())
    if "auth_otps" not in tables:
        op.create_table(
            "auth_otps",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=True),
            sa.Column("email", sa.String(length=320), nullable=False),
            sa.Column("purpose", AUTH_OTP_PURPOSE, nullable=False),
            sa.Column("otp_hash", sa.String(length=512), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("attempts", sa.Integer(), nullable=False),
            sa.Column("max_attempts", sa.Integer(), nullable=False),
            sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_auth_otps_email", "auth_otps", ["email"])

    if "refresh_tokens" not in tables:
        op.create_table(
            "refresh_tokens",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("tenant_id", sa.Uuid(), nullable=True),
            sa.Column("token_hash", sa.String(length=128), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["tenant_id"], ["organizations.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
        op.create_index("ix_refresh_tokens_tenant_id", "refresh_tokens", ["tenant_id"])
        op.create_index(
            "ix_refresh_tokens_token_hash",
            "refresh_tokens",
            ["token_hash"],
            unique=True,
        )

    if "oauth_accounts" not in tables:
        op.create_table(
            "oauth_accounts",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("provider", OAUTH_PROVIDER, nullable=False),
            sa.Column("provider_user_id", sa.String(length=255), nullable=False),
            sa.Column("provider_email", sa.String(length=320), nullable=False),
            sa.Column("email_verified", sa.Boolean(), nullable=False),
            sa.Column("raw_profile_json", sa.JSON(), nullable=True),
            sa.Column(
                "linked_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("provider", "provider_user_id", name="uq_oauth_provider_user"),
        )
        op.create_index("ix_oauth_accounts_user_id", "oauth_accounts", ["user_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    for table in ("oauth_accounts", "refresh_tokens", "auth_otps"):
        if table in tables:
            op.drop_table(table)

    inspector = sa.inspect(bind)
    if "users" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("users")}
        with op.batch_alter_table("users") as batch_op:
            for column_name in (
                "auth_provider_primary",
                "status",
                "role",
                "avatar_url",
                "country",
                "company_name",
            ):
                if column_name in columns:
                    batch_op.drop_column(column_name)
            if "password_hash" in columns:
                batch_op.alter_column(
                    "password_hash",
                    existing_type=sa.String(length=512),
                    nullable=False,
                )

    _drop_enums(bind)
