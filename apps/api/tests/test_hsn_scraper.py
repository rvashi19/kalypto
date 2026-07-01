# ruff: noqa: E501
from __future__ import annotations

import json
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

from app.models import HsnCode
from app.services import hsn_scraper
from app.services.hsn_scraper import HsnScrapeError, fetch_official_file, fetch_ogd_records


class _FakeResponse:
    def __init__(self, body: bytes, content_type: str = "application/json"):
        self._body = body
        self.headers = {"Content-Type": content_type}

    def read(self, *args, **kwargs) -> bytes:
        return self._body

    @property
    def headers_obj(self):  # pragma: no cover
        return self.headers


@contextmanager
def _ctx(resp: _FakeResponse):
    yield _HeaderShim(resp)


class _HeaderShim:
    """Mimics the urlopen response (.read + .headers.get)."""

    def __init__(self, resp: _FakeResponse):
        self._resp = resp
        self.headers = SimpleNamespace(get=lambda key, default="": resp.headers.get(key, default))

    def read(self, *args, **kwargs) -> bytes:
        return self._resp.read()


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    # Skip SSRF/DNS validation and polite-delay sleeps in tests.
    monkeypatch.setattr(hsn_scraper, "validate_public_source_url", lambda *a, **k: None)
    monkeypatch.setattr(hsn_scraper.time, "sleep", lambda *a, **k: None)


def _ogd_pages(monkeypatch, pages: list[list[dict]]):
    calls = {"i": 0}

    def fake_urlopen(request, timeout=60):  # noqa: ARG001
        idx = calls["i"]
        calls["i"] += 1
        records = pages[idx] if idx < len(pages) else []
        body = json.dumps({"status": "ok", "records": records}).encode("utf-8")
        return _ctx(_FakeResponse(body))

    monkeypatch.setattr(hsn_scraper, "urlopen", fake_urlopen)


def test_ogd_connector_imports_records(session, monkeypatch):
    _ogd_pages(
        monkeypatch,
        [
            [
                {"hsn_code": "09103010", "description": "Turmeric (curcuma) powder"},
                {"hsn_code": "10063020", "description": "Basmati rice, milled"},
            ],
            [],
        ],
    )
    outcome = fetch_ogd_records(
        session=session,
        resource_id="demo-resource",
        source_version="ogd-2024",
        api_key="test-key",
    )
    assert outcome.records_fetched == 2
    assert outcome.result.job.status == "completed"
    assert outcome.result.job.records_created == 2
    turmeric = session.scalars(select(HsnCode).where(HsnCode.normalized_code == "09103010")).first()
    assert turmeric is not None
    assert turmeric.source_name.startswith("data.gov.in")
    assert turmeric.code == "09103010"  # leading zero preserved


def test_ogd_connector_idempotent(session, monkeypatch):
    page = [{"hsn_code": "09103010", "description": "Turmeric (curcuma) powder"}]
    _ogd_pages(monkeypatch, [page, []])
    fetch_ogd_records(session=session, resource_id="r", source_version="ogd-2024", api_key="k")
    _ogd_pages(monkeypatch, [page, []])
    second = fetch_ogd_records(session=session, resource_id="r", source_version="ogd-2024", api_key="k")
    assert session.scalar(select(func.count()).select_from(HsnCode)) == 1
    assert second.result.job.records_created == 0
    assert second.result.job.records_updated == 1


def test_ogd_requires_api_key(session, monkeypatch):
    monkeypatch.setattr(hsn_scraper.get_settings(), "data_gov_in_api_key", None, raising=False)
    with pytest.raises(HsnScrapeError, match="DATA_GOV_IN_API_KEY"):
        fetch_ogd_records(session=session, resource_id="r", source_version="v", api_key=None)


def test_ogd_surfaces_source_error(session, monkeypatch):
    def fake_urlopen(request, timeout=60):  # noqa: ARG001
        body = json.dumps({"status": "error", "message": "Meta not found"}).encode("utf-8")
        return _ctx(_FakeResponse(body))

    monkeypatch.setattr(hsn_scraper, "urlopen", fake_urlopen)
    with pytest.raises(HsnScrapeError, match="Meta not found"):
        fetch_ogd_records(session=session, resource_id="bad", source_version="v", api_key="k")


