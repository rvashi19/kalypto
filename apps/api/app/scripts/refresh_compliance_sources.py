from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import ComplianceScrapeRun, Organization
from app.services.compliance_scraper import ComplianceScraperError, get_compliance_scraper
from app.services.compliance_store import (
    ComplianceStoreConfigurationError,
    get_compliance_knowledge_store,
)


@dataclass(frozen=True, slots=True)
class RefreshSummary:
    organizations: int
    sources_checked: int
    unchanged: int
    changed: int
    failed: int


def refresh_due_sources(*, limit_per_org: int = 25) -> RefreshSummary:
    scraper = get_compliance_scraper()
    session = SessionLocal()
    organizations = 0
    sources_checked = 0
    unchanged = 0
    changed = 0
    failed = 0
    try:
        for organization in session.scalars(select(Organization).order_by(Organization.name)).all():
            organizations += 1
            store = get_compliance_knowledge_store(session=session, tenant_id=organization.id)
            for source in store.due_sources(limit=limit_per_org):
                sources_checked += 1
                run = ComplianceScrapeRun(
                    tenant_id=organization.id,
                    source_url=source.source_url,
                    country=source.country,
                    category=source.category,
                    status="running",
                    records_found=0,
                    errors=None,
                )
                session.add(run)
                session.flush()
                try:
                    document = scraper.scrape(source.source_url)
                    snapshot = store.record_source_snapshot(
                        source_url=document.source_url,
                        country=source.country,
                        category=source.category,
                        title=document.title,
                        markdown=document.markdown,
                    )
                    run.status = snapshot.status
                    if snapshot.status == "needs_review":
                        changed += 1
                    else:
                        unchanged += 1
                except (ComplianceScraperError, ComplianceStoreConfigurationError) as error:
                    failed += 1
                    run.status = "failed"
                    run.errors = {"message": str(error)}
                run.completed_at = datetime.now(UTC)
                session.commit()
    finally:
        session.close()
    return RefreshSummary(
        organizations=organizations,
        sources_checked=sources_checked,
        unchanged=unchanged,
        changed=changed,
        failed=failed,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh due compliance source snapshots.")
    parser.add_argument("--limit-per-org", type=int, default=25)
    args = parser.parse_args()
    summary = refresh_due_sources(limit_per_org=max(1, args.limit_per_org))
    print(
        "organizations={organizations} sources_checked={sources_checked} unchanged={unchanged} "
        "changed={changed} failed={failed}".format(**asdict(summary)),
    )


if __name__ == "__main__":
    main()
