# ruff: noqa: E501
"""Admin-triggered, rate-limited, source-versioned HSN master scraper.

Two official-source connectors, both feeding the same idempotent import pipeline
(`import_hsn_snapshot`) so every fetch produces an audited HsnImportJob + source
evidence and never creates duplicate rows:

1. OGD connector — data.gov.in (Open Government Data Platform of India) REST API.
   Official, machine-readable, ToS-friendly. Needs a free api.data.gov.in key.
2. Official-file connector — downloads a direct CSV/XLSX/JSON snapshot published on
   a government domain (e.g. a DGFT/CBIC ITC-HS export file) and imports it.

This is never invoked during normal user search; it only runs when an admin asks.
Live HTML scraping of SPA portals (DGFT) is intentionally avoided as unreliable —
prefer the OGD API or a published snapshot file.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.services.compliance_scraper import validate_public_source_url
from app.services.hsn_import import ImportResult, import_hsn_snapshot
from app.services.rate_limit import rate_limiter

MAX_FILE_BYTES = 25_000_000
OGD_PAGE_SIZE = 1000
OGD_BASE = "https://api.data.gov.in/resource"


class HsnScrapeError(RuntimeError):
    """Raised when an official HSN source cannot be fetched safely."""


@dataclass(slots=True)
class ScrapeOutcome:
    result: ImportResult
    records_fetched: int
    source_label: str


def _enforce_interval(host: str) -> None:
    """Polite rate limit: cap scrape runs per host per minute and add a small delay."""
    settings = get_settings()
    rate_limiter.enforce(bucket="hsn-scrape", key=host, limit=10, window_seconds=60)
    if settings.hsn_scrape_min_interval_seconds > 0:
        time.sleep(min(settings.hsn_scrape_min_interval_seconds, 5))


def _user_agent() -> str:
    return get_settings().hsn_scrape_user_agent


def fetch_official_file(
    *,
    session: Session,
    url: str,
    source_name: str,
    source_version: str | None,
    source_document_title: str | None = None,
    source_document_date: str | None = None,
    import_type: str | None = None,
    created_by: str | None = None,
) -> ScrapeOutcome:
    """Download a published official snapshot file and import it idempotently."""
    settings = get_settings()
    validate_public_source_url(url, allow_private=settings.hsn_scrape_allow_private)
    _enforce_interval(urlparse(url).hostname or "unknown")

    request = Request(
        url,
        method="GET",
        headers={"User-Agent": _user_agent(), "Accept": "text/csv,application/json,*/*;q=0.5"},
    )
    try:
        with urlopen(request, timeout=60) as response:  # noqa: S310
            content_type = response.headers.get("Content-Type", "")
            raw = response.read(MAX_FILE_BYTES + 1)
    except HTTPError as error:
        raise HsnScrapeError(f"Official source returned HTTP {error.code}.") from error
    except URLError as error:
        raise HsnScrapeError(f"Official source request failed: {error}") from error

    if len(raw) > MAX_FILE_BYTES:
        raise HsnScrapeError("Official source file is too large to import safely.")

    resolved_type = (import_type or _infer_type(url, content_type)).lower()
    if resolved_type not in {"csv", "json", "xlsx"}:
        raise HsnScrapeError(
            f"Unsupported official file type '{resolved_type}'. Provide a CSV, XLSX, or JSON snapshot."
        )

    result = import_hsn_snapshot(
        session=session,
        raw_bytes=raw,
        import_type=resolved_type,
        source_name=source_name,
        source_url=url,
        source_document_title=source_document_title,
        source_document_date=source_document_date,
        source_version=source_version,
        created_by=created_by,
    )
    return ScrapeOutcome(result=result, records_fetched=result.job.records_seen, source_label=url)


def _infer_type(url: str, content_type: str) -> str:
    lowered = url.lower()
    if lowered.endswith(".csv") or "csv" in content_type:
        return "csv"
    if lowered.endswith(".xlsx") or "sheet" in content_type or "excel" in content_type:
        return "xlsx"
    if lowered.endswith(".json") or "json" in content_type:
        return "json"
    return "csv"


def fetch_ogd_records(
    *,
    session: Session,
    resource_id: str,
    source_version: str | None,
    api_key: str | None = None,
    max_records: int | None = None,
    source_name: str = "data.gov.in (Open Government Data Platform, India)",
    source_document_title: str | None = None,
    source_document_date: str | None = None,
    created_by: str | None = None,
) -> ScrapeOutcome:
    """Fetch HSN rows from a data.gov.in resource and import them idempotently.

    Field names vary by resource; the import pipeline's column-alias logic maps
    common code/description headers, so records are passed through as JSON.
    """
    settings = get_settings()
    key = api_key or settings.data_gov_in_api_key
    if not key:
        raise HsnScrapeError(
            "DATA_GOV_IN_API_KEY is required for the data.gov.in connector. "
            "Register a free key at https://data.gov.in and set it in the environment."
        )
    limit_total = max_records or settings.hsn_scrape_max_records
    resource_url = f"{OGD_BASE}/{resource_id}"
    validate_public_source_url(resource_url, allow_private=settings.hsn_scrape_allow_private)

    records: list[dict[str, object]] = []
    offset = 0
    while len(records) < limit_total:
        _enforce_interval("api.data.gov.in")
        page = min(OGD_PAGE_SIZE, limit_total - len(records))
        query = urlencode(
            {"api-key": key, "format": "json", "limit": page, "offset": offset}
        )
        request = Request(
            f"{resource_url}?{query}",
            method="GET",
            headers={"User-Agent": _user_agent(), "Accept": "application/json"},
        )
        try:
            with urlopen(request, timeout=60) as response:  # noqa: S310
                body = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            raise HsnScrapeError(f"data.gov.in returned HTTP {error.code}.") from error
        except URLError as error:
            raise HsnScrapeError(f"data.gov.in request failed: {error}") from error

        if body.get("status") == "error":
            raise HsnScrapeError(
                f"data.gov.in error: {body.get('message', 'unknown')}. "
                "Check the resource id and that the dataset exposes HSN code/description fields."
            )
        page_records = body.get("records") or []
        if not page_records:
            break
        records.extend(page_records)
        offset += len(page_records)
        if len(page_records) < page:
            break

    if not records:
        raise HsnScrapeError("data.gov.in returned no records for this resource.")

    payload = json.dumps({"records": records}).encode("utf-8")
    result = import_hsn_snapshot(
        session=session,
        raw_bytes=payload,
        import_type="json",
        source_name=source_name,
        source_url=f"https://data.gov.in/resource/{resource_id}",
        source_document_title=source_document_title,
        source_document_date=source_document_date,
        source_version=source_version,
        created_by=created_by,
    )
    return ScrapeOutcome(result=result, records_fetched=len(records), source_label=resource_id)
