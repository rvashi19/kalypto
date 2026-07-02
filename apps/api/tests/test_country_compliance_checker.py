# ruff: noqa: E501
"""Tests for the Country Compliance Checker v1 (check / retrieval / review / whitelist)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.models import (
    ComplianceRetrievalJob,
    ComplianceSourceRegistry,
    Membership,
    MembershipRole,
    Organization,
    User,
)
from app.models.compliance import ComplianceRequirement
from app.schemas.compliance import ComplianceCheckRequest, ComplianceRequirementInput
from app.services import compliance_retrieval_job as job_module
from app.services.compliance_check_service import ComplianceCheckService
from app.services.compliance_retrieval import ComplianceDataWriter
from app.services.compliance_scraper import ScrapedSourceDocument
from app.services.compliance_storage import reset_compliance_storage
from app.services.compliance_whitelist import is_domain_allowed

# ── Fixtures / helpers ────────────────────────────────────────────────────────

def _tenant(session, role: MembershipRole = MembershipRole.OWNER) -> tuple[Organization, User, Membership]:
    org = Organization(name="Demo", slug=f"demo-{uuid.uuid4().hex[:8]}")
    user = User(email=f"u-{uuid.uuid4().hex[:8]}@example.com", password_hash="x", full_name="U")
    session.add_all([org, user])
    session.flush()
    membership = Membership(organization_id=org.id, user_id=user.id, role=role)
    session.add(membership)
    session.flush()
    return org, user, membership


def _approved_requirement(**overrides) -> ComplianceRequirementInput:
    values = {
        "country": "Canada",
        "category": "beverages",
        "hsn_code": "2009",
        "product_keywords": ["mango", "juice", "beverage"],
        "requirement_type": "import_document",
        "requirement_text": "Commercial invoice and packing list support importer-side entry.",
        "source_url": "https://www.cbsa-asfc.gc.ca/import/guide-eng.html",
        "source_name": "CBSA import guide",
        "source_authority_level": "official",
        "confidence_score": 84,
        "last_checked_at": datetime.now(UTC),
        "status": "active",
        "review_status": "approved",
        "reviewed_by": "test",
        "reviewed_at": datetime.now(UTC),
    }
    values.update(overrides)
    return ComplianceRequirementInput(**values)


def _check_payload(**overrides) -> ComplianceCheckRequest:
    values = {
        "origin_country": "India",
        "destination_country": "Canada",
        "hsn_code": "200989",
        "product_description": "Mango juice beverage in retail bottles",
        "product_category": "beverages",
    }
    values.update(overrides)
    return ComplianceCheckRequest(**values)


class _FakeExtractor:
    """Fake AI extractor with a call counter to assert dedup behaviour."""

    def __init__(self) -> None:
        self.calls = 0

    def extract_requirements_from_source_text(self, **kwargs):
        from app.services.compliance_ai_extractor import ExtractedRequirement, ExtractionResult

        self.calls += 1
        return ExtractionResult(
            requirements=[
                ExtractedRequirement(
                    requirement_type="document",
                    title="Import declaration",
                    summary="File an import declaration with the customs authority.",
                    detail="A commercial invoice and import declaration are required at entry.",
                    mandatory_or_conditional="mandatory",
                    evidence_excerpt="Importers must file a declaration...",
                    confidence_label="Medium",
                )
            ],
            missing_questions=["Is the product retail or bulk?"],
            buyer_questions=["Does the buyer need FDA prior notice?"],
            cha_questions=["Confirm HSN classification."],
            ambiguities=[],
            evidence_summary="Source establishes import declaration requirement.",
        )


def _register_source(session, org, url="https://www.cbsa-asfc.gc.ca/import/guide-eng.html") -> ComplianceSourceRegistry:
    src = ComplianceSourceRegistry(
        tenant_id=org.id,
        country="Canada",
        authority_name="CBSA",
        source_name="CBSA import guide",
        base_url=url,
        allowed_domains_json=[],
        source_type="html",
        product_categories_json=["beverages"],
        is_active=True,
    )
    session.add(src)
    session.flush()
    return src


# ── Whitelist ─────────────────────────────────────────────────────────────────

def test_whitelisted_official_domain_allowed() -> None:
    assert is_domain_allowed("https://www.cbsa-asfc.gc.ca/import/guide.html")
    assert is_domain_allowed("https://fda.gov/food")
    assert is_domain_allowed("https://apeda.gov.in/x")


def test_non_whitelisted_domain_rejected() -> None:
    assert not is_domain_allowed("https://random-consultant-blog.com/guide")
    assert not is_domain_allowed("https://medium.com/@someone/customs")


# ── /check: local match, no match, no source ──────────────────────────────────

def test_approved_local_requirement_matches(session) -> None:
    org, user, _ = _tenant(session)
    ComplianceDataWriter(session, org.id).upsert_requirement(_approved_requirement())
    session.flush()

    resp = ComplianceCheckService(session).check(
        payload=_check_payload(), tenant_id=org.id, user_id=user.id
    )
    assert resp.status == "answered"
    assert resp.sources, "expected source citations"
    assert any(cards for cards in resp.requirements.values())
    assert resp.retrieval_job_id is None


def test_no_local_match_creates_retrieval_job(session) -> None:
    org, user, _ = _tenant(session)
    resp = ComplianceCheckService(session).check(
        payload=_check_payload(), tenant_id=org.id, user_id=user.id
    )
    assert resp.status == "retrieval_queued"
    assert resp.retrieval_job_id is not None
    job = session.get(ComplianceRetrievalJob, uuid.UUID(resp.retrieval_job_id))
    assert job is not None and job.status == "queued"


def test_no_source_found_response(session) -> None:
    org, user, _ = _tenant(session)
    resp = ComplianceCheckService(session).check(
        payload=_check_payload(start_retrieval=False), tenant_id=org.id, user_id=user.id
    )
    assert resp.status == "no_verified_source"
    assert "No verified official requirement" in resp.answer_summary


def test_missing_question_generation(session) -> None:
    org, user, _ = _tenant(session)
    resp = ComplianceCheckService(session).check(
        payload=_check_payload(hsn_code=None), tenant_id=org.id, user_id=user.id
    )
    assert any("HSN" in q for q in resp.missing_questions)
    assert resp.cha_questions


def test_pending_requirement_not_returned_as_answer(session) -> None:
    org, user, _ = _tenant(session)
    ComplianceDataWriter(session, org.id).upsert_requirement(
        _approved_requirement(status="draft", review_status="pending")
    )
    session.flush()
    resp = ComplianceCheckService(session).check(
        payload=_check_payload(), tenant_id=org.id, user_id=user.id
    )
    # Pending is excluded → no answered match, retrieval queued instead.
    assert resp.status == "retrieval_queued"


# ── Retrieval job runner: snapshot, dedup, AI, pending_review ─────────────────

def test_retrieval_creates_snapshot_and_pending_requirements(session, monkeypatch, tmp_path) -> None:
    org, user, _ = _tenant(session)
    _register_source(session, org)
    session.flush()

    from app.core.settings import get_settings

    monkeypatch.setattr(get_settings(), "compliance_storage_path", str(tmp_path))
    reset_compliance_storage()
    fake = _FakeExtractor()
    monkeypatch.setattr(job_module, "get_compliance_ai_extractor", lambda: fake)
    monkeypatch.setattr(
        job_module,
        "get_compliance_scraper",
        lambda: type("S", (), {"scrape": lambda self, url: ScrapedSourceDocument(
            source_url=url, title="CBSA", markdown="Importers must file a declaration. " * 20
        )})(),
    )

    job = ComplianceRetrievalJob(
        tenant_id=org.id, destination_country="Canada", product_category="beverages",
        hsn_code="200989", product_description="Mango juice", status="queued",
    )
    session.add(job)
    session.flush()

    job_module.run_retrieval_job(session, job_id=job.id, tenant_id=org.id)
    session.flush()

    assert job.snapshots_created == 1
    assert job.requirements_extracted == 1
    assert fake.calls == 1
    # Extracted requirement must be pending_review, not active/approved.
    pending = session.query(ComplianceRequirement).filter_by(
        tenant_id=org.id, review_status="pending"
    ).all()
    assert len(pending) == 1
    assert pending[0].status == "draft"
    # Storage file written under the checksum key.
    assert any(tmp_path.rglob("extracted.txt"))


def test_checksum_dedup_skips_repeated_ai_extraction(session, monkeypatch, tmp_path) -> None:
    org, user, _ = _tenant(session)
    _register_source(session, org)
    session.flush()

    from app.core.settings import get_settings

    monkeypatch.setattr(get_settings(), "compliance_storage_path", str(tmp_path))
    reset_compliance_storage()
    fake = _FakeExtractor()
    monkeypatch.setattr(job_module, "get_compliance_ai_extractor", lambda: fake)
    monkeypatch.setattr(
        job_module,
        "get_compliance_scraper",
        lambda: type("S", (), {"scrape": lambda self, url: ScrapedSourceDocument(
            source_url=url, title="CBSA", markdown="Static official content that never changes. " * 20
        )})(),
    )

    def _run():
        job = ComplianceRetrievalJob(
            tenant_id=org.id, destination_country="Canada", product_category="beverages",
            status="queued",
        )
        session.add(job)
        session.flush()
        job_module.run_retrieval_job(session, job_id=job.id, tenant_id=org.id)
        session.flush()
        return job

    first = _run()
    assert first.snapshots_created == 1
    assert fake.calls == 1

    second = _run()
    # Unchanged checksum → no new snapshot, AI NOT called again.
    assert second.snapshots_created == 0
    assert fake.calls == 1


def test_approved_requirement_appears_in_answer_after_review(session, monkeypatch, tmp_path) -> None:
    org, user, _ = _tenant(session)
    _register_source(session, org)
    session.flush()
    from app.core.settings import get_settings

    monkeypatch.setattr(get_settings(), "compliance_storage_path", str(tmp_path))
    reset_compliance_storage()
    fake = _FakeExtractor()
    monkeypatch.setattr(job_module, "get_compliance_ai_extractor", lambda: fake)
    monkeypatch.setattr(
        job_module,
        "get_compliance_scraper",
        lambda: type("S", (), {"scrape": lambda self, url: ScrapedSourceDocument(
            source_url=url, title="CBSA", markdown="Importers must file a declaration. " * 20
        )})(),
    )
    job = ComplianceRetrievalJob(
        tenant_id=org.id, destination_country="Canada", product_category="beverages",
        hsn_code="200989", product_description="Mango juice", status="queued",
    )
    session.add(job)
    session.flush()
    job_module.run_retrieval_job(session, job_id=job.id, tenant_id=org.id)
    session.flush()

    pending = session.query(ComplianceRequirement).filter_by(
        tenant_id=org.id, review_status="pending"
    ).first()
    # Admin approves.
    pending.review_status = "approved"
    pending.status = "active"
    session.flush()

    resp = ComplianceCheckService(session).check(
        payload=_check_payload(), tenant_id=org.id, user_id=user.id
    )
    assert resp.status == "answered"


# ── API-level: admin-only + tenant scoping ────────────────────────────────────

@pytest.fixture()
def client_factory(session, monkeypatch):
    from app.api.deps import CurrentUserContext, get_current_user_context
    from app.core.settings import get_settings
    from app.db.session import get_db_session
    from app.main import app

    # Audit middleware opens a second SQLite connection; disable it so it does not
    # contend with the shared test session for the file lock.
    monkeypatch.setattr(get_settings(), "audit_logging_enabled", False)

    def make(role: MembershipRole):
        org, user, membership = _tenant(session, role=role)
        session.commit()  # release the write lock before requests
        ctx = CurrentUserContext(user=user, organization=org, membership=membership, token=None)  # type: ignore[arg-type]
        app.dependency_overrides[get_db_session] = lambda: session
        app.dependency_overrides[get_current_user_context] = lambda: ctx
        return TestClient(app), org, user

    yield make
    app.dependency_overrides.clear()


def test_review_queue_admin_only(client_factory) -> None:
    client, _, _ = client_factory(MembershipRole.STAFF)
    resp = client.get("/api/v1/compliance/review-queue")
    assert resp.status_code == 403


def test_review_queue_owner_allowed(client_factory) -> None:
    client, _, _ = client_factory(MembershipRole.OWNER)
    resp = client.get("/api/v1/compliance/review-queue")
    assert resp.status_code == 200
    assert resp.json() == []


def test_create_source_rejects_non_whitelisted_domain(client_factory) -> None:
    client, _, _ = client_factory(MembershipRole.OWNER)
    resp = client.post(
        "/api/v1/compliance/sources",
        json={
            "country": "Canada",
            "authority_name": "Blog",
            "source_name": "Consultant blog",
            "base_url": "https://random-consultant-blog.com/guide",
            "allowed_domains": [],
            "source_type": "html",
            "product_categories": ["beverages"],
        },
    )
    assert resp.status_code == 422


def test_create_source_accepts_official_domain(client_factory) -> None:
    client, _, _ = client_factory(MembershipRole.OWNER)
    resp = client.post(
        "/api/v1/compliance/sources",
        json={
            "country": "Canada",
            "authority_name": "CBSA",
            "source_name": "CBSA import guide",
            "base_url": "https://www.cbsa-asfc.gc.ca/import/guide-eng.html",
            "allowed_domains": [],
            "source_type": "html",
            "product_categories": ["beverages"],
        },
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["country"] == "Canada"


def test_session_tenant_scoping(client_factory) -> None:
    client, org, user = client_factory(MembershipRole.OWNER)
    # Session belonging to a different tenant is not visible.
    other = uuid.uuid4()
    resp = client.get(f"/api/v1/compliance/sessions/{other}")
    assert resp.status_code == 404


# ── Automation: seed sources, refresh-due, auto-retry ─────────────────────────

def test_seed_official_sources_is_idempotent(session) -> None:
    from app.services.compliance_source_seed import OFFICIAL_SOURCES, seed_official_sources

    org, _, _ = _tenant(session)
    first = seed_official_sources(session, org.id)
    session.flush()
    assert first["created"] == len(OFFICIAL_SOURCES)
    assert first["created"] > 0

    second = seed_official_sources(session, org.id)
    session.flush()
    assert second["created"] == 0  # nothing re-created on a second run
    total = session.query(ComplianceSourceRegistry).filter_by(tenant_id=org.id).count()
    assert total == len(OFFICIAL_SOURCES)


def test_seeded_sources_are_all_whitelisted() -> None:
    from app.services.compliance_source_seed import OFFICIAL_SOURCES

    for _country, _auth, _name, url, _type, _cats in OFFICIAL_SOURCES:
        assert is_domain_allowed(url), f"seed URL not whitelisted: {url}"


def test_refresh_due_runs_jobs_for_due_sources(session, monkeypatch, tmp_path) -> None:
    from app.core.settings import get_settings
    from app.services.compliance_refresh import refresh_due_sources

    org, _, _ = _tenant(session)
    _register_source(session, org)  # last_checked_at is None -> due
    session.flush()

    monkeypatch.setattr(get_settings(), "compliance_storage_path", str(tmp_path))
    reset_compliance_storage()
    fake = _FakeExtractor()
    monkeypatch.setattr(job_module, "get_compliance_ai_extractor", lambda: fake)
    monkeypatch.setattr(
        job_module,
        "get_compliance_scraper",
        lambda: type("S", (), {"scrape": lambda self, url: ScrapedSourceDocument(
            source_url=url, title="CBSA", markdown="Importers must file a declaration. " * 20
        )})(),
    )

    summary = refresh_due_sources(session, tenant_id=org.id)
    session.flush()
    assert summary["due_groups"] == 1
    assert summary["jobs_run"] == 1
    assert summary["requirements_extracted"] == 1


def test_refresh_due_skips_recently_checked(session) -> None:
    from datetime import UTC, datetime

    from app.services.compliance_refresh import refresh_due_sources

    org, _, _ = _tenant(session)
    src = _register_source(session, org)
    src.last_checked_at = datetime.now(UTC)  # just checked -> not due
    session.flush()

    summary = refresh_due_sources(session, tenant_id=org.id)
    assert summary["due_groups"] == 0
    assert summary["jobs_run"] == 0


def test_auto_retry_skips_permanent_failure() -> None:
    from app.services.compliance_queue import _is_permanent_failure

    assert _is_permanent_failure("No active official source registered for this country/category.")
    assert _is_permanent_failure("Refused to fetch non-whitelisted domain: 'blog.com'.")
    assert not _is_permanent_failure("Source request failed: timed out")
    assert not _is_permanent_failure(None)


def test_seed_endpoint_admin_only(client_factory) -> None:
    client, _, _ = client_factory(MembershipRole.STAFF)
    resp = client.post("/api/v1/compliance/sources/seed")
    assert resp.status_code == 403


def test_seed_endpoint_owner_seeds(client_factory) -> None:
    from app.services.compliance_source_seed import OFFICIAL_SOURCES

    client, _, _ = client_factory(MembershipRole.OWNER)
    resp = client.post("/api/v1/compliance/sources/seed")
    assert resp.status_code == 200
    assert resp.json()["created"] == len(OFFICIAL_SOURCES)
