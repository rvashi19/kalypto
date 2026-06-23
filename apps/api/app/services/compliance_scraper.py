# ruff: noqa: E501
from __future__ import annotations

import html
import ipaddress
import json
import re
import socket
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from app.core.settings import get_settings

MAX_SOURCE_BYTES = 2_000_000
MIN_EXTRACTED_CHARS = 120


class ComplianceScraperError(RuntimeError):
    """Raised when a compliance source cannot be scraped safely."""


@dataclass(frozen=True, slots=True)
class ScrapedSourceDocument:
    source_url: str
    title: str
    markdown: str


class ComplianceScraper(Protocol):
    def scrape(self, source_url: str) -> ScrapedSourceDocument: ...


class _ReadableHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self._skip_depth = 0
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_name = tag.lower()
        if tag_name in {"script", "style", "noscript", "svg", "canvas"}:
            self._skip_depth += 1
        if tag_name == "title":
            self._in_title = True
        if tag_name in {"p", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"}:
            self.text_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag_name = tag.lower()
        if tag_name in {"script", "style", "noscript", "svg", "canvas"} and self._skip_depth:
            self._skip_depth -= 1
        if tag_name == "title":
            self._in_title = False
        if tag_name in {"p", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"}:
            self.text_parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        cleaned = normalize_scraped_text(data)
        if not cleaned:
            return
        if self._in_title:
            self.title_parts.append(cleaned)
        self.text_parts.append(cleaned)

    @property
    def title(self) -> str:
        return normalize_scraped_text(" ".join(self.title_parts)) or "Untitled source"

    @property
    def markdown(self) -> str:
        lines = [
            normalize_scraped_text(line)
            for line in "\n".join(self.text_parts).splitlines()
            if normalize_scraped_text(line)
        ]
        return "\n".join(lines)


def normalize_scraped_text(value: str) -> str:
    decoded = html.unescape(value)
    decoded = re.sub(r"\s+", " ", decoded)
    return decoded.strip()


def html_to_readable_document(*, source_url: str, raw_html: str) -> ScrapedSourceDocument:
    parser = _ReadableHTMLParser()
    parser.feed(raw_html)
    markdown = parser.markdown
    if len(markdown) < MIN_EXTRACTED_CHARS:
        raise ComplianceScraperError(
            "The page was fetched but did not contain enough readable text for review.",
        )
    return ScrapedSourceDocument(
        source_url=source_url,
        title=parser.title,
        markdown=markdown[:100_000],
    )


def validate_public_source_url(source_url: str, *, allow_private: bool) -> None:
    parsed = urlparse(source_url)
    if parsed.scheme not in {"http", "https"}:
        raise ComplianceScraperError("Only http/https source URLs can be scraped.")
    if not parsed.hostname:
        raise ComplianceScraperError("Source URL must include a hostname.")
    if allow_private:
        return
    try:
        addresses = socket.getaddrinfo(parsed.hostname, None)
    except socket.gaierror as error:
        raise ComplianceScraperError(f"Could not resolve source host: {parsed.hostname}") from error

    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise ComplianceScraperError(
                "Private, loopback, link-local, reserved, or multicast source URLs are blocked.",
            )


class ManualReviewScraper:
    def scrape(self, source_url: str) -> ScrapedSourceDocument:
        return ScrapedSourceDocument(
            source_url=source_url,
            title="Manual review required",
            markdown=(
                "No live scraper provider is configured. Configure COMPLIANCE_SCRAPER_PROVIDER=http "
                "or firecrawl, then ingest only human-reviewed structured records."
            ),
        )


class HttpComplianceScraper:
    def __init__(self) -> None:
        self.settings = get_settings()

    def scrape(self, source_url: str) -> ScrapedSourceDocument:
        validate_public_source_url(
            source_url,
            allow_private=self.settings.compliance_allow_private_scrape,
        )
        request = Request(
            source_url,
            method="GET",
            headers={
                "User-Agent": self.settings.compliance_scraper_user_agent,
                "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.5",
            },
        )
        try:
            with urlopen(request, timeout=30) as response:  # noqa: S310
                content_type = response.headers.get("Content-Type", "")
                raw = response.read(MAX_SOURCE_BYTES + 1)
        except HTTPError as error:
            raise ComplianceScraperError(f"Source returned HTTP {error.code}.") from error
        except URLError as error:
            raise ComplianceScraperError(f"Source request failed: {error}") from error

        if len(raw) > MAX_SOURCE_BYTES:
            raise ComplianceScraperError("Source response is too large to scrape safely.")
        if "pdf" in content_type.lower():
            raise ComplianceScraperError(
                "PDF extraction is not supported by the built-in HTTP scraper. Use Firecrawl or manual review.",
            )

        encoding = "utf-8"
        match = re.search(r"charset=([\w.-]+)", content_type, flags=re.IGNORECASE)
        if match:
            encoding = match.group(1)
        text = raw.decode(encoding, errors="replace")
        if "html" in content_type.lower() or "<html" in text[:500].lower():
            return html_to_readable_document(source_url=source_url, raw_html=text)

        cleaned = "\n".join(
            line for line in (normalize_scraped_text(line) for line in text.splitlines()) if line
        )
        if len(cleaned) < MIN_EXTRACTED_CHARS:
            raise ComplianceScraperError(
                "The source was fetched but did not contain enough readable text for review.",
            )
        return ScrapedSourceDocument(
            source_url=source_url,
            title=urlparse(source_url).hostname or "Text source",
            markdown=cleaned[:100_000],
        )


class FirecrawlComplianceScraper:
    endpoint = "https://api.firecrawl.dev/v2/scrape"

    def __init__(self) -> None:
        self.settings = get_settings()

    def scrape(self, source_url: str) -> ScrapedSourceDocument:
        validate_public_source_url(
            source_url,
            allow_private=self.settings.compliance_allow_private_scrape,
        )
        if not self.settings.firecrawl_api_key:
            raise ComplianceScraperError("FIRECRAWL_API_KEY is required for the Firecrawl scraper.")

        payload = json.dumps({"url": source_url, "formats": ["markdown"]}).encode("utf-8")
        request = Request(
            self.endpoint,
            data=payload,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.settings.firecrawl_api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urlopen(request, timeout=90) as response:  # noqa: S310
                raw = response.read().decode("utf-8")
        except (HTTPError, URLError) as error:
            raise ComplianceScraperError(f"Firecrawl request failed: {error}") from error

        body = json.loads(raw)
        data = body.get("data", {})
        metadata = data.get("metadata", {})
        markdown = data.get("markdown") or ""
        if len(markdown) < MIN_EXTRACTED_CHARS:
            raise ComplianceScraperError("Firecrawl returned no usable markdown content.")
        return ScrapedSourceDocument(
            source_url=metadata.get("sourceURL") or source_url,
            title=metadata.get("title") or "Untitled source",
            markdown=markdown[:100_000],
        )


def get_compliance_scraper() -> ComplianceScraper:
    provider = get_settings().compliance_scraper_provider.lower()
    if provider == "firecrawl":
        return FirecrawlComplianceScraper()
    if provider == "http":
        return HttpComplianceScraper()
    return ManualReviewScraper()
