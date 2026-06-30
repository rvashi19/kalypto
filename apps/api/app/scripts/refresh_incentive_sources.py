"""Refresh official incentive sources that are due (for a daily cron).

Each source carries its own refresh_interval_days (e.g. 3-4), so running this once
a day re-imports only what is due. Imported rows are pending and still require admin
approval before becoming visible.

Usage (from apps/api):  python -m app.scripts.refresh_incentive_sources
"""

from __future__ import annotations

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import IncentiveSource
from app.services.incentive_sources import IncentiveSourceError, is_due, refresh_source


def main() -> None:
    session = SessionLocal()
    refreshed = 0
    try:
        sources = session.scalars(select(IncentiveSource).where(IncentiveSource.is_active.is_(True))).all()
        for source in sources:
            if not is_due(source):
                continue
            try:
                outcome = refresh_source(session=session, source=source, created_by="scheduler")
                refreshed += 1
                print(f"[{source.source_name}] {outcome.message}")
            except IncentiveSourceError as error:
                source.last_status = "failed"
                session.commit()
                print(f"[{source.source_name}] refresh failed: {error}")
    finally:
        session.close()
    print(f"done: {refreshed} source(s) refreshed")


if __name__ == "__main__":
    main()
