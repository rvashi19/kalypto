# ruff: noqa: E501
from app.models import ComplianceRequirement, Organization, User
from app.schemas.compliance import ComplianceCheckerRequest, ComplianceRequirementInput
from app.services.compliance_answer import CountryComplianceCheckerService
from app.services.compliance_normalization import normalize_country, normalize_hsn
from app.services.compliance_retrieval import ComplianceDataWriter, ComplianceRetriever


def test_country_and_hsn_normalization() -> None:
    assert normalize_country("UAE") == "United Arab Emirates"
    assert normalize_country("usa") == "USA"
    assert normalize_hsn(" 2009.89 ") == "200989"
    assert normalize_hsn("unknown") is None


def test_compliance_retrieval_is_tenant_scoped(session) -> None:
    first_org = Organization(name="First", slug="first")
    second_org = Organization(name="Second", slug="second")
    session.add_all([first_org, second_org])
    session.flush()

    first_record = ComplianceRequirementInput(
        country="Canada",
        category="beverages",
        hsn_code="2009",
        product_keywords=["mango", "juice"],
        requirement_type="labeling",
        requirement_text="Retail food labels should be verified for bilingual Canadian requirements.",
        source_url="https://inspection.canada.ca/en/food-labels/labelling",
        source_name="CFIA food labelling",
        source_authority_level="official",
        confidence_score=80,
    )
    second_record = ComplianceRequirementInput(
        country="Canada",
        category="beverages",
        hsn_code="2009",
        product_keywords=["mango", "juice"],
        requirement_type="certificate",
        requirement_text="Second tenant private certificate record should not be visible.",
        source_url="https://example.com/private",
        source_name="Private source",
        source_authority_level="operator_seeded",
        confidence_score=80,
    )
    ComplianceDataWriter(session, first_org.id).ingest([first_record])
    ComplianceDataWriter(session, second_org.id).ingest([second_record])
    session.commit()

    matches = ComplianceRetriever(session, first_org.id).retrieve(
        product="Mango juice beverage",
        hsn_code="200989",
        destination_country="Canada",
        category="beverages",
    )

    assert len(matches) == 1
    assert "bilingual Canadian requirements" in matches[0].requirement.requirement_text
    assert session.query(ComplianceRequirement).count() == 2


def test_checker_returns_insufficient_data_without_records(session) -> None:
    organization = Organization(name="Demo", slug="demo")
    user = User(email="owner@example.com", password_hash="hash", full_name="Owner")
    session.add_all([organization, user])
    session.commit()

    response = CountryComplianceCheckerService(session).answer(
        payload=ComplianceCheckerRequest(
            product="Packaged tea",
            hsn_code="0902",
            destination_country="Canada",
            category="beverages",
        ),
        tenant_id=organization.id,
        user_id=user.id,
    )

    assert response.status == "insufficient_data"
    assert "Insufficient verified data available" in response.answer
    assert response.confidence_level == "Low"


def test_checker_formats_retrieved_sources(session) -> None:
    organization = Organization(name="Demo", slug="demo")
    user = User(email="owner@example.com", password_hash="hash", full_name="Owner")
    session.add_all([organization, user])
    session.flush()
    ComplianceDataWriter(session, organization.id).ingest(
        [
            ComplianceRequirementInput(
                country="Canada",
                category="beverages",
                hsn_code="2009",
                product_keywords=["mango", "juice"],
                requirement_type="import_document",
                requirement_text="Commercial invoice and packing list should support importer-side entry.",
                source_url="https://www.cbsa-asfc.gc.ca/import/guide-eng.html",
                source_name="CBSA import guide",
                source_authority_level="official",
                confidence_score=84,
            ),
        ],
    )
    session.commit()

    response = CountryComplianceCheckerService(session).answer(
        payload=ComplianceCheckerRequest(
            product="Mango juice beverage",
            hsn_code="200989",
            destination_country="Canada",
            category="beverages",
            details={"retail_or_bulk": "retail", "packaging_type": "bottle"},
        ),
        tenant_id=organization.id,
        user_id=user.id,
    )

    assert response.status == "answered"
    assert response.sections.required_import_documents == [
        "Commercial invoice and packing list should support importer-side entry.",
    ]
    assert response.sections.source_references[0].source_name == "CBSA import guide"
    assert "Disclaimer" in response.answer