from __future__ import annotations

from datetime import UTC, datetime, timedelta

SHORT_FRESHNESS_CATEGORIES = {"beverages", "food/agri", "dry fruits", "spices"}


def freshness_days(*, category: str, requirement_type: str) -> int:
    if requirement_type == "restriction":
        return 7
    if category in SHORT_FRESHNESS_CATEGORIES:
        return 15
    if category == "textiles":
        return 30
    if requirement_type == "import_document":
        return 60
    return 30


def calculate_expires_at(
    *,
    category: str,
    requirement_type: str,
    last_checked_at: datetime | None,
) -> datetime:
    checked_at = last_checked_at or datetime.now(UTC)
    days = freshness_days(category=category, requirement_type=requirement_type)
    return checked_at + timedelta(days=days)


def is_stale(*, expires_at: datetime | None, now: datetime | None = None) -> bool:
    if expires_at is None:
        return True
    current = now or datetime.now(UTC)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    return expires_at <= current
