# ruff: noqa: E501
"""Country Compliance Checker v1 — source registry, retrieval jobs, check sessions, evidence

Revision ID: 0014_country_compliance_checker
Revises: 0013_document_builder
Create Date: 2026-07-02 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0014_country_compliance_checker"
down_revision = "0013_document_builder"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = inspector.get_table_names()

    # Additive column on existing compliance_requirements (nullable, idempotent).
    if "compliance_requirements" in existing:
        cols = {c["name"] for c in inspector.get_columns("compliance_requirements")}
        if "origin_country" not in cols:
            op.add_column(
                "compliance_requirements",
                sa.Column("origin_country", sa.String(120), nullable=True),
            )
            op.create_index(
                "ix_compliance_requirements_origin_country",
                "compliance_requirements",
                ["origin_country"],
            )

    if "compliance_source_registry" not in existing:
        op.create_table(
            "compliance_source_registry",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("tenant_id", sa.Uuid(), nullable=False),
            sa.Column("country", sa.String(120), nullable=False),
            sa.Column("authority_name", sa.String(255), nullable=False),
            sa.Column("source_name", sa.String(255), nullable=False),
            sa.Column("base_url", sa.String(2048), nullable=False),
            sa.Column("allowed_domains_json", sa.JSON(), nullable=False),
            sa.Column("source_type", sa.String(20), nullable=False, server_default="mixed"),
            sa.Column("product_categories_json", sa.JSON(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("refresh_frequency_days", sa.Integer(), nullable=False, server_default="30"),
            sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["tenant_id"], ["organizations.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_compliance_source_registry_tenant_id", "compliance_source_registry", ["tenant_id"])
        op.create_index("ix_compliance_source_registry_country", "compliance_source_registry", ["country"])
        op.create_index("ix_compliance_source_registry_is_active", "compliance_source_registry", ["is_active"])

    if "compliance_retrieval_jobs" not in existing:
        op.create_table(
            "compliance_retrieval_jobs",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("tenant_id", sa.Uuid(), nullable=False),
            sa.Column("requested_by_user_id", sa.Uuid(), nullable=True),
            sa.Column("origin_country", sa.String(120), nullable=True),
            sa.Column("destination_country", sa.String(120), nullable=False),
            sa.Column("product_category", sa.String(120), nullable=False),
            sa.Column("hsn_code", sa.String(20), nullable=True),
            sa.Column("product_description", sa.Text(), nullable=True),
            sa.Column("status", sa.String(40), nullable=False, server_default="queued"),
            sa.Column("source_registry_ids_json", sa.JSON(), nullable=False),
            sa.Column("pages_fetched", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("snapshots_created", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("requirements_extracted", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["tenant_id"], ["organizations.id"]),
            sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_compliance_retrieval_jobs_tenant_id", "compliance_retrieval_jobs", ["tenant_id"])
        op.create_index("ix_compliance_retrieval_jobs_dest", "compliance_retrieval_jobs", ["destination_country"])
        op.create_index("ix_compliance_retrieval_jobs_category", "compliance_retrieval_jobs", ["product_category"])
        op.create_index("ix_compliance_retrieval_jobs_status", "compliance_retrieval_jobs", ["status"])

    if "compliance_check_sessions" not in existing:
        op.create_table(
            "compliance_check_sessions",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("tenant_id", sa.Uuid(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=True),
            sa.Column("origin_country", sa.String(120), nullable=True),
            sa.Column("destination_country", sa.String(120), nullable=False),
            sa.Column("hsn_code", sa.String(20), nullable=True),
            sa.Column("product_description", sa.Text(), nullable=False),
            sa.Column("product_category", sa.String(120), nullable=False),
            sa.Column("input_facts_json", sa.JSON(), nullable=True),
            sa.Column("missing_questions_json", sa.JSON(), nullable=False),
            sa.Column("answer_summary_json", sa.JSON(), nullable=True),
            sa.Column("source_ids_json", sa.JSON(), nullable=False),
            sa.Column("confidence_label", sa.String(20), nullable=True),
            sa.Column("retrieval_job_id", sa.Uuid(), nullable=True),
            sa.Column("status", sa.String(40), nullable=False, server_default="answered"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["tenant_id"], ["organizations.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["retrieval_job_id"], ["compliance_retrieval_jobs.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_compliance_check_sessions_tenant_id", "compliance_check_sessions", ["tenant_id"])
        op.create_index("ix_compliance_check_sessions_status", "compliance_check_sessions", ["status"])

    if "compliance_requirement_evidence" not in existing:
        op.create_table(
            "compliance_requirement_evidence",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("tenant_id", sa.Uuid(), nullable=False),
            sa.Column("requirement_id", sa.Uuid(), nullable=False),
            sa.Column("source_snapshot_id", sa.Uuid(), nullable=True),
            sa.Column("source_url", sa.String(2048), nullable=False),
            sa.Column("authority_name", sa.String(255), nullable=True),
            sa.Column("evidence_excerpt", sa.Text(), nullable=False),
            sa.Column("page_number", sa.Integer(), nullable=True),
            sa.Column("table_reference", sa.String(255), nullable=True),
            sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("checksum", sa.String(64), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["tenant_id"], ["organizations.id"]),
            sa.ForeignKeyConstraint(["requirement_id"], ["compliance_requirements.id"]),
            sa.ForeignKeyConstraint(["source_snapshot_id"], ["compliance_source_snapshots.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_compliance_requirement_evidence_tenant_id", "compliance_requirement_evidence", ["tenant_id"])
        op.create_index("ix_compliance_requirement_evidence_requirement_id", "compliance_requirement_evidence", ["requirement_id"])


def downgrade() -> None:
    bind = op.get_bind()
    existing = sa.inspect(bind).get_table_names()
    for table in (
        "compliance_requirement_evidence",
        "compliance_check_sessions",
        "compliance_retrieval_jobs",
        "compliance_source_registry",
    ):
        if table in existing:
            op.drop_table(table)
    if "compliance_requirements" in existing:
        cols = {c["name"] for c in sa.inspect(bind).get_columns("compliance_requirements")}
        if "origin_country" in cols:
            op.drop_column("compliance_requirements", "origin_country")
