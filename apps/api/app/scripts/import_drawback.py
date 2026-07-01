"""Import a CBIC All-Industry-Rates (AIR) Duty Drawback Schedule PDF.

The simplified (post-2020) schedule is a single rate column:
  Tariff Item | Description | Unit | Drawback Rate | Drawback cap per unit
Rates are often set at the 4-digit heading level (the Incentive Finder's parent-
prefix lookup matches those from any 8-digit code). "Nil" imports as 0%.

Rows import as PENDING unless --approve is passed.

Usage (from apps/api):
    python -m app.scripts.import_drawback "<Drawback Schedule.pdf>" \
        --effective-from 2023-10-30 \
        --source-name "CBIC AIR Duty Drawback Schedule (Notif. 77/2023-Cus N.T.)" \
        --source-url https://www.cbic.gov.in/entities/duty-drawback [--approve]
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import IncentiveRate, Organization
from app.services.incentive_import import import_incentive_snapshot
from app.services.incentive_sources import register_source

_ROW = re.compile(
    r"^\s*(\d{2,8})\s+(?:(.*?)\s+)?(Nil|\d{1,3}(?:\.\d+)?\s*%)\s*(\d+(?:\.\d+)?)?\s*$"
)
_UNITS = {"Kg", "Piece", "Pair", "Sqm", "Gross", "Litre", "Tonne", "Set", "Dozen", "1000", "Number"}


def parse_drawback_pdf(
    path: Path, *, effective_from: str, source_name: str
) -> list[dict[str, object]]:
    import pdfplumber

    records: list[dict[str, object]] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            for line in (page.extract_text() or "").splitlines():
                match = _ROW.match(line)
                if not match:
                    continue
                code = match.group(1)
                if len(code) not in (2, 4, 6, 8):
                    continue
                rate = match.group(3).replace(" ", "").replace("%", "")
                rate = "0" if rate.lower() == "nil" else rate
                desc = (match.group(2) or "").strip()
                unit = None
                parts = desc.split()
                if parts and parts[-1] in _UNITS:
                    unit = parts[-1]
                    desc = " ".join(parts[:-1])
                cap = match.group(4)
                records.append(
                    {
                        "scheme": "drawback",
                        "hsn_code": code,
                        "product_description": desc[:300] or None,
                        "unit_of_quantity": unit,
                        "rate_value": rate,
                        "cap_value": cap or None,
                        "cap_unit": "Rs. per unit" if cap else None,
                        "effective_from": effective_from,
                        "source_name": source_name,
                    }
                )
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description="Import a CBIC AIR Drawback Schedule PDF.")
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--effective-from", required=True, help="YYYY-MM-DD")
    parser.add_argument("--source-name", required=True)
    parser.add_argument("--source-url", default="https://www.cbic.gov.in/entities/duty-drawback")
    parser.add_argument("--approve", action="store_true", help="Approve all imported rows now")
    args = parser.parse_args()

    print("parsing PDF…")
    records = parse_drawback_pdf(
        args.pdf, effective_from=args.effective_from, source_name=args.source_name
    )
    print(f"parsed {len(records)} drawback rate rows")
    payload = json.dumps({"records": records}).encode("utf-8")

    session = SessionLocal()
    try:
        org = session.scalars(select(Organization).order_by(Organization.created_at)).first()
        if org is None:
            print("No organization found. Run seed_demo first.")
            return
        source = register_source(
            session=session,
            tenant_id=org.id,
            scheme="drawback",
            source_name=args.source_name,
            source_type="pdf",
            source_url=args.source_url,
            source_document_title=args.source_name,
            refresh_interval_days=None,
            created_by="cli",
        )
        result = import_incentive_snapshot(
            session=session,
            tenant_id=org.id,
            raw_bytes=payload,
            import_type="json",
            source_name=args.source_name,
            scheme="drawback",
            source_url=args.source_url,
            source_document_title=args.source_name,
            source_version=f"dbk-{args.effective_from}",
            source_id=source.id,
            created_by="cli",
        )
        approved = 0
        if args.approve:
            rows = session.scalars(
                select(IncentiveRate).where(IncentiveRate.source_id == source.id)
            ).all()
            now = datetime.now(UTC)
            for r in rows:
                r.approval_status = "approved"
                r.is_active = True
                r.verified_by = "cli"
                r.verified_at = now
            approved = len(rows)
            session.commit()
        job = result.job
        print(
            f"status={job.status} seen={job.records_seen} created={job.records_created} "
            f"updated={job.records_updated} errors={len(result.errors)} approved={approved}"
        )
    finally:
        session.close()


if __name__ == "__main__":
    main()
