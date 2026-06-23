# ruff: noqa: E501
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol
from urllib.error import URLError
from urllib.request import Request, urlopen

from app.core.settings import get_settings


class ComplianceScraperError(RuntimeError):
    """Raised when a compliance source cannot be scraped."""


@dataclass(frozen=True, slots=True)
class ScrapedSourceDocument:
    source_url: str
    title: str
    markdown: str


class ComplianceScraper(Protocol):
    def scrape(self, source_url: str) -> ScrapedSourceDocument: ...


class ManualReviewScraper:
    def scrape(self, source_url: str) -> ScrapedSourceDocument:
        return ScrapedSourceDocument(
            source_url=source_url,
            title="Manual review required",
            markdown=(
                "No live scraper provider is configured. Run the existing scraping script or configure "
                "FIRECRAWL_API_KEY, then ingest verified structured records."
            ),
        )


class FirecrawlComplianceScraper:
    endpoint = "https://api.firecrawl.dev/v2/scrape"

    def __init__(self) -> None:
        self.settings = get_settings()

    def scrape(self, source_url: str) -> ScrapedSourceDocument:
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
        except URLError as error:
            raise ComplianceScraperError(f"Firecrawl request failed: {error}") from error

        body = json.loads(raw)
        data = body.get("data", {})
        metadata = data.get("metadata", {})
        markdown = data.get("markdown") or ""
        if not markdown:
            raise ComplianceScraperError("Firecrawl returned no markdown content.")
        return ScrapedSourceDocument(
            source_url=metadata.get("sourceURL") or source_url,
            title=metadata.get("title") or "Untitled source",
            markdown=markdown,
        )


def get_compliance_scraper() -> ComplianceScraper:
    provider = get_settings().compliance_scraper_provider.lower()
    if provider == "firecrawl":
        return FirecrawlComplianceScraper()
    return ManualReviewScraper()
