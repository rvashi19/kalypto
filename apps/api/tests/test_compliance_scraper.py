from __future__ import annotations

from typing import Any

import pytest

from app.services import compliance_scraper
from app.services.compliance_scraper import (
    ComplianceScraperError,
    HttpComplianceScraper,
    html_to_readable_document,
    validate_public_source_url,
)


class FakeResponse:
    headers = {"Content-Type": "text/html; charset=utf-8"}

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: Any) -> None:
        return None

    def read(self, limit: int) -> bytes:
        return b"""
        <html>
          <head><title>Food import rules</title><script>ignore()</script></head>
          <body>
            <h1>Food import rules</h1>
            <p>Commercial food imports require importer-side review and verified documents.</p>
            <p>Labels and certificates must be confirmed before shipment.</p>
            <p>This source is stored for compliance evidence review only.</p>
          </body>
        </html>
        """


def test_html_to_readable_document_extracts_title_and_text() -> None:
    document = html_to_readable_document(
        source_url="https://example.gov/rules",
        raw_html="""
        <html><head><title>Official Rules</title></head>
        <body><script>bad()</script><h1>Official Rules</h1>
        <p>
          Importers must confirm documents, certificates, labels, inspections,
          and product-specific controls before importing regulated goods.
        </p>
        <p>Exporter should verify the requirements with broker and official source.</p>
        </body></html>
        """,
    )

    assert document.title == "Official Rules"
    assert "bad()" not in document.markdown
    assert "documents, certificates" in document.markdown


def test_private_source_urls_are_blocked_by_default() -> None:
    with pytest.raises(ComplianceScraperError):
        validate_public_source_url("http://127.0.0.1:8000/private", allow_private=False)


def test_http_scraper_fetches_and_normalizes_html(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        compliance_scraper,
        "validate_public_source_url",
        lambda source_url, *, allow_private: None,
    )
    monkeypatch.setattr(compliance_scraper, "urlopen", lambda request, timeout: FakeResponse())

    document = HttpComplianceScraper().scrape("https://example.gov/import-rules")

    assert document.source_url == "https://example.gov/import-rules"
    assert document.title == "Food import rules"
    assert "Commercial food imports require importer-side review" in document.markdown
