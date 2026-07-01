"""Import a DGFT RoDTEP Appendix 4R / 4RE schedule PDF into the incentive master.

The 4R/4RE PDFs are clean tables: Entry | Tariff Item | Description | UQC | Rate % | Cap.
Rows import as PENDING (admin approval required) unless --approve is passed.

Usage (from apps/api):
    python -m app.scripts.import_rodtep_4r "<path to Appendix 4R.pdf>" \
        --effective-from 2024-10-10 \
        --source-name "DGFT RoDTEP Appendix 4R (w.e.f. 10.10.2024)" \
        --source-url https://www.dgft.gov.in/CP/?opt=RoDTEP [--scheme rodtep] [--approve]
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

_HEADER_TOKENS = {"tariff item", "(2)", "description of goods"}


def parse_4r_pdf(
    path: Path, *, scheme: str, effective_from: str, source_name: str
) -> list[dict[str, object]]:
    import pdfplumber

    records: list[dict[str, object]] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables() or []:
                for row in table:
                    if not row or len(row) < 6:
                        continue
                    code = (row[1] or "").strip().replace(" ", "")
                    if not re.fullmatch(r"\d{2,8}", code):
                        continue
                    if (row[1] or "").strip().lower() in _HEADER_TOKENS:
                        continue
                    rate = (row[4] or "").strip().replace("%", "").strip()
                    try:
                        float(rate)
                    except ValueError:
                        continue
                    cap = (row[5] or "").strip()
                    records.append(
                        {
                            "scheme": scheme,
                            "hsn_code": code,
                            "product_description": (row[2] or "").replace("\n", " ").strip()[:300],
                            "unit_of_quantity": (row[3] or "").strip() or None,
                            "rate_value": rate,
                            "cap_value": cap or None,
                            "cap_unit": "Rs. per UQC" if cap else None,
                            "effective_from": effective_from,
                            "source_name": source_name,
                        }
                    )
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description="Import a RoDTEP Appendix 4R/4RE PDF.")
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--effective-from", required=True, help="YYYY-MM-DD")
    parser.add_argument("--source-name", required=True)
    parser.add_argument("--source-url", default="https://www.dgft.gov.in/CP/?opt=RoDTEP")
    parser.add_argument("--scheme", default="rodtep")
    parser.add_argument("--approve", action="store_true", help="Approve all imported rows now")
    args = parser.parse_args()

    print("parsing PDF…")
    records = parse_4r_pdf(
        args.pdf,
        scheme=args.scheme,
        effective_from=args.effective_from,
        source_name=args.source_name,
    )
    print(f"parsed {len(records)} rate rows")
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
            scheme=args.scheme,
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
            scheme=args.scheme,
            source_url=args.source_url,
            source_document_title=args.source_name,
            source_version=f"4R-{args.effective_from}",
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
