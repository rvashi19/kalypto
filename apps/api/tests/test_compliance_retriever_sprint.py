# ruff: noqa: E501
"""Tests for the SourceRetriever sprint: adapters, XLSX/CSV, snapshot metadata, review queue, seed."""

from __future__ import annotations

import io
import uuid
from datetime import UTC, datetime

import openpyxl

from app.models import (
    ComplianceReviewQueue,
    ComplianceSourceRegistry,
    Membership,
    MembershipRole,
    Organization,
    User,
)
from app.models.compliance import ComplianceRequirement, ComplianceSourceSnapshot
from app.services import compliance_retrieval_job as job_module
from app.services.compliance_source_retriever import (
    HttpSourceRetriever,
    RetrievalResult,
    SpreadsheetRetriever,
    _detect_source_type,
    extract_csv,
    extract_xlsx,
    get_retriever_for,
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _tenant(session) -> Organization:
    org = Organization(name="Demo", slug=f"demo-{uuid.uuid4().hex[:8]}")
    user = User(email=f"u-{uuid.uuid4().hex[:8]}@example.com", password_hash="x", full_name="U")
    session.add_all([org, user])
    session.flush()
    session.add(Membership(organization_id=org.id, user_id=user.id, role=MembershipRole.OWNER))
    session.flush()
    return org


def _register_source(session, org, *, url, source_type="html") -> ComplianceSourceRegistry:
    src = ComplianceSourceRegistry(
        tenant_id=org.id, country="Canada", authority_name="CBSA",
        source_name="CBSA source", base_url=url, allowed_domains_json=[],
        source_type=source_type, product_categories_json=["beverages"], is_active=True,
    )
    session.add(src)
    session.flush()
    return src


class _FakeExtractor:
    def __init__(self) -> None:
        self.calls = 0

    def extract_requirements_from_source_text(self, **kwargs):
        from app.services.compliance_ai_extractor import ExtractedRequirement, ExtractionResult
        self.calls += 1
        return ExtractionResult(
            requirements=[ExtractedRequirement(
                requirement_type="document", title="Import declaration",
                summary="File an import declaration.", detail="Commercial invoice required.",
                mandatory_or_conditional="mandatory", evidence_excerpt="Importers must file...",
                confidence_label="Medium",
            )],
            missing_questions=["Retail or bulk?"], buyer_questions=["FDA prior notice?"],
            cha_questions=["Confirm HSN."], ambiguities=[], evidence_summary="Establishes declaration.",
        )


# ── Adapter unit tests ────────────────────────────────────────────────────────

def test_detect_source_type_by_extension() -> None:
    assert _detect_source_type("https://apeda.gov.in/x.xlsx", None) == "xlsx"
    assert _detect_source_type("https://fda.gov/x.csv", None) == "csv"
    assert _detect_source_type("https://fda.gov/rules.pdf", None) == "pdf"
    assert _detect_source_type("https://gov.uk/import", None) == "html"


def test_adapter_can_handle_dispatch() -> None:
    assert isinstance(get_retriever_for("html"), HttpSourceRetriever)
    assert isinstance(get_retriever_for("pdf"), HttpSourceRetriever)
    assert isinstance(get_retriever_for("xlsx"), SpreadsheetRetriever)
    assert isinstance(get_retriever_for("csv"), SpreadsheetRetriever)


def test_extract_xlsx_produces_table_text() -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Document", "Requirement"])
    ws.append(["Phytosanitary Certificate", "Required for plant products"])
    buf = io.BytesIO()
    wb.save(buf)
    title, text = extract_xlsx(buf.getvalue(), source_url="https://apeda.gov.in/list.xlsx")
    assert "Phytosanitary Certificate" in text
    assert "Requirement" in text
    assert title.endswith(".xlsx")


def test_extract_csv_handles_bom_and_headers() -> None:
    raw = "﻿Document,Requirement\nCommercial Invoice,Mandatory\n".encode()
    title, text = extract_csv(raw, source_url="https://fda.gov/list.csv")
    assert "Commercial Invoice | Mandatory" in text
    assert "Document | Requirement" in text


# ── Wiring: XLSX source through the retrieval job (no network) ────────────────

def test_xlsx_source_records_snapshot_metadata(session, monkeypatch, tmp_path) -> None:
    from app.core.settings import get_settings
    from app.services.compliance_storage import reset_compliance_storage

    org = _tenant(session)
    _register_source(session, org, url="https://apeda.gov.in/list.xlsx", source_type="xlsx")
    session.flush()

    monkeypatch.setattr(get_settings(), "compliance_storage_path", str(tmp_path))
    reset_compliance_storage()
    fake_ai = _FakeExtractor()
    monkeypatch.setattr(job_module, "get_compliance_ai_extractor", lambda: fake_ai)
    # Avoid network: stub retrieve_source to return an XLSX RetrievalResult.
    monkeypatch.setattr(
        job_module, "retrieve_source",
        lambda url, **kw: RetrievalResult(
            source_url=url, final_url=url, source_type="xlsx",
            source_title="list.xlsx", extracted_text="Document | Requirement\nPhyto | Required",
            checksum="abc123", http_status=200, retrieved_at=datetime.now(UTC),
            parser_used="openpyxl", raw_bytes=b"xlsxbytes",
        ),
    )

    job = job_module.ComplianceRetrievalJob(
        tenant_id=org.id, destination_country="Canada", product_category="beverages",
        status="queued",
    )
    session.add(job)
    session.flush()
    job_module.run_retrieval_job(session, job_id=job.id, tenant_id=org.id)
    session.flush()

    assert job.snapshots_created == 1
    snap = session.query(ComplianceSourceSnapshot).filter_by(tenant_id=org.id).first()
    assert snap.source_type == "xlsx"
    assert snap.parser_used == "openpyxl"
    assert snap.final_url == "https://apeda.gov.in/list.xlsx"
    assert snap.extracted_text_storage_key and snap.raw_storage_key


def test_review_queue_item_created_for_pending_requirement(session, monkeypatch, tmp_path) -> None:
    from app.core.settings import get_settings
    from app.services.compliance_scraper import ScrapedSourceDocument
    from app.services.compliance_storage import reset_compliance_storage

    org = _tenant(session)
    _register_source(session, org, url="https://www.cbsa-asfc.gc.ca/import")
    session.flush()
    monkeypatch.setattr(get_settings(), "compliance_storage_path", str(tmp_path))
    reset_compliance_storage()
    fake_ai = _FakeExtractor()
    monkeypatch.setattr(job_module, "get_compliance_ai_extractor", lambda: fake_ai)
    monkeypatch.setattr(
        job_module, "get_compliance_scraper",
        lambda: type("S", (), {"scrape": lambda self, url, allowed_domains=None: ScrapedSourceDocument(
            source_url=url, title="CBSA", markdown="Importers must file a declaration. " * 20
        )})(),
    )

    job = job_module.ComplianceRetrievalJob(
        tenant_id=org.id, destination_country="Canada", product_category="beverages", status="queued",
    )
    session.add(job)
    session.flush()
    job_module.run_retrieval_job(session, job_id=job.id, tenant_id=org.id)
    session.flush()

    pending = session.query(ComplianceRequirement).filter_by(
        tenant_id=org.id, review_status="pending"
    ).all()
    assert len(pending) == 1
    queue = session.query(ComplianceReviewQueue).filter_by(tenant_id=org.id).all()
    assert len(queue) == 1
    assert queue[0].status == "pending"
    assert queue[0].requirement_id == pending[0].id
    # HTML snapshot metadata populated too.
    snap = session.query(ComplianceSourceSnapshot).filter_by(tenant_id=org.id).first()
    assert snap.parser_used == "html_text"
    assert snap.source_type == "html"


# ── Seed script idempotency ───────────────────────────────────────────────────

def test_seed_official_sources_idempotent(session) -> None:
    from app.services.compliance_source_seed import OFFICIAL_SOURCES, seed_official_sources

    org = _tenant(session)
    first = seed_official_sources(session, org.id)
    session.flush()
    assert first["created"] == len(OFFICIAL_SOURCES)
    second = seed_official_sources(session, org.id)
    session.flush()
    assert second["created"] == 0