_EXIMGURU_DEFAULT = '<a href="/hs-codes/09-chapter-9-coffee-tea.aspx">Chapter 9</a>'
_EXIMGURU_CHAPTER = (
    "<table><tr><td>0910</td>"
    '<td><a href="0910-ginger-saffron-turmeric.aspx">Harmonised Codes of Ginger, Turmeric</a></td>'
    "</tr></table>"
)
_EXIMGURU_HEADING = (
    "<table>"
    "<tr><td>0910</td><td>Ginger, saffron, turmeric</td></tr>"
    "<tr><td>091030</td><td>Turmeric (curcuma):</td></tr>"
    "<tr><td>09103010</td><td>Fresh</td></tr>"
    "<tr><td>09103020</td><td>Dried</td></tr>"
    "</table>"
)


def test_eximguru_connector_crawls_and_imports(session, monkeypatch):
    def fake_get(url: str) -> str:
        if url.endswith("default.aspx"):
            return _EXIMGURU_DEFAULT
        if "09-chapter" in url:
            return _EXIMGURU_CHAPTER
        if "0910-ginger" in url:
            return _EXIMGURU_HEADING
        return "<html></html>"

    monkeypatch.setattr(hsn_scraper, "_eximguru_get", fake_get)
    outcome = hsn_scraper.fetch_eximguru(
        session=session, chapters=[9], source_version="eximguru-2026"
    )
    assert outcome.result.job.status == "completed"
    codes = {c.normalized_code for c in session.scalars(select(HsnCode)).all()}
    assert {"0910", "091030", "09103010", "09103020"} <= codes
    leaf = session.scalars(select(HsnCode).where(HsnCode.normalized_code == "09103010")).first()
    # 6-digit subheading context is prefixed onto the bare leaf qualifier.
    assert "Turmeric" in leaf.description
    assert leaf.source_name.startswith("EximGuru")


def test_cross_verify_confirms_with_authentic_sources(session, monkeypatch):
    from app.models import HsnCode
    from app.services import hsn_cross_verify

    session.add(
        HsnCode(
            code="69120010",
            normalized_code="69120010",
            digit_level=8,
            description="Ceramic tableware and kitchenware",
            source_name="seed",
            is_active=True,
        )
    )
    session.commit()
    # Authentic live source agrees.
    monkeypatch.setattr(
        hsn_cross_verify, "fetch_code_description", lambda code: ("Ceramic tableware, kitchenware", True)
    )
    result = hsn_cross_verify.cross_verify_code(
        session=session,
        code="69120010",
        product="ceramic coffee mug",
        llm_description="Ceramic tableware and kitchenware",
    )
    assert result.status == "cross_verified"
    assert result.authentic_count == 2

    # A code no authentic source knows -> unverified.
    monkeypatch.setattr(hsn_cross_verify, "fetch_code_description", lambda code: (None, False))
    bad = hsn_cross_verify.cross_verify_code(
        session=session, code="99999999", product="ceramic coffee mug"
    )
    assert bad.status == "unverified"
    assert bad.authentic_count == 0


def test_official_file_connector_imports_csv(session, monkeypatch):
    csv_body = b"code,description\n09103010,Turmeric powder\n62052000,Men's cotton shirt woven\n"

    def fake_urlopen(request, timeout=60):  # noqa: ARG001
        return _ctx(_FakeResponse(csv_body, content_type="text/csv"))

    monkeypatch.setattr(hsn_scraper, "urlopen", fake_urlopen)
    outcome = fetch_official_file(
        session=session,
        url="https://content.dgft.gov.in/itc-hs.csv",
        source_name="DGFT ITC(HS) 2024",
        source_version="itchs-2024",
    )
    assert outcome.result.job.records_created == 2
    assert outcome.result.job.import_type == "csv"
    shirt = session.scalars(select(HsnCode).where(HsnCode.normalized_code == "62052000")).first()
    assert shirt is not None
    assert shirt.source_url == "https://content.dgft.gov.in/itc-hs.csv"
