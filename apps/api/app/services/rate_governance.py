"""Shared guardrails for client-facing incentive rate usage."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import RateTable


def as_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def is_rate_approved_and_current(row: RateTable, *, now: datetime | None = None) -> bool:
    current_time = now or datetime.now(UTC)
    if row.review_status != "approved":
        return False
    if row.expires_at is not None and as_aware_utc(row.expires_at) <= current_time:
        return False
    return True


def approved_current_rate_rows(
    *, session: Session, tenant_id: UUID, hsn_code: str | None = None
) -> list[RateTable]:
    rows = session.scalars(
        select(RateTable)
        .where(
            RateTable.tenant_id == tenant_id,
            RateTable.review_status == "approved",
        )
        .order_by(RateTable.effective_date.desc())
    ).all()
    now = datetime.now(UTC)
    current_rows = [row for row in rows if is_rate_approved_and_current(row, now=now)]
    if hsn_code is None:
        return current_rows
    return [row for row in current_rows if hsn_code.startswith(row.hsn)]


def latest_rate_by_scheme(rows: list[RateTable]) -> list[RateTable]:
    latest_by_scheme: dict[str, RateTable] = {}
    for row in sorted(
        rows,
        key=lambda item: (len(item.hsn), item.effective_date),
        reverse=True,
    ):
        latest_by_scheme.setdefault(row.scheme.strip().lower(), row)
    return list(latest_by_scheme.values())
