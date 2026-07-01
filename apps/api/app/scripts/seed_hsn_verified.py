"""Load the curated verified product->HSN mappings into the database.

Usage (from apps/api):
    python -m app.scripts.seed_hsn_verified [path/to/hsn_verified.csv]

Idempotent: re-running updates the mappings and cleans the mapped master rows'
descriptions in place.
"""

from __future__ import annotations

import sys
from pathlib import Path

from app.db.session import SessionLocal
from app.services.hsn_verified import load_verified_aliases

DEFAULT_CSV = Path(__file__).resolve().with_name("data") / "hsn_verified.csv"


def main() -> None:
    csv_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CSV
    raw = csv_path.read_bytes()
    session = SessionLocal()
    try:
        result = load_verified_aliases(session=session, raw_bytes=raw)
    finally:
        session.close()
    print(
        f"verified aliases: {result['aliases']} new | "
        f"codes created: {result['codes_created']} | codes updated: {result['codes_updated']}"
    )


if __name__ == "__main__":
    main()
