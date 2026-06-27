# ruff: noqa: E501
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.models import ComplianceRequirement, Organization, User
from app.schemas.compliance import ComplianceCheckerRequest, ComplianceRequirementInput
from app.scripts.seed_demo import compliance_seed_records
from app.services.compliance_answer import CountryComplianceCheckerService
from app.services.compliance_normalization import normalize_country, normalize_hsn
from app.services.compliance_retrieval import ComplianceDataWriter, ComplianceRetriever
from app.services.compliance_store import PostgresComplianceKnowledgeStore

DISCLAIMER = (
    "This is compliance assistance based on available source-backed records. It is not legal, "
    "customs, or regulatory advice. Verify requirements with the importer, customs broker, "
    "or official authority before shipment."
)


def _tenant(session) -> tuple[Organization, User]:
    organization = Organization(name="Demo", slug=f"demo-{datetime.now(UTC).timestamp()}")
    user = User(
        email=f"owner-{datetime.now(UTC).timestamp()}@example.com",
        password_hash="hash",
        full_name="Owner",
    )
    session.add_all([organization, user])
    session.flush()
    return organization, user


def _answer(session, organization: Organization, user: User, **overrides):
    payload = {
        "product": "Mango juice beverage",
        "hsn_code": "200989",
        "destination_country": "Canada",
        "category": "beverages",
        "details": {"retail_or_bulk": "retail", "packaging_type": "bottle"},
    }
    payload.update(overrides)
    return CountryComplianceCheckerService(session).answer(
        payload=ComplianceCheckerRequest(**payload),
        tenant_id=organization.id,
        user_id=user.id,
    )


def _requirement(**overrides) -> ComplianceRequirementInput:
    values = {
        "country": "Canada",
        "category": "beverages",
        "hsn_code": "2009",
        "product_keywords": ["mango", "juice", "beverage"],
        "requirement_type": "import_document",
        "requirement_text": "Commercial invoice and packing list should support importer-side entry.",
        "source_url": "https://www.cbsa-asfc.gc.ca/import/guide-eng.html",
        "source_name": "CBSA import guide",
        "source_authority_level": "official",
        "confidence_score": 84,
        "last_checked_at": datetime.now(UTC),
        "review_status": "approved",
        "reviewed_by": "test",
        "reviewed_at": datetime.now(UTC),
    }
    values.update(overrides)
    return ComplianceRequirementInput(**values)


def test_country_and_hsn_normalization() -> None:
    assert normalize_country("UAE") == "United Arab Emirates"
    assert normalize_country(" usa ") == "USA"
    assert normalize_hsn(" 2009.89 ") == "200989"
    assert normalize_hsn("unknown") is None


def test_local_demo_database_is_ignored() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    gitignore = (repo_root / ".gitignore").read_text(encoding="utf-8")
    assert "apps/api/local_kalypto.db" in gitignore
    assert "apps/api/*.db" in gitignore


def test_compliance_retrieval_is_tenant_scoped(session) -> None:
    first_org = Organization(name="First", slug="first")
    second_org = Organization(name="Second", slug="second")
    session.add_all([first_org, second_org])
    session.flush()

    ComplianceDataWriter(session, first_org.id).ingest([_requirement()])
    ComplianceDataWriter(session, second_org.id).ingest(
        [
            _requirement(
                requirement_type="certificate",
                requirement_text="Second tenant private certificate record should not be visible.",
                source_url="https://example.com/private",
                source_name="Private source",
                source_authority_level="operator_seeded",
            ),
        ],
    )
    session.commit()

    matches = ComplianceRetriever(session, first_org.id).retrieve(
        product="Mango juice beverage",
        hsn_code="200989",
        destination_country="Canada",
        category="beverages",
    )

    assert len(matches) == 1
    assert "importer-side entry" in matches[0].requirement.extracted_requirement
    assert session.query(ComplianceRequirement).count() == 2


def test_approved_evidence_is_used_in_chatbot_answer(session) -> None:
    organization, user = _tenant(session)
    ComplianceDataWriter(session, organization.id).ingest([_requirement()])
    session.commit()

    response = _answer(session, organization, user)

    assert response.status == "answered"
    assert response.sections.required_import_documents == [
        "Commercial invoice and packing list should support importer-side entry.",
    ]
    assert response.sections.source_references[0].source_name == "CBSA import guide"
    assert response.sections.source_references[0].last_checked_date is not None
    assert response.last_checked_date is not None
    assert response.confidence_level in {"High", "Medium", "Low"}
    assert response.disclaimer == DISCLAIMER


def test_pending_evidence_is_not_used_in_final_answer(session) -> None:
    organization, user = _tenant(session)
    ComplianceDataWriter(session, organization.id).ingest(
        [
            _requirement(
                review_status="pending",
                requirement_text="Pending record should never appear in approved answer.",
            ),
        ],
    )
    session.commit()

    response = _answer(session, organization, user)

    assert response.status == "needs_review"
    assert "Pending record should never appear" not in response.answer
    assert response.sections.required_import_documents == []
    assert any(
        "Pending or unreviewed evidence exists" in item for item in response.unresolved_questions
    )


def test_missing_evidence_returns_insufficient_verified_data(session) -> None:
    organization, user = _tenant(session)
    session.commit()

    response = _answer(session, organization, user)

    assert response.status == "insufficient_verified_data"
    assert "Insufficient verified data available" in response.answer
    assert response.confidence_level == "Low"
    assert response.disclaimer == DISCLAIMER


