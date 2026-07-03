from __future__ import annotations

from io import BytesIO
from typing import Any

import pytest
from reportlab.pdfgen import canvas

from app.services import compliance_scraper
from app.services.compliance_scraper import (
    ComplianceScraperError,
    HttpComplianceScraper,
    html_to_readable_document,
    pdf_to_readable_document,
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
    scraper = HttpComplianceScraper()
    # The scraper now fetches via a no-auto-redirect opener; patch that.
    monkeypatch.setattr(scraper._opener, "open", lambda request, timeout: FakeResponse())

    document = scraper.scrape("https://example.gov/import-rules")

    assert document.source_url == "https://example.gov/import-rules"
    assert document.title == "Food import rules"
    assert "Commercial food imports require importer-side review" in document.markdown


def _redirect_error(location: str) -> Any:
    from email.message import Message

    headers = Message()
    headers["Location"] = location
    return compliance_scraper.HTTPError(
        "https://www.cbsa-asfc.gc.ca/import", 302, "Found", headers, None  # type: ignore[arg-type]
    )


def test_assert_hop_allowed_blocks_offwhitelist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        compliance_scraper, "validate_public_source_url", lambda u, *, allow_private: None
    )
    with pytest.raises(ComplianceScraperError, match="non-whitelisted"):
        compliance_scraper._assert_hop_allowed(
            "https://random-blog.com/x", allow_private=False, allowed_domains=[]
        )


def test_assert_hop_allowed_blocks_private_ip_on_redirect() -> None:
    # SSRF guard runs on every hop regardless of whitelist (allowed_domains=None).
    with pytest.raises(ComplianceScraperError):
        compliance_scraper._assert_hop_allowed(
            "http://169.254.169.254/latest/meta-data", allow_private=False, allowed_domains=None
        )


def test_scraper_refuses_redirect_off_whitelist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        compliance_scraper, "validate_public_source_url", lambda u, *, allow_private: None
    )
    scraper = HttpComplianceScraper()

    def fake_open(request: Any, timeout: int) -> Any:
        raise _redirect_error("https://evil.example.com/pwn")

    monkeypatch.setattr(scraper._opener, "open", fake_open)
    with pytest.raises(ComplianceScraperError, match="non-whitelisted"):
        scraper.scrape("https://www.cbsa-asfc.gc.ca/import", allowed_domains=[])


def test_scraper_follows_whitelisted_redirect(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        compliance_scraper, "validate_public_source_url", lambda u, *, allow_private: None
    )
    scraper = HttpComplianceScraper()
    calls = {"n": 0}

    def fake_open(request: Any, timeout: int) -> Any:
        calls["n"] += 1
        if calls["n"] == 1:
            raise _redirect_error("https://www.cbsa-asfc.gc.ca/import/final")
        return FakeResponse()

    monkeypatch.setattr(scraper._opener, "open", fake_open)
    document = scraper.scrape("https://www.cbsa-asfc.gc.ca/import", allowed_domains=[])
    assert calls["n"] == 2  # followed one redirect, then fetched
    assert document.source_url == "https://www.cbsa-asfc.gc.ca/import/final"


def test_pdf_to_readable_document_extracts_official_source_text() -> None:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.drawString(72, 720, "Official import notice")
    pdf.drawString(72, 700, "Certificate and labeling requirements must be verified before export.")
    pdf.drawString(72, 680, "Inspection requirements are product and destination specific.")
    pdf.save()

    document = pdf_to_readable_document(
        source_url="https://example.gov/notices/import-notice.pdf",
        raw_pdf=buffer.getvalue(),
    )

    assert document.title == "import-notice.pdf"
    assert "Official import notice" in document.markdown
    assert "labeling requirements" in document.markdown


# ── Scrapling optional provider (stealth-disabled) ───────────────────────────

def test_get_compliance_scraper_selects_scrapling(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.settings import get_settings

    monkeypatch.setattr(get_settings(), "compliance_scraper_provider", "scrapling")
    scraper = compliance_scraper.get_compliance_scraper()
    assert isinstance(scraper, compliance_scraper.ScraplingComplianceScraper)


def test_scrapling_rejects_offwhitelist_before_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    # Whitelist is enforced before Scrapling is even imported.
    monkeypatch.setattr(
        compliance_scraper, "validate_public_source_url", lambda u, *, allow_private: None
    )
    scraper = compliance_scraper.ScraplingComplianceScraper()
    with pytest.raises(ComplianceScraperError, match="non-whitelisted"):
        scraper.scrape("https://random-blog.com/x", allowed_domains=[])


def test_scrapling_reports_missing_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    # With a whitelisted URL but Scrapling not installed, a clear install hint is raised.
    monkeypatch.setattr(
        compliance_scraper, "validate_public_source_url", lambda u, *, allow_private: None
    )
    scraper = compliance_scraper.ScraplingComplianceScraper()
    with pytest.raises(ComplianceScraperError, match="not installed"):
        scraper.scrape("https://www.cbsa-asfc.gc.ca/import", allowed_domains=[])
