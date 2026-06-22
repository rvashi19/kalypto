from __future__ import annotations

from app.db.session import SessionLocal
from app.models import Organization
from app.services.compliance_scraper import ComplianceScraperError, get_compliance_scraper
from app.services.compliance_store import (
    ComplianceStoreConfigurationError,
    get_compliance_knowledge_store,
)


def main() -> None:
    session = SessionLocal()
    try:
        scraper = get_compliance_scraper()
        organizations = session.query(Organization).all()
        refreshed = 0
        failures = 0
        for organization in organizations:
            try:
                store = get_compliance_knowledge_store(session=session, tenant_id=organization.id)
            except ComplianceStoreConfigurationError as error:
                print(f"{organization.slug}: compliance store unavailable: {error}")
                failures += 1
                continue

            for source in store.due_sources(limit=25):
                try:
                    document = scraper.scrape(source.source_url)
                    snapshot = store.record_source_snapshot(
                        source_url=document.source_url,
                        country=source.country,
                        category=source.category,
                        title=document.title,
                        markdown=document.markdown,
                    )
                    refreshed += 1
                    print(f"{organization.slug}: {source.source_url} -> {snapshot.status}")
                except ComplianceScraperError as error:
                    failures += 1
                    print(f"{organization.slug}: {source.source_url} failed: {error}")

        print(f"Compliance refresh complete. refreshed={refreshed} failures={failures}")
    finally:
        session.close()


if __name__ == "__main__":
    main()