# ruff: noqa: E501
"""Registry of official incentive-rate sources and their (re)import.

A source points at an official DGFT/CBIC/MoT schedule file (CSV/XLSX/PDF). Refresh
downloads it, imports rows as pending (admin-approval required), and tracks
checksum/version/last-fetched so a scheduled job can refresh only what is due.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.models import IncentiveSource
from app.services.compliance_scraper import validate_public_source_url
from app.services.incentive_import import IncentiveImportResult, import_incentive_snapshot

MAX_FILE_BYTES = 30_000_000


class IncentiveSourceError(RuntimeError):
    pass


@dataclass
class RefreshOutcome:
    source: IncentiveSource
    result: IncentiveImportResult | None
    message: str


def register_source(
    *,
    session: Session,
    tenant_id: UUID | None,
    scheme: str | None,
    source_name: str,
    source_type: str,
    source_url: str | None = None,
    source_document_title: str | None = None,
    refresh_interval_days: int | None = None,
    created_by: str | None = None,
) -> IncentiveSource:
    source = IncentiveSource(
        tenant_id=tenant_id,
        scheme=(scheme or None),
        source_name=source_name,
        source_url=source_url,
        source_document_title=source_document_title,
        source_type=source_type.lower(),
        refresh_interval_days=refresh_interval_days,
        last_status="registered",
        is_active=True,
        created_by=created_by,
    )
    session.add(source)
    session.commit()
    session.refresh(source)
    return source


def list_sources(*, session: Session, tenant_id: UUID) -> list[IncentiveSource]:
    return list(
        session.scalars(
            select(IncentiveSource)
            .where(or_(IncentiveSource.tenant_id == tenant_id, IncentiveSource.tenant_id.is_(None)))
            .order_by(IncentiveSource.created_at.desc())
        ).all()
    )


def is_due(source: IncentiveSource, *, now: datetime | None = None) -> bool:
    if not (source.is_active and source.source_url and source.refresh_interval_days):
        return False
    if source.last_fetched_at is None:
        return True
    now = now or datetime.now(UTC)
    last = source.last_fetched_at
    if last.tzinfo is None:
        last = last.replace(tzinfo=UTC)
    return last + timedelta(days=source.refresh_interval_days) <= now


def _download(url: str) -> bytes:
    settings = get_settings()
    validate_public_source_url(url, allow_private=settings.hsn_scrape_allow_private)
    request = Request(
        url,
        method="GET",
        headers={"User-Agent": settings.hsn_scrape_user_agent, "Accept": "*/*"},
    )
    try:
        with urlopen(request, timeout=60) as response:  # noqa: S310
            raw = response.read(MAX_FILE_BYTES + 1)
    except HTTPError as error:
        raise IncentiveSourceError(f"Source returned HTTP {error.code}.") from error
    except URLError as error:
        raise IncentiveSourceError(f"Source request failed: {error}") from error
    if len(raw) > MAX_FILE_BYTES:
        raise IncentiveSourceError("Source file is too large to import safely.")
    return cast(bytes, raw)


def refresh_source(*, session: Session, source: IncentiveSource, created_by: str | None = None) -> RefreshOutcome:
    """Re-fetch a configured source URL and import its rows as pending."""
    if not source.source_url:
        raise IncentiveSourceError("This source has no URL configured; upload the file instead.")
    raw = _download(source.source_url)
    version = f"auto-{datetime.now(UTC):%Y%m%d-%H%M}"
    result = import_incentive_snapshot(
        session=session,
        tenant_id=source.tenant_id,
        raw_bytes=raw,
        import_type=source.source_type,
        source_name=source.source_name,
        scheme=source.scheme,
        source_url=source.source_url,
        source_document_title=source.source_document_title,
        source_version=version,
        source_id=source.id,
        created_by=created_by,
        commit=False,
    )
    source.last_fetched_at = datetime.now(UTC)
    source.last_checksum = result.job.checksum
    source.last_source_version = version
    source.last_status = result.job.status
    source.last_records = result.job.records_seen
    session.commit()
    created = result.job.records_created
    updated = result.job.records_updated
    return RefreshOutcome(
        source=source,
        result=result,
        message=(
            f"Imported {created} new and updated {updated} rate(s) as pending — "
            f"approve them before they become visible. Host: {urlparse(source.source_url).hostname}."
        ),
    )
