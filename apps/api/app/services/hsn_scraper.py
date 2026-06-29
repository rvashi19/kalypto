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

import html
import json
import re
import time
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlparse
from urllib.request import Request, urlopen

from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.services.compliance_scraper import validate_public_source_url
from app.services.hsn_import import ImportResult, import_hsn_snapshot
from app.services.rate_limit import rate_limiter

MAX_FILE_BYTES = 25_000_000
OGD_PAGE_SIZE = 1000
OGD_BASE = "https://api.data.gov.in/resource"

EXIMGURU_BASE = "https://www.eximguru.com/hs-codes/"
EXIMGURU_SOURCE = "EximGuru ITC-HS aggregator (secondary/supplementary source)"
_CRAWL_DELAY_SECONDS = 0.4


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


# ── EximGuru connector (private ITC-HS aggregator) ──────────────────────────────
# Official DGFT/CBIC sources remain primary; EximGuru republishes the same public
# ITC-HS schedule and is treated as secondary/supplementary evidence. robots.txt
# allows crawling; requests are spaced by a polite fixed delay.


def _clean_text(raw: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw))).strip()


def _eximguru_get(url: str) -> str:
    settings = get_settings()
    validate_public_source_url(url, allow_private=settings.hsn_scrape_allow_private)
    request = Request(
        url,
        method="GET",
        headers={"User-Agent": _user_agent(), "Accept": "text/html,*/*;q=0.5"},
    )
    try:
        with urlopen(request, timeout=30) as response:  # noqa: S310
            raw = response.read(MAX_FILE_BYTES + 1)
    except HTTPError as error:
        raise HsnScrapeError(f"EximGuru returned HTTP {error.code} for {url}.") from error
    except URLError as error:
        raise HsnScrapeError(f"EximGuru request failed for {url}: {error}") from error
    time.sleep(_CRAWL_DELAY_SECONDS)
    return raw.decode("utf-8", errors="replace")


def _chapter_links() -> dict[int, str]:
    """Map chapter number -> chapter page URL from the EximGuru index."""
    html_text = _eximguru_get(EXIMGURU_BASE + "default.aspx")
    links: dict[int, str] = {}
    for href in re.findall(r'hs-codes/((\d{2})-chapter-[0-9a-z\-]+\.aspx)', html_text, re.I):
        path, chapter = href
        links.setdefault(int(chapter), urljoin(EXIMGURU_BASE, path))
    return links


def _parse_rows(html_text: str) -> list[tuple[str, str, str | None]]:
    """Return (code, description, heading_href|None) for code-like table rows."""
    out: list[tuple[str, str, str | None]] = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", html_text, re.S | re.I):
        cells = [_clean_text(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S | re.I)]
        cells = [c for c in cells if c]
        if len(cells) < 2:
            continue
        code = cells[0].replace(".", "").replace(" ", "")
        if not re.fullmatch(r"\d{2,8}", code):
            continue
        href_match = re.search(r'href="((?:\d{4})[^"]*\.aspx)"', row, re.I)
        href = urljoin(EXIMGURU_BASE, href_match.group(1)) if href_match else None
        out.append((code, cells[1], href))
    return out


def fetch_eximguru(
    *,
    session: Session,
    chapters: list[int] | None,
    source_version: str,
    max_records: int | None = None,
    created_by: str | None = None,
) -> ScrapeOutcome:
    """Crawl EximGuru chapter -> heading -> leaf pages and import the ITC-HS rows."""
    settings = get_settings()
    rate_limiter.enforce(bucket="hsn-scrape", key="eximguru", limit=20, window_seconds=60)
    limit_total = max_records or settings.hsn_scrape_max_records

    index = _chapter_links()
    targets = sorted(set(chapters)) if chapters else sorted(index)
    records: dict[str, dict[str, object]] = {}

    for chapter in targets:
        chapter_url = index.get(chapter)
        if not chapter_url:
            continue
        chapter_html = _eximguru_get(chapter_url)
        for code, desc, heading_url in _parse_rows(chapter_html):
            if len(code) == 4:
                heading_desc = re.sub(r"^harmonised codes of\s*", "", desc, flags=re.I).strip()
                records.setdefault(code, {"code": code, "description": heading_desc or desc})
                if heading_url and len(records) < limit_total:
                    _collect_heading(heading_url, records, limit_total, heading_desc)
            if len(records) >= limit_total:
                break
        if len(records) >= limit_total:
            break

    if not records:
        raise HsnScrapeError(
            "EximGuru crawl returned no rows. The site structure may have changed."
        )

    payload = json.dumps({"records": list(records.values())}).encode("utf-8")
    result = import_hsn_snapshot(
        session=session,
        raw_bytes=payload,
        import_type="json",
        source_name=EXIMGURU_SOURCE,
        source_url=EXIMGURU_BASE,
        source_document_title="ITC-HS schedule (via EximGuru)",
        source_document_date=None,
        source_version=source_version,
        created_by=created_by,
    )
    return ScrapeOutcome(
        result=result,
        records_fetched=len(records),
        source_label=f"eximguru:{','.join(str(c) for c in targets[:8])}",
    )


