"""Local CLI import of an official HSN/ITC(HS) snapshot file.

Usage (from apps/api):
    python -m app.scripts.import_hsn <file> --source-name "DGFT ITC(HS) 2022" \
        --source-url https://www.dgft.gov.in/CP/... --source-version itchs-2022 \
        [--source-document-title "..."] [--source-document-date 2022-01-01] [--type csv]

File type is inferred from the extension when --type is omitted (csv/json/xlsx).
This script is idempotent: re-running it upserts rows without creating duplicates.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from app.db.session import SessionLocal
from app.services.hsn_import import import_hsn_snapshot


def main() -> None:
    parser = argparse.ArgumentParser(description="Import an official HSN snapshot file.")
    parser.add_argument("file", type=Path)
    parser.add_argument("--source-name", required=True)
    parser.add_argument("--source-url", default=None)
    parser.add_argument("--source-document-title", default=None)
    parser.add_argument("--source-document-date", default=None, help="YYYY-MM-DD")
    parser.add_argument("--source-version", default=None)
    parser.add_argument("--type", dest="import_type", default=None, choices=["csv", "json", "xlsx"])
    args = parser.parse_args()

    import_type = args.import_type or args.file.suffix.lstrip(".").lower()
    raw_bytes = args.file.read_bytes()

    session = SessionLocal()
    try:
        result = import_hsn_snapshot(
            session=session,
            raw_bytes=raw_bytes,
            import_type=import_type,
            source_name=args.source_name,
            source_url=args.source_url,
            source_document_title=args.source_document_title,
            source_document_date=args.source_document_date,
            source_version=args.source_version,
            created_by="cli",
        )
    finally:
        session.close()

    job = result.job
    print(
        f"status={job.status} seen={job.records_seen} "
        f"created={job.records_created} updated={job.records_updated} "
        f"errors={len(result.errors)}"
    )
    for error in result.errors[:20]:
        print(f"  row {error['row']}: {error['message']}")


if __name__ == "__main__":
    main()
