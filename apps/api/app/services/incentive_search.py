# ruff: noqa: E501
"""Incentive/rate lookup for an already-selected HSN code.

This module never classifies products or guesses HSN codes — it only takes a code
(exact or a parent prefix) and returns matching incentive records. Normal users see
only approved, active, non-expired rows; admins also see pending/expired.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import HsnCode, IncentiveRate, IncentiveSourceEvidence
from app.services.hsn_normalization import InvalidHsnCodeError, normalize_code

MIN_HSN_DIGITS = 2


@dataclass
class IncentiveMatch:
    row: IncentiveRate
    match_level: str  # exact / prefix
    evidence_count: int


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def is_current(row: IncentiveRate, *, asof: datetime) -> bool:
    if _as_utc(row.effective_from) > asof:
        return False
    if row.effective_to is not None and _as_utc(row.effective_to) <= asof:
        return False
    return True


def is_visible_to_user(row: IncentiveRate, *, asof: datetime) -> bool:
    return row.approval_status == "approved" and row.is_active and is_current(row, asof=asof)


def hsn_exists_in_master(session: Session, normalized: str) -> bool:
    return (
        session.scalar(
            select(func.count())
            .select_from(HsnCode)
            .where(HsnCode.normalized_code == normalized, HsnCode.is_active.is_(True))
        )
        or 0
    ) > 0


def _evidence_counts(session: Session, ids: list[UUID]) -> dict[UUID, int]:
    if not ids:
        return {}
    rows = session.execute(
        select(IncentiveSourceEvidence.incentive_rate_id, func.count())
        .where(IncentiveSourceEvidence.incentive_rate_id.in_(ids))
        .group_by(IncentiveSourceEvidence.incentive_rate_id)
    ).all()
    return {row[0]: row[1] for row in rows}


def search_incentives(
    *,
    session: Session,
    tenant_id: UUID,
    hsn_code: str,
    scheme: str | None = None,
    export_date: datetime | None = None,
    include_unapproved: bool = False,
    limit: int = 50,
) -> list[IncentiveMatch]:
    """Exact-then-parent-prefix incentive lookup. Raises InvalidHsnCodeError on bad input."""
    normalized = normalize_code(hsn_code)
    if len(normalized) < MIN_HSN_DIGITS:
        raise InvalidHsnCodeError(
            f"Enter at least {MIN_HSN_DIGITS} HSN digits (e.g. 12119030)."
        )

    # The query code plus each parent level it falls under.
    prefixes = {normalized} | {normalized[:n] for n in (2, 4, 6, 8) if n <= len(normalized)}
    query = (
        select(IncentiveRate)
        .where(IncentiveRate.normalized_hsn_code.in_(prefixes))
        .where(or_(IncentiveRate.tenant_id == tenant_id, IncentiveRate.tenant_id.is_(None)))
    )
    if scheme and scheme.lower() != "all":
        query = query.where(func.lower(IncentiveRate.scheme) == scheme.lower())
    rows = session.scalars(query).all()

    asof = _as_utc(export_date) if export_date else datetime.now(UTC)
    candidates = [
        row for row in rows if include_unapproved or is_visible_to_user(row, asof=asof)
    ]

    def sort_key(row: IncentiveRate) -> tuple[str, int, datetime]:
        return (row.scheme.lower(), len(row.normalized_hsn_code), _as_utc(row.effective_from))

    candidates.sort(key=sort_key, reverse=True)

    if include_unapproved:
        selected = candidates  # admins see every matching row (pending/expired included)
    else:
        # Normal users: best (most specific, latest) approved row per scheme.
        seen: set[str] = set()
        selected = []
        for row in candidates:
            key = row.scheme.lower()
            if key in seen:
                continue
            seen.add(key)
            selected.append(row)

    selected = selected[:limit]
    evidence = _evidence_counts(session, [row.id for row in selected])
    return [
        IncentiveMatch(
            row=row,
            match_level="exact" if row.normalized_hsn_code == normalized else "prefix",
            evidence_count=evidence.get(row.id, 0),
        )
        for row in selected
    ]
