# ruff: noqa: E501
"""Scheduled refresh of registered official sources.

Finds sources whose refresh window (refresh_frequency_days) has elapsed, groups them
by (country, category), and runs one retrieval job per group. Checksum dedup in the
runner means unchanged sources cost nothing (no repeat AI). Designed to be called by
an external scheduler (GitHub Actions) via POST /compliance/refresh-due.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.models import ComplianceRetrievalJob, ComplianceSourceRegistry
from app.services.compliance_retrieval_job import run_retrieval_job


def _is_due(source: ComplianceSourceRegistry, now: datetime) -> bool:
    if source.last_checked_at is None:
        return True
    last = source.last_checked_at
    if last.tzinfo is None:
        last = last.replace(tzinfo=UTC)
    return last < now - timedelta(days=max(1, source.refresh_frequency_days))


def refresh_due_sources(session: Session, *, tenant_id: UUID, limit: int = 25) -> dict:
    """Run retrieval jobs for all due (country, category) groups. Returns a summary."""
    now = datetime.now(UTC)
    sources = session.scalars(
        select(ComplianceSourceRegistry).where(
            ComplianceSourceRegistry.tenant_id == tenant_id,
            ComplianceSourceRegistry.is_active.is_(True),
        )
    ).all()

    # Distinct (country, category) pairs among due sources.
    pairs: set[tuple[str, str]] = set()
    for source in sources:
        if not _is_due(source, now):
            continue
        categories = source.product_categories_json or ["food/agri"]
        for category in categories:
            pairs.add((source.country, category))

    summary = {
        "due_groups": len(pairs),
        "jobs_run": 0,
        "pages_fetched": 0,
        "snapshots_created": 0,
        "requirements_extracted": 0,
        "failures": 0,
    }

    for country, category in sorted(pairs)[:limit]:
        job = ComplianceRetrievalJob(
            tenant_id=tenant_id,
            destination_country=country,
            product_category=category,
            status="queued",
            max_retries=max(0, get_settings().compliance_max_retries),
        )
        session.add(job)
        session.flush()
        run_retrieval_job(session, job_id=job.id, tenant_id=tenant_id, force=False)
        summary["jobs_run"] += 1
        summary["pages_fetched"] += job.pages_fetched
        summary["snapshots_created"] += job.snapshots_created
        summary["requirements_extracted"] += job.requirements_extracted
        if job.status == "failed":
            summary["failures"] += 1

    session.flush()
    return summary
