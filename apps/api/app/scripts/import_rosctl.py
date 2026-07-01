"""Import the Ministry of Textiles RoSCTL Schedule (Notif. 14/26/2016-IT, 7.3.2019).

The schedule splits the rebate into Schedule 1 (State levies) and Schedule 2
(Central levies); the combined RoSCTL rate = Schedule 1 + Schedule 2 (caps add too).
Schedules 3 & 4 are the Advance-Authorisation variant and are skipped here.

RoSCTL lines are classified by fabric type (e.g. "610501 Of Cotton"), which do not
map 1:1 to customs 8-digit HSN — the Incentive Finder matches them by 4-digit heading
so an apparel HSN shows the fabric-rate variants. Rows import as PENDING unless --approve.

Usage (from apps/api):
    python -m app.scripts.import_rosctl "<RoSCTL schedule.pdf>" \
        --effective-from 2019-03-07 \
        --source-name "MoT RoSCTL Schedule 1+2 (Notif. 14/26/2016-IT, 7.3.2019)" [--approve]
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

_ROW = re.compile(r"^\s*(\d{4,8})\s+(.*?)\s+(\d{1,2}(?:\.\d+)?)\s+(\d+(?:\.\d+)?)\s*$")
_UNITS = {"Piece", "Kg", "Pair", "Sqm", "Set", "Number", "Gross", "Dozen"}


def parse_rosctl_pdf(
    path: Path, *, effective_from: str, source_name: str
) -> list[dict[str, object]]:
    import pdfplumber

    state: dict[str, tuple[float, float, str]] = {}
    central: dict[str, tuple[float, float]] = {}
    schedule = 0
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            for line in (page.extract_text() or "").splitlines():
                header = re.search(r"Schedule\s*(\d)\s*:", line)
                if header:
                    schedule = int(header.group(1))
                    continue
                if schedule not in (1, 2):
                    continue
                match = _ROW.match(line.strip())
                if not match:
                    continue
                code, desc = match.group(1), match.group(2).strip()
                rate, cap = float(match.group(3)), float(match.group(4))
                if schedule == 1:
                    state[code] = (rate, cap, desc)
                else:
                    central[code] = (rate, cap)

    records: list[dict[str, object]] = []
    for code, (s_rate, s_cap, desc) in state.items():
        c_rate, c_cap = central.get(code, (0.0, 0.0))
        unit = None
        parts = desc.split()
        if parts and parts[-1] in _UNITS:
            unit = parts[-1]
            desc = " ".join(parts[:-1])
        records.append(
            {
                "scheme": "rosctl",
                "hsn_code": code,
                "product_description": desc[:300] or None,
                "unit_of_quantity": unit,
                "rate_value": round(s_rate + c_rate, 2),
                "cap_value": round(s_cap + c_cap, 2) or None,
                "cap_unit": "Rs. per unit" if (s_cap + c_cap) else None,
                "condition_text": f"Combined RoSCTL = State {s_rate}% + Central {c_rate}%.",
                "effective_from": effective_from,
                "source_name": source_name,
            }
        )
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description="Import a RoSCTL Schedule PDF.")
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--effective-from", required=True, help="YYYY-MM-DD")
    parser.add_argument("--source-name", required=True)
    parser.add_argument("--source-url", default="https://texmin.gov.in")
    parser.add_argument("--approve", action="store_true", help="Approve all imported rows now")
    args = parser.parse_args()

    print("parsing PDF…")
    records = parse_rosctl_pdf(
        args.pdf, effective_from=args.effective_from, source_name=args.source_name
    )
    print(f"parsed {len(records)} combined RoSCTL rate rows")
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
            scheme="rosctl",
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
            scheme="rosctl",
            source_url=args.source_url,
            source_document_title=args.source_name,
            source_version=f"rosctl-{args.effective_from}",
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