def test_stale_evidence_is_flagged_and_excluded(session) -> None:
    organization, user = _tenant(session)
    ComplianceDataWriter(session, organization.id).ingest(
        [
            _requirement(
                requirement_text="Stale approved evidence should not be used.",
                last_checked_at=datetime.now(UTC) - timedelta(days=45),
                expires_at=datetime.now(UTC) - timedelta(days=1),
            ),
        ],
    )
    session.commit()

    response = _answer(session, organization, user)

    assert response.status == "needs_review"
    assert "Stale approved evidence" not in response.answer
    assert any("stale" in item.lower() for item in response.unresolved_questions)


def test_checker_can_answer_seeded_canada_beverage(session) -> None:
    organization, user = _tenant(session)
    ComplianceDataWriter(session, organization.id).ingest(compliance_seed_records())
    session.commit()

    response = _answer(session, organization, user)

    assert response.status == "answered"
    assert response.sections.source_references
    assert response.last_checked_date is not None
    assert response.disclaimer == DISCLAIMER


def test_unsupported_scope_returns_safe_response(session) -> None:
    organization, user = _tenant(session)
    session.commit()

    response = _answer(
        session,
        organization,
        user,
        destination_country="Australia",
        category="beverages",
    )

    assert response.status == "unsupported_scope"
    assert "Insufficient verified data available" in response.answer
    assert response.sections.source_references == []


def test_postgres_store_detects_source_snapshot_changes_and_review(session) -> None:
    organization, _ = _tenant(session)
    store = PostgresComplianceKnowledgeStore(session=session, tenant_id=organization.id)

    first = store.record_source_snapshot(
        source_url="https://example.gov/rules",
        country="Canada",
        category="beverages",
        title="Rules",
        markdown="Current label rules for import review.",
    )
    unchanged = store.record_source_snapshot(
        source_url="https://example.gov/rules",
        country="Canada",
        category="beverages",
        title="Rules",
        markdown="Current label rules for import review.",
    )
    changed = store.record_source_snapshot(
        source_url="https://example.gov/rules",
        country="Canada",
        category="beverages",
        title="Rules",
        markdown="Updated label rules for import review.",
    )
    session.flush()

    changes = store.list_source_changes(status="needs_review")
    reviewed = store.review_source_change(
        change_id=changes[0].id,
        status="reviewed",
        reviewed_by="owner@example.com",
        notes="Reviewed source update.",
    )

    assert first.status == "new_snapshot"
    assert unchanged.status == "unchanged"
    assert changed.status == "needs_review"
    assert len(changes) == 1
    assert reviewed.status == "reviewed"
    assert reviewed.reviewed_by == "owner@example.com"


def test_postgres_source_change_detail_includes_review_excerpts(session) -> None:
    organization, _ = _tenant(session)
    store = PostgresComplianceKnowledgeStore(session=session, tenant_id=organization.id)
    store.record_source_snapshot(
        source_url="https://example.gov/rules",
        country="Canada",
        category="beverages",
        title="Old Rules",
        markdown="Old label rules for import review.",
    )
    store.record_source_snapshot(
        source_url="https://example.gov/rules",
        country="Canada",
        category="beverages",
        title="Updated Rules",
        markdown="Updated label rules for import review with new certificate reminder.",
    )
    session.flush()

    change = store.list_source_changes(status="needs_review")[0]
    detail = store.get_source_change_detail(change_id=change.id)

    assert detail.current_title == "Updated Rules"
    assert "new certificate reminder" in detail.current_markdown_excerpt
    assert detail.previous_title == "Old Rules"
    assert "Old label rules" in (detail.previous_markdown_excerpt or "")


def test_postgres_due_sources_uses_latest_snapshot_freshness(session) -> None:
    organization, _ = _tenant(session)
    store = PostgresComplianceKnowledgeStore(session=session, tenant_id=organization.id)
    store.ingest([_requirement()])
    store.record_source_snapshot(
        source_url="https://www.cbsa-asfc.gc.ca/import/guide-eng.html",
        country="Canada",
        category="beverages",
        title="CBSA",
        markdown="Fresh source snapshot for compliance monitoring.",
    )
    session.commit()

    due = store.due_sources(limit=10)

    assert due == []


def test_postgres_coverage_cells_report_verified_partial_and_empty(session) -> None:
    organization, _ = _tenant(session)
    store = PostgresComplianceKnowledgeStore(session=session, tenant_id=organization.id)
    store.ingest(
        [
            _requirement(requirement_type="import_document"),
            _requirement(
                requirement_type="labeling",
                requirement_text="Retail labels require importer-side confirmation.",
                source_url="https://inspection.canada.ca/en/food-labels/labelling",
            ),
            _requirement(
                requirement_type="inspection",
                requirement_text="Food shipments may be subject to inspection controls.",
                source_url="https://inspection.canada.ca/en/importing-food-plants-animals",
            ),
            _requirement(
                country="USA",
                category="textiles",
                hsn_code="6109",
                product_keywords=["cotton", "shirt"],
                requirement_type="labeling",
                requirement_text="Textile labels require fiber content and origin checks.",
                source_url="https://www.ftc.gov/business-guidance/industry/clothing-and-textiles",
                source_name="FTC textile guidance",
            ),
        ]
    )
    session.commit()

    cells = store.coverage_cells(countries=["Canada", "USA"], categories=["beverages", "textiles"])
    status_by_key = {(cell.country, cell.category): cell.status for cell in cells}

    assert status_by_key[("Canada", "beverages")] == "verified"
    assert status_by_key[("USA", "textiles")] == "partial"
    assert status_by_key[("USA", "beverages")] == "empty"