def _compose_description(heading_desc: str, leaf: str) -> str:
    """Build a faithful description from the unambiguous heading + the leaf cell.

    The heading is prepended only when the leaf is a bare qualifier (no internal
    context of its own), so "Of cotton" under "Men's shirts" becomes
    "Men's shirts: Of cotton" while an already-qualified leaf is left as-is.
    """
    head = heading_desc.strip().rstrip(":").strip()
    leaf = leaf.strip().rstrip(":").strip()
    if not leaf:
        return head
    if not head:
        return leaf
    if head.lower() in leaf.lower() or leaf.lower() in head.lower():
        return leaf if len(leaf) >= len(head) else head
    bare = ":" not in leaf and len(leaf.split()) <= 4
    return f"{head}: {leaf}" if bare else leaf


# ── Single-code live lookup (used for cross-verification) ───────────────────────

_CHAPTER_INDEX_CACHE: dict[int, str] = {}
_CHAPTER_HEADINGS_CACHE: dict[int, dict[str, tuple[str | None, str]]] = {}
_HEADING_CODES_CACHE: dict[str, dict[str, str]] = {}


def _chapter_links_cached() -> dict[int, str]:
    if not _CHAPTER_INDEX_CACHE:
        _CHAPTER_INDEX_CACHE.update(_chapter_links())
    return _CHAPTER_INDEX_CACHE


def _chapter_headings(chapter: int) -> dict[str, tuple[str | None, str]]:
    """{heading4: (heading_url|None, heading_desc)} for a chapter, cached."""
    if chapter in _CHAPTER_HEADINGS_CACHE:
        return _CHAPTER_HEADINGS_CACHE[chapter]
    url = _chapter_links_cached().get(chapter)
    headings: dict[str, tuple[str | None, str]] = {}
    if url:
        for code, desc, heading_url in _parse_rows(_eximguru_get(url)):
            if len(code) == 4:
                clean = re.sub(r"^harmonised codes of\s*", "", desc, flags=re.I).strip()
                headings[code] = (heading_url, clean or desc)
    _CHAPTER_HEADINGS_CACHE[chapter] = headings
    return headings


def _heading_codes(heading_url: str, heading_desc: str) -> dict[str, str]:
    if heading_url in _HEADING_CODES_CACHE:
        return _HEADING_CODES_CACHE[heading_url]
    codes: dict[str, str] = {}
    for code, desc, _ in _parse_rows(_eximguru_get(heading_url)):
        codes[code] = desc if len(code) == 4 else _compose_description(heading_desc, desc)
    _HEADING_CODES_CACHE[heading_url] = codes
    return codes


def fetch_code_description(code: str) -> tuple[str | None, bool]:
    """Live authentic lookup of one code on EximGuru. Returns (description, exact_match)."""
    digits = "".join(c for c in (code or "") if c.isdigit())
    if len(digits) < 2:
        return None, False
    try:
        chapter = int(digits[:2])
    except ValueError:
        return None, False
    headings = _chapter_headings(chapter)
    if len(digits) == 4:
        if digits in headings:
            return headings[digits][1], True
        return None, False
    heading4 = digits[:4]
    if heading4 not in headings:
        return None, False
    heading_url, heading_desc = headings[heading4]
    if len(digits) == 2:
        return heading_desc, True
    if not heading_url:
        return heading_desc, False
    leaf_map = _heading_codes(heading_url, heading_desc)
    if digits in leaf_map:
        return leaf_map[digits], True
    return heading_desc, False


def _collect_heading(
    heading_url: str,
    records: dict[str, dict[str, object]],
    limit_total: int,
    heading_desc: str,
) -> None:
    heading_html = _eximguru_get(heading_url)
    for code, desc, _ in _parse_rows(heading_html):
        if len(code) == 4:
            records.setdefault(code, {"code": code, "description": desc.rstrip(":").strip()})
        else:
            records.setdefault(code, {"code": code, "description": _compose_description(heading_desc, desc)})
        if len(records) >= limit_total:
            return
