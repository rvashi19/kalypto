"""Admin CLI to scrape an official HSN source into the master.

data.gov.in (Open Government Data Platform) connector:
    python -m app.scripts.scrape_hsn ogd --resource-id <id> \
        --source-version itchs-2024 [--api-key KEY] [--max-records 20000]
    (or set DATA_GOV_IN_API_KEY in the environment)

Official snapshot-file connector (direct CSV/XLSX/JSON URL on a gov domain):
    python -m app.scripts.scrape_hsn file --url https://<gov-domain>/itc-hs.csv \
        --source-name "DGFT ITC(HS) 2024" --source-version itchs-2024

Idempotent: re-running upserts without creating duplicate rows.
"""

from __future__ import annotations

import argparse

from app.db.session import SessionLocal
from app.services.hsn_scraper import HsnScrapeError, fetch_official_file, fetch_ogd_records


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape an official HSN source.")
    sub = parser.add_subparsers(dest="source", required=True)

    ogd = sub.add_parser("ogd", help="data.gov.in REST API connector")
    ogd.add_argument("--resource-id", required=True)
    ogd.add_argument("--source-version", required=True)
    ogd.add_argument("--api-key", default=None)
    ogd.add_argument("--max-records", type=int, default=None)
    ogd.add_argument("--source-name", default="data.gov.in (Open Government Data Platform, India)")
    ogd.add_argument("--source-document-title", default=None)
    ogd.add_argument("--source-document-date", default=None)

    fil = sub.add_parser("file", help="Direct official snapshot file URL connector")
    fil.add_argument("--url", required=True)
    fil.add_argument("--source-name", required=True)
    fil.add_argument("--source-version", required=True)
    fil.add_argument("--import-type", default=None, choices=["csv", "xlsx", "json"])
    fil.add_argument("--source-document-title", default=None)
    fil.add_argument("--source-document-date", default=None)

    args = parser.parse_args()
    session = SessionLocal()
    try:
        if args.source == "ogd":
            outcome = fetch_ogd_records(
                session=session,
                resource_id=args.resource_id,
                source_version=args.source_version,
                api_key=args.api_key,
                max_records=args.max_records,
                source_name=args.source_name,
                source_document_title=args.source_document_title,
                source_document_date=args.source_document_date,
                created_by="cli",
            )
        else:
            outcome = fetch_official_file(
                session=session,
                url=args.url,
                source_name=args.source_name,
                source_version=args.source_version,
                import_type=args.import_type,
                source_document_title=args.source_document_title,
                source_document_date=args.source_document_date,
                created_by="cli",
            )
    except HsnScrapeError as error:
        print(f"scrape failed: {error}")
        raise SystemExit(1) from error
    finally:
        session.close()

    job = outcome.result.job
    print(
        f"status={job.status} fetched={outcome.records_fetched} seen={job.records_seen} "
        f"created={job.records_created} updated={job.records_updated} "
        f"errors={len(outcome.result.errors)}"
    )


if __name__ == "__main__":
    main()
