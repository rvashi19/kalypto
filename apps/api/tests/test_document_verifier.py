# ruff: noqa: E501
"""Tests for AI Document Verifier runs, extraction, comparison, and issues."""

from __future__ import annotations

import tempfile
import uuid
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.api.deps import CurrentUserContext, get_current_user_context
from app.db.session import get_db_session
from app.main import app
from app.models import Membership, MembershipRole, Organization, User
from app.models.compliance import ComplianceCountry, ComplianceRequirement, ProductCategory
from app.services import document_verifier as verifier_module
from app.services import storage as storage_mod
from app.services.document_verifier import DocumentExtractionResult, ExtractedFieldValue


@pytest.fixture()
def client(session):
    org = Organization(id=uuid.uuid4(), name="Verifier Org", slug=f"verifier-{uuid.uuid4().hex[:8]}")
    user = User(id=uuid.uuid4(), email=f"verifier-{uuid.uuid4().hex[:8]}@example.com", password_hash="x", is_active=True)
    membership = Membership(id=uuid.uuid4(), user_id=user.id, organization_id=org.id, role=MembershipRole.OWNER)
    session.add_all([org, user, membership])
    session.commit()

    ctx = CurrentUserContext(user=user, organization=org, membership=membership, token=None)  # type: ignore[arg-type]
    local_backend = storage_mod.LocalStorage(tempfile.mkdtemp())
    with patch.object(storage_mod, "_build_backend", return_value=local_backend), patch.object(
        verifier_module, "_resolve_provider", return_value=None
    ):
        storage_mod._build_backend.cache_clear()
        app.dependency_overrides[get_db_session] = lambda: session
        app.dependency_overrides[get_current_user_context] = lambda: ctx
        try:
            yield TestClient(app), org
        finally:
            app.dependency_overrides.clear()
            storage_mod._build_backend.cache_clear()


