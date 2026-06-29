"""Seed the 2-digit ITC-HS chapter index into the HSN master.

Usage (from apps/api):  python -m app.scripts.seed_hsn_chapters
"""

from __future__ import annotations

from app.db.session import SessionLocal
from app.services.hsn_chapters import seed_chapters


def main() -> None:
    session = SessionLocal()
    try:
        result = seed_chapters(session=session)
    finally:
        session.close()
    print(
        f"chapters: seen={result['seen']} created={result['created']} updated={result['updated']}"
    )


if __name__ == "__main__":
    main()
