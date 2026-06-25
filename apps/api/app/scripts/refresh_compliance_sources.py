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
                print(f"organization={organization.slug} store_unavailable error={error}")
                failures += 1
                continue

            for source in store.due_sources(limit=25):
                print(
                    "checking_source "
                    f"organization={organization.slug} source={source.source_url} "
                    f"country={source.country} category={source.category} "
                    f"last_checked_at={source.last_checked_at}"
                )
                try:
                    document = scraper.scrape(source.source_url)
                    snapshot = store.record_source_snapshot(
                        source_url=document.source_url,
                        country=source.country,
                        category=source.category,
                        title=document.title,
                        markdown=document.markdown,
                    )
                    session.commit()
                    refreshed += 1
                    print(
                        "source_checked "
                        f"organization={organization.slug} source={snapshot.source_url} "
                        f"content_hash={snapshot.content_hash} status={snapshot.status} "
                        f"previous_content_hash={snapshot.previous_content_hash} "
                        f"message={snapshot.message}"
                    )
                except ComplianceScraperError as error:
                    session.rollback()
                    failures += 1
                    print(
                        "source_check_failed "
                        f"organization={organization.slug} source={source.source_url} error={error}"
                    )

        print(f"Compliance refresh complete. refreshed={refreshed} failures={failures}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