def _create_run(client: TestClient) -> str:
    resp = client.post(
        "/api/v1/document-verifier/runs",
        json={
            "title": "Invoice audit",
            "reference_number": "INV-AUDIT-1",
            "origin_country": "India",
            "destination_country": "Canada",
            "hsn_code": "090422",
            "product_description": "Chilli flakes",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _csv_bytes(*, invoice: str = "INV-1", hsn: str = "090422", value: str = "1000") -> bytes:
    return (
        "Document,Commercial Invoice\n"
        f"Invoice No:,{invoice}\n"
        f"HSN:,{hsn}\n"
        f"Total Invoice Value:,{value}\n"
        "Product Description:,Chilli flakes\n"
    ).encode()


def test_create_verification_run(client) -> None:
    test_client, _ = client
    run_id = _create_run(test_client)
    detail = test_client.get(f"/api/v1/document-verifier/runs/{run_id}")
    assert detail.status_code == 200
    assert detail.json()["title"] == "Invoice audit"


def test_upload_document_and_reject_invalid_type(client) -> None:
    test_client, _ = client
    run_id = _create_run(test_client)
    ok = test_client.post(
        f"/api/v1/document-verifier/runs/{run_id}/documents",
        files=[("files", ("invoice.csv", _csv_bytes(), "text/csv"))],
    )
    assert ok.status_code == 200
    assert ok.json()["documents"][0]["file_type"] == "csv"

    bad = test_client.post(
        f"/api/v1/document-verifier/runs/{run_id}/documents",
        files=[("files", ("malware.exe", b"MZ", "application/octet-stream"))],
    )
    assert bad.status_code == 415


def test_extract_csv_fields_without_ai(client) -> None:
    test_client, _ = client
    run_id = _create_run(test_client)
    test_client.post(
        f"/api/v1/document-verifier/runs/{run_id}/documents",
        files=[("files", ("invoice.csv", _csv_bytes(), "text/csv"))],
    )
    resp = test_client.post(f"/api/v1/document-verifier/runs/{run_id}/extract")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["fields_extracted"] >= 2
    detail = test_client.get(f"/api/v1/document-verifier/runs/{run_id}").json()
    keys = {field["field_key"] for field in detail["fields"]}
    assert {"invoice_number", "hsn_code", "total_invoice_value"} <= keys


def test_extract_pdf_fields_with_mocked_ai(client, monkeypatch) -> None:
    test_client, _ = client
    run_id = _create_run(test_client)
    test_client.post(
        f"/api/v1/document-verifier/runs/{run_id}/documents",
        files=[("files", ("invoice.pdf", b"%PDF fake text", "application/pdf"))],
    )

    monkeypatch.setattr(verifier_module, "extract_document_text", lambda _raw, _type: ("Commercial Invoice", "pdfplumber"))
    monkeypatch.setattr(
        verifier_module,
        "extract_fields_with_ai_or_parser",
        lambda _text, _type: DocumentExtractionResult(
            document_type="commercial_invoice",
            parser_used="ai_json",
            fields=[
                ExtractedFieldValue(
                    field_key="invoice_number",
                    field_label="Invoice Number",
                    raw_value="INV-AI",
                    normalized_value="INV-AI",
                    confidence_score=91,
                    page_number=1,
                    evidence_excerpt="Invoice No: INV-AI",
                )
            ],
        ),
    )

    resp = test_client.post(f"/api/v1/document-verifier/runs/{run_id}/extract")
    assert resp.status_code == 200
    detail = test_client.get(f"/api/v1/document-verifier/runs/{run_id}").json()
    assert detail["documents"][0]["parser_used"] == "ai_json"
    assert detail["fields"][0]["raw_value"] == "INV-AI"


def test_pending_extraction_does_not_verify(client) -> None:
    test_client, _ = client
    run_id = _create_run(test_client)
    test_client.post(
        f"/api/v1/document-verifier/runs/{run_id}/documents",
        files=[("files", ("invoice.csv", _csv_bytes(), "text/csv"))],
    )
    resp = test_client.post(f"/api/v1/document-verifier/runs/{run_id}/verify")
    assert resp.status_code == 409
    assert "extracted" in resp.json()["detail"]


def test_mismatched_hsn_and_invoice_value_create_issues(client) -> None:
    test_client, _ = client
    run_id = _create_run(test_client)
    test_client.post(
        f"/api/v1/document-verifier/runs/{run_id}/documents",
        files=[
            ("files", ("invoice.csv", _csv_bytes(invoice="INV-1", hsn="090422", value="1000"), "text/csv")),
            ("files", ("shipping-bill.csv", _csv_bytes(invoice="INV-1", hsn="090421", value="1300"), "text/csv")),
        ],
    )
    assert test_client.post(f"/api/v1/document-verifier/runs/{run_id}/extract").status_code == 200
    verify = test_client.post(f"/api/v1/document-verifier/runs/{run_id}/verify")
    assert verify.status_code == 200, verify.text
    issues = test_client.get(f"/api/v1/document-verifier/runs/{run_id}/issues").json()
    issue_fields = {issue["field_key"] for issue in issues}
    assert "hsn_code" in issue_fields
    assert "total_invoice_value" in issue_fields
    assert verify.json()["high_count"] >= 1


def test_resolve_ignore_and_report_counts(client) -> None:
    test_client, _ = client
    run_id = _create_run(test_client)
    test_client.post(
        f"/api/v1/document-verifier/runs/{run_id}/documents",
        files=[
            ("files", ("invoice.csv", _csv_bytes(hsn="090422"), "text/csv")),
            ("files", ("packing.csv", _csv_bytes(hsn="090421"), "text/csv")),
        ],
    )
    test_client.post(f"/api/v1/document-verifier/runs/{run_id}/extract")
    test_client.post(f"/api/v1/document-verifier/runs/{run_id}/verify")
    issues = test_client.get(f"/api/v1/document-verifier/runs/{run_id}/issues").json()
    assert issues
    resolved = test_client.post(f"/api/v1/document-verifier/issues/{issues[0]['id']}/resolve")
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"
    ignored = test_client.post(f"/api/v1/document-verifier/issues/{issues[-1]['id']}/ignore")
    assert ignored.status_code == 200
    assert ignored.json()["status"] == "ignored"
    report = test_client.get(f"/api/v1/document-verifier/runs/{run_id}/report")
    assert report.status_code == 200
    assert report.json()["issues_count"] == len(issues)


def test_missing_required_document_from_ccr_creates_issue(client, session) -> None:
    test_client, org = client
    country = ComplianceCountry(tenant_id=org.id, name="Canada", region="North America")
    category = ProductCategory(tenant_id=org.id, name="Spices")
    session.add_all([country, category])
    session.flush()
    session.add(
        ComplianceRequirement(
            tenant_id=org.id,
            country_id=country.id,
            category_id=category.id,
            hsn_code="0904",
            product_keywords=["spice"],
            requirement_type="certificate",
            requirement_text="A phytosanitary certificate is required for this product.",
            source_url="https://apeda.gov.in/",
            source_name="APEDA",
            source_authority_level="official",
            confidence_score=80,
            status="active",
            review_status="approved",
            reviewed_by="test",
            reviewed_at=datetime.now(UTC),
            content_hash=f"test-{uuid.uuid4().hex}",
        )
    )
    session.commit()
    run_id = _create_run(test_client)
    test_client.post(
        f"/api/v1/document-verifier/runs/{run_id}/documents",
        files=[("files", ("invoice.csv", _csv_bytes(), "text/csv"))],
    )
    test_client.post(f"/api/v1/document-verifier/runs/{run_id}/extract")
    verify = test_client.post(f"/api/v1/document-verifier/runs/{run_id}/verify")
    assert verify.status_code == 200
    issues = test_client.get(f"/api/v1/document-verifier/runs/{run_id}/issues").json()
    assert any(issue["issue_type"] == "required_document_missing" for issue in issues)
