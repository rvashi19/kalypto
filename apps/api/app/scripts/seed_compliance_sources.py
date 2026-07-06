# ruff: noqa: E501
"""Idempotently seed official compliance sources for one or all tenants.

    python -m app.scripts.seed_compliance_sources                # all organizations
    python -m app.scripts.seed_compliance_sources <org-slug>     # a single organization

Seeds a *limited* curated set of official government/regulatory source registry entries
(India export side, USA, Canada, UK, EU, UAE) marked by country + product category +
refresh frequency. This is NOT full country coverage — it is a vetted starting set.
Re-running never duplicates sources (dedupe on tenant + country + base_url).
"""

from __future__ import annotations

import sys

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import Organization
from app.services.compliance_source_seed import seed_official_sources


def main() -> None:
    slug = sys.argv[1] if len(sys.argv) > 1 else None
    session = SessionLocal()
    try:
        query = select(Organization)
        if slug:
            query = query.where(Organization.slug == slug)
        orgs = list(session.scalars(query).all())
        if not orgs:
            print(f"No organizations found{f' for slug={slug!r}' if slug else ''}.")
            return
        for org in orgs:
            result = seed_official_sources(session, org.id)
            session.commit()
            print(
                f"[{org.slug}] created={result['created']} updated={result['updated']} "
                f"skipped={result['skipped']} total={result['total']}"
            )
    finally:
        session.close()


if __name__ == "__main__":
    main()
