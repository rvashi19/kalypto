# ruff: noqa: E501
"""SourceRetriever abstraction for the Country Compliance Checker.

A clean adapter layer over fetching + text extraction for official sources. Reuses the
existing whitelist/SSRF-guarded scraper for HTML/PDF and adds XLSX/CSV support via the
existing openpyxl/csv tooling. Every adapter returns a uniform `RetrievalResult` so the
retrieval job can store rich snapshot metadata.

Only official (whitelisted) domains are ever fetched — the guard lives in the shared
scraper helpers (`_assert_hop_allowed`) and is applied before every network read.
"""

from __future__ import annotations

import csv
import hashlib
import io
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, build_opener

from app.core.settings import get_settings
from app.services.compliance_scraper import (
    MAX_SOURCE_BYTES,
    ComplianceScraperError,
    ScrapedSourceDocument,
    _assert_hop_allowed,
    _NoFollowRedirectHandler,
    get_compliance_scraper,
    html_to_readable_document,
    normalize_scraped_text,
    pdf_to_readable_document,
)


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    source_url: str
    final_url: str
    source_type: str  # html / pdf / xlsx / csv / markdown / text
    source_title: str
    extracted_text: str
    checksum: str
    http_status: int
    retrieved_at: datetime
    parser_used: str
    raw_bytes: bytes | None = None
    raw_storage_key: str | None = None
    extracted_text_storage_key: str | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _checksum(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def _detect_source_type(source_url: str, declared: str | None) -> str:
    path = urlparse(source_url).path.lower()
    if path.endswith(".pdf"):
        return "pdf"
    if path.endswith(".xlsx") or path.endswith(".xls"):
        return "xlsx"
    if path.endswith(".csv"):
        return "csv"
    if declared and declared in {"html", "pdf", "xlsx", "csv"}:
        return declared
    return "html"


# ── Pure extractors (network-free; unit-testable with raw bytes) ─────────────

def extract_xlsx(raw: bytes, *, source_url: str) -> tuple[str, str]:
    """Return (title, normalized table text) from XLSX bytes using openpyxl."""
    import openpyxl  # noqa: PLC0415

    wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    lines: list[str] = []
    for sheet in wb.worksheets:
        lines.append(f"# Sheet: {sheet.title}")
        for row in sheet.iter_rows(values_only=True):
            cells = [normalize_scraped_text(str(c)) for c in row if c is not None and str(c).strip()]
            if cells:
                lines.append(" | ".join(cells))
    wb.close()
    text = "\n".join(lines).strip()
    title = urlparse(source_url).path.rsplit("/", 1)[-1] or "XLSX source"
    return title, text


def extract_csv(raw: bytes, *, source_url: str) -> tuple[str, str]:
    """Return (title, normalized table text) from CSV bytes (utf-8/utf-8-sig/latin-1)."""
    text_content: str | None = None
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            text_content = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if text_content is None:
        text_content = raw.decode("utf-8", errors="replace")
    reader = csv.reader(io.StringIO(text_content))
    lines = [
        " | ".join(normalize_scraped_text(c) for c in row if c.strip())
        for row in reader
        if any(cell.strip() for cell in row)
    ]
    text = "\n".join(lines).strip()
    title = urlparse(source_url).path.rsplit("/", 1)[-1] or "CSV source"
    return title, text


# ── Byte fetch with whitelist + SSRF guard (bounded redirects) ───────────────

def _fetch_bytes(source_url: str, *, allowed_domains: list[str] | None, timeout: int) -> tuple[bytes, str, int]:
    """Fetch raw bytes for XLSX/CSV. Returns (raw, final_url, http_status)."""
    settings = get_settings()
    opener = build_opener(_NoFollowRedirectHandler)
    current = source_url
    for _hop in range(6):
        _assert_hop_allowed(
            current,
            allow_private=settings.compliance_allow_private_scrape,
            allowed_domains=allowed_domains,
        )
        request = Request(current, method="GET", headers={"User-Agent": settings.compliance_scraper_user_agent})
        try:
            with opener.open(request, timeout=timeout) as response:  # noqa: S310
                raw = response.read(MAX_SOURCE_BYTES + 1)
                status = getattr(response, "status", 200) or 200
                if len(raw) > MAX_SOURCE_BYTES:
                    raise ComplianceScraperError("Source response is too large to fetch safely.")
                return raw, current, int(status)
        except HTTPError as error:
            if error.code in (301, 302, 303, 307, 308):
                location = error.headers.get("Location") if error.headers else None
                if not location:
                    raise ComplianceScraperError("Redirect without Location header.") from error
                from urllib.parse import urljoin
                current = urljoin(current, location)
                continue
            raise ComplianceScraperError(f"Source returned HTTP {error.code}.") from error
        except URLError as error:
            raise ComplianceScraperError(f"Source request failed: {error}") from error
    raise ComplianceScraperError("Source exceeded the redirect limit.")


# ── Adapters ─────────────────────────────────────────────────────────────────

class SourceRetriever(Protocol):
    parser_name: str

    def can_handle(self, source_type: str) -> bool: ...

    def fetch(self, source_url: str, *, allowed_domains: list[str] | None, timeout: int) -> RetrievalResult: ...


class HttpSourceRetriever:
    """Handles HTML + PDF by delegating to the existing whitelist/SSRF-guarded scraper."""

    parser_name = "http"

    def can_handle(self, source_type: str) -> bool:
        return source_type in {"html", "pdf"}

    def fetch(self, source_url: str, *, allowed_domains: list[str] | None, timeout: int) -> RetrievalResult:
        scraper = get_compliance_scraper()
        doc: ScrapedSourceDocument = scraper.scrape(source_url, allowed_domains=allowed_domains)
        stype = "pdf" if urlparse(doc.source_url).path.lower().endswith(".pdf") else "html"
        return RetrievalResult(
            source_url=source_url,
            final_url=doc.source_url,
            source_type=stype,
            source_title=doc.title,
            extracted_text=doc.markdown,
            checksum=_checksum(doc.markdown),
            http_status=200,
            retrieved_at=datetime.now(UTC),
            parser_used="pdfplumber" if stype == "pdf" else "html_text",
        )


class SpreadsheetRetriever:
    """Handles XLSX + CSV via openpyxl / stdlib csv."""

    parser_name = "spreadsheet"

    def can_handle(self, source_type: str) -> bool:
        return source_type in {"xlsx", "csv"}

    def fetch(self, source_url: str, *, allowed_domains: list[str] | None, timeout: int) -> RetrievalResult:
        source_type = _detect_source_type(source_url, None)
        raw, final_url, status = _fetch_bytes(source_url, allowed_domains=allowed_domains, timeout=timeout)
        if source_type == "xlsx":
            title, text = extract_xlsx(raw, source_url=final_url)
            parser = "openpyxl"
        else:
            title, text = extract_csv(raw, source_url=final_url)
            parser = "csv"
        if not text:
            raise ComplianceScraperError(f"{source_type.upper()} parsed but contained no readable rows.")
        return RetrievalResult(
            source_url=source_url,
            final_url=final_url,
            source_type=source_type,
            source_title=title,
            extracted_text=text[:200_000],
            checksum=_checksum(text),
            http_status=status,
            retrieved_at=datetime.now(UTC),
            parser_used=parser,
            raw_bytes=raw,
        )


_ADAPTERS: list[SourceRetriever] = [HttpSourceRetriever(), SpreadsheetRetriever()]


def get_retriever_for(source_type: str) -> SourceRetriever:
    for adapter in _ADAPTERS:
        if adapter.can_handle(source_type):
            return adapter
    raise ComplianceScraperError(f"No retriever adapter handles source_type={source_type!r}.")


def retrieve_source(
    source_url: str,
    *,
    declared_source_type: str | None = None,
    allowed_domains: list[str] | None = None,
    timeout: int | None = None,
) -> RetrievalResult:
    """Fetch + extract an official source, dispatching to the right adapter."""
    source_type = _detect_source_type(source_url, declared_source_type)
    timeout = timeout or get_settings().compliance_fetch_timeout_seconds
    adapter = get_retriever_for(source_type)
    return adapter.fetch(source_url, allowed_domains=allowed_domains, timeout=timeout)


# expose reusable helpers
__all__ = [
    "RetrievalResult",
    "SourceRetriever",
    "HttpSourceRetriever",
    "SpreadsheetRetriever",
    "extract_xlsx",
    "extract_csv",
    "retrieve_source",
    "get_retriever_for",
    "html_to_readable_document",
    "pdf_to_readable_document",
]
