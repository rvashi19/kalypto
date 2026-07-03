# ruff: noqa: E501
from __future__ import annotations

import html
import ipaddress
import json
import re
import socket
from dataclasses import dataclass
from html.parser import HTMLParser
from io import BytesIO
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen

from app.core.settings import get_settings
from app.services.compliance_whitelist import is_domain_allowed

MAX_SOURCE_BYTES = 2_000_000
MIN_EXTRACTED_CHARS = 120
MAX_REDIRECTS = 5


class _NoFollowRedirectHandler(HTTPRedirectHandler):
    """Blocks urllib's automatic redirect following so each hop can be re-validated
    (SSRF + official-domain whitelist) before it is fetched. Returning None here makes
    urllib raise HTTPError for the 3xx instead of silently following it."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        return None


class ComplianceScraperError(RuntimeError):
    """Raised when a compliance source cannot be scraped safely."""


@dataclass(frozen=True, slots=True)
class ScrapedSourceDocument:
    source_url: str
    title: str
    markdown: str


class ComplianceScraper(Protocol):
    def scrape(
        self, source_url: str, *, allowed_domains: list[str] | None = None
    ) -> ScrapedSourceDocument:
        """Fetch a source. When allowed_domains is not None, the official-domain
        whitelist is enforced on the initial URL and every redirect hop."""
        ...


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


def pdf_to_readable_document(*, source_url: str, raw_pdf: bytes) -> ScrapedSourceDocument:
    try:
        import pdfplumber  # noqa: PLC0415
    except ImportError as error:
        raise ComplianceScraperError(
            "PDF extraction requires pdfplumber. Install the API requirements first.",
        ) from error

    text_parts: list[str] = []
    try:
        with pdfplumber.open(BytesIO(raw_pdf)) as pdf:
            for page_number, page in enumerate(pdf.pages, start=1):
                text = page.extract_text(x_tolerance=1, y_tolerance=3) or ""
                cleaned = "\n".join(
                    line
                    for line in (normalize_scraped_text(line) for line in text.splitlines())
                    if line
                )
                if cleaned:
                    text_parts.append(f"Page {page_number}\n{cleaned}")
    except Exception as error:  # pragma: no cover - pdfplumber raises varied parser errors
        raise ComplianceScraperError(f"PDF extraction failed: {error}") from error

    markdown = "\n\n".join(text_parts).strip()
    if len(markdown) < MIN_EXTRACTED_CHARS:
        raise ComplianceScraperError(
            "The PDF was fetched but did not contain enough extractable text for review.",
        )
    title = urlparse(source_url).path.rsplit("/", maxsplit=1)[-1] or "PDF source"
    return ScrapedSourceDocument(
        source_url=source_url,
        title=title,
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
    def scrape(
        self, source_url: str, *, allowed_domains: list[str] | None = None
    ) -> ScrapedSourceDocument:
        return ScrapedSourceDocument(
            source_url=source_url,
            title="Manual review required",
            markdown=(
                "No live scraper provider is configured. Configure COMPLIANCE_SCRAPER_PROVIDER=http "
                "or firecrawl, then ingest only human-reviewed structured records."
            ),
        )


def _assert_hop_allowed(url: str, *, allow_private: bool, allowed_domains: list[str] | None) -> None:
    """Re-validate SSRF + (optional) official-domain whitelist for a URL before fetching it."""
    validate_public_source_url(url, allow_private=allow_private)
    if allowed_domains is not None and not is_domain_allowed(url, allowed_domains):
        raise ComplianceScraperError(
            f"Refused redirect to non-whitelisted domain: {urlparse(url).hostname!r}. "
            "Only official government/regulatory sources are allowed."
        )


class HttpComplianceScraper:
    def __init__(self) -> None:
        self.settings = get_settings()
        # Opener that does NOT auto-follow redirects; we follow them manually so
        # each hop is re-checked against the SSRF guard and the domain whitelist.
        self._opener = build_opener(_NoFollowRedirectHandler)

    def scrape(
        self, source_url: str, *, allowed_domains: list[str] | None = None
    ) -> ScrapedSourceDocument:
        current = source_url
        raw = b""
        content_type = ""
        final_url = source_url
        for _hop in range(MAX_REDIRECTS + 1):
            # Validate BEFORE every fetch — covers the initial URL and each redirect target.
            _assert_hop_allowed(
                current,
                allow_private=self.settings.compliance_allow_private_scrape,
                allowed_domains=allowed_domains,
            )
            request = Request(
                current,
                method="GET",
                headers={
                    "User-Agent": self.settings.compliance_scraper_user_agent,
                    "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.5",
                },
            )
            try:
                with self._opener.open(
                    request,
                    timeout=max(1, self.settings.compliance_fetch_timeout_seconds),
                ) as response:  # noqa: S310
                    content_type = response.headers.get("Content-Type", "")
                    raw = response.read(MAX_SOURCE_BYTES + 1)
                    final_url = current
                break
            except HTTPError as error:
                if error.code in (301, 302, 303, 307, 308):
                    location = error.headers.get("Location") if error.headers else None
                    if not location:
                        raise ComplianceScraperError(
                            "Source returned a redirect without a Location header."
                        ) from error
                    current = urljoin(current, location)
                    continue
                raise ComplianceScraperError(f"Source returned HTTP {error.code}.") from error
            except URLError as error:
                raise ComplianceScraperError(f"Source request failed: {error}") from error
        else:
            raise ComplianceScraperError(
                f"Source exceeded the redirect limit ({MAX_REDIRECTS} hops)."
            )

        if len(raw) > MAX_SOURCE_BYTES:
            raise ComplianceScraperError("Source response is too large to scrape safely.")
        parsed = urlparse(final_url)
        if "pdf" in content_type.lower() or parsed.path.lower().endswith(".pdf"):
            return pdf_to_readable_document(source_url=final_url, raw_pdf=raw)

        encoding = "utf-8"
        match = re.search(r"charset=([\w.-]+)", content_type, flags=re.IGNORECASE)
        if match:
            encoding = match.group(1)
        text = raw.decode(encoding, errors="replace")
        if "html" in content_type.lower() or "<html" in text[:500].lower():
            return html_to_readable_document(source_url=final_url, raw_html=text)

        cleaned = "\n".join(
            line for line in (normalize_scraped_text(line) for line in text.splitlines()) if line
        )
        if len(cleaned) < MIN_EXTRACTED_CHARS:
            raise ComplianceScraperError(
                "The source was fetched but did not contain enough readable text for review.",
            )
        return ScrapedSourceDocument(
            source_url=final_url,
            title=urlparse(final_url).hostname or "Text source",
            markdown=cleaned[:100_000],
        )


class FirecrawlComplianceScraper:
    endpoint = "https://api.firecrawl.dev/v2/scrape"

    def __init__(self) -> None:
        self.settings = get_settings()

    def scrape(
        self, source_url: str, *, allowed_domains: list[str] | None = None
    ) -> ScrapedSourceDocument:
        _assert_hop_allowed(
            source_url,
            allow_private=self.settings.compliance_allow_private_scrape,
            allowed_domains=allowed_domains,
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
            with urlopen(
                request,
                timeout=max(1, self.settings.compliance_fetch_timeout_seconds),
            ) as response:  # noqa: S310
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


class ScraplingComplianceScraper:
    """Optional provider backed by Scrapling (https://github.com/D4Vinci/Scrapling).

    Use only for whitelisted official sources whose content our plain HTTP scraper
    cannot read (e.g. JavaScript-rendered pages). Intentionally **stealth-disabled**:
    we never use StealthyFetcher, CAPTCHA solving, or fingerprint spoofing — CCR
    fetches official government sources politely, never evades bot detection.

    Scrapling is an optional dependency (not in requirements.txt). Install with
    `pip install "scrapling[fetchers]"` (adds browsers) when a source needs it.
    PDFs are delegated to the HTTP + pdfplumber path.
    """

    def __init__(self) -> None:
        self.settings = get_settings()

    def scrape(
        self, source_url: str, *, allowed_domains: list[str] | None = None
    ) -> ScrapedSourceDocument:
        # Enforce SSRF + whitelist on the requested URL BEFORE importing/fetching.
        _assert_hop_allowed(
            source_url,
            allow_private=self.settings.compliance_allow_private_scrape,
            allowed_domains=allowed_domains,
        )
        # PDFs: reuse the SSRF/whitelist/redirect-safe HTTP + pdfplumber path.
        if urlparse(source_url).path.lower().endswith(".pdf"):
            return HttpComplianceScraper().scrape(source_url, allowed_domains=allowed_domains)

        try:
            # Non-stealth fetchers only. Fetcher = HTTP; DynamicFetcher = Playwright (JS).
            if self.settings.compliance_scrapling_render_js:
                from scrapling.fetchers import DynamicFetcher as _Fetcher  # noqa: PLC0415
            else:
                from scrapling.fetchers import Fetcher as _Fetcher  # noqa: PLC0415
        except ImportError as error:
            raise ComplianceScraperError(
                "Scrapling is not installed. Run `pip install \"scrapling[fetchers]\"` "
                "to enable COMPLIANCE_SCRAPER_PROVIDER=scrapling."
            ) from error

        try:
            page = _Fetcher.get(
                source_url,
                timeout=max(1, self.settings.compliance_fetch_timeout_seconds),
            )
        except Exception as error:  # scrapling raises varied fetch errors
            raise ComplianceScraperError(f"Scrapling fetch failed: {error}") from error

        # Re-validate the final URL after any internal redirects Scrapling followed.
        final_url = getattr(page, "url", source_url) or source_url
        _assert_hop_allowed(
            final_url,
            allow_private=self.settings.compliance_allow_private_scrape,
            allowed_domains=allowed_domains,
        )

        status = getattr(page, "status", 200)
        if isinstance(status, int) and status >= 400:
            raise ComplianceScraperError(f"Source returned HTTP {status}.")

        html_body = getattr(page, "html_content", None) or getattr(page, "body", None) or str(page)
        document = html_to_readable_document(source_url=final_url, raw_html=html_body)
        title = getattr(page, "title", None)
        if isinstance(title, str) and title.strip():
            document = ScrapedSourceDocument(
                source_url=final_url, title=title.strip(), markdown=document.markdown
            )
        return document


def get_compliance_scraper() -> ComplianceScraper:
    provider = get_settings().compliance_scraper_provider.lower()
    if provider == "firecrawl":
        return FirecrawlComplianceScraper()
    if provider == "scrapling":
        return ScraplingComplianceScraper()
    if provider == "http":
        return HttpComplianceScraper()
    return ManualReviewScraper()
