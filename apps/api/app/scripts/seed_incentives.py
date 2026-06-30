"""Seed sample incentive/rate records into the demo tenant.

Usage (from apps/api):  python -m app.scripts.seed_incentives
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import Organization
from app.services.incentive_import import import_incentive_snapshot

DEFAULT_CSV = Path(__file__).resolve().with_name("data") / "incentive_sample.csv"


def main() -> None:
    session = SessionLocal()
    try:
        org = session.scalars(select(Organization).order_by(Organization.created_at)).first()
        if org is None:
            print("No organization found. Run seed_demo first.")
            return
        result = import_incentive_snapshot(
            session=session,
            tenant_id=org.id,
            raw_bytes=DEFAULT_CSV.read_bytes(),
            import_type="csv",
            source_name="KALYPTO sample incentive schedules",
            created_by="seed",
        )
        job = result.job
        summary = (
            f"incentives: status={job.status} seen={job.records_seen} "
            f"created={job.records_created} updated={job.records_updated} errors={len(result.errors)}"
        )
    finally:
        session.close()
    print(summary)


if __name__ == "__main__":
    main()
