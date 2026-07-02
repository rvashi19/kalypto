"""Cross-load HSN codes from incentive_rates into hsn_codes.

For every unique code in the Incentive Finder (RoDTEP / Drawback / RoSCTL) that is
not yet present in the HSN master, this script inserts a lightweight row so users
can search for those codes in the HSN Finder.

Idempotent: codes already in hsn_codes are skipped.

Usage (from apps/api):
    python -m app.scripts.crossload_incentive_hsn [--dry-run]
"""

from __future__ import annotations

import argparse
import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.hsn import HsnCode
from app.models.incentive import IncentiveRate
from app.services.hsn_normalization import (
    chapter_code,
    digit_level,
    heading_code,
    is_valid_level,
    parent_code,
    subheading_code,
)

_SOURCE_NAME = "Incentive Finder crossload (RoDTEP/Drawback/RoSCTL)"
_SOURCE_VERSION = "incentive-crossload-v1"


def _best_description(candidates: list[str | None]) -> str:
    """Return the longest non-empty description, or a placeholder."""
    best = ""
    for d in candidates:
        if d and len(d) > len(best):
            best = d
    return best or "—"


def run(dry_run: bool = False) -> None:
    session = SessionLocal()
    try:
        # --- collect all incentive codes, grouped by normalized_hsn_code ---
        print("Reading incentive_rates…")
        rate_rows = session.execute(
            select(
                IncentiveRate.normalized_hsn_code,
                IncentiveRate.hsn_code,
                IncentiveRate.product_description,
            ).order_by(IncentiveRate.normalized_hsn_code)
        ).all()

        codes_map: dict[str, tuple[str, list[str | None]]] = {}
        for norm, raw, desc in rate_rows:
            if not norm or not is_valid_level(norm):
                continue
            if norm not in codes_map:
                codes_map[norm] = (raw, [desc])
            else:
                codes_map[norm][1].append(desc)

        print(f"  {len(codes_map)} unique HSN codes in incentive_rates")

        # --- fetch already-existing normalized codes from hsn_codes ---
        existing: set[str] = set(
            session.scalars(select(HsnCode.normalized_code)).all()
        )
        print(f"  {len(existing)} codes already in hsn_codes")

        missing = {k: v for k, v in codes_map.items() if k not in existing}
        print(f"  {len(missing)} codes to insert")

        if dry_run:
            for norm in sorted(missing)[:20]:
                raw, descs = missing[norm]
                print(f"  DRY-RUN  {norm}  {_best_description(descs)[:60]}")
            if len(missing) > 20:
                print(f"  … and {len(missing) - 20} more")
            print("Dry-run complete — no rows written.")
            return

        now = datetime.now(UTC)
        inserted = 0
        for norm, (raw, descs) in missing.items():
            level = digit_level(norm)
            row = HsnCode(
                id=uuid.uuid4(),
                code=raw or norm,
                normalized_code=norm,
                digit_level=level,
                description=_best_description(descs),
                chapter_code=chapter_code(norm),
                heading_code=heading_code(norm),
                subheading_code=subheading_code(norm),
                parent_code=parent_code(norm),
                source_name=_SOURCE_NAME,
                source_version=_SOURCE_VERSION,
                is_active=True,
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            inserted += 1
            if inserted % 1000 == 0:
                session.flush()
                print(f"  … flushed {inserted}")

        session.commit()
        print(f"Done. Inserted {inserted} new HSN codes from incentive data.")
    finally:
        session.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Cross-load incentive HSN codes into hsn_codes.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be inserted without writing anything.",
    )
    args = parser.parse_args()
    run(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
