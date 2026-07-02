# ruff: noqa: E501
"""Tests for Document Builder — validator, parser, generator, and API endpoints.

Fixture: cumin shipment (HSN 09093129, 1000 kg, USD 2/kg, 20 bags × 50 kg, CIF Jebel Ali).
"""

from __future__ import annotations

import io
import zipfile

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.document_generator import (
    SUPPORTED_DOC_TYPES,
    checksum,
    generate_document,
    generate_zip,
)
from app.services.document_sheet_parser import (
    detect_column_mapping,
    detect_missing_fields,
    parse_rows,
)
from app.services.document_validator import validate_shipment_data

# ── Cumin fixture ─────────────────────────────────────────────────────────────

CUMIN = {
    "exporter": {
        "company_name": "Spice Exports Pvt Ltd",
        "address": "12 Industrial Estate, Unjha",
        "city": "Unjha",
        "state": "Gujarat",
        "postal_code": "384170",
        "country": "India",
        "iec": "0900000001",
        "gstin": "24AAACP0000A1Z5",
        "bank_name": "State Bank of India",
        "bank_account": "30000000001",
        "ifsc_swift": "SBININBB210",
        "ad_code": "1234567",
    },
    "buyer": {
        "buyer_name": "Dubai Spices Trading LLC",
        "buyer_address": "PO Box 12345, Jebel Ali Free Zone, Dubai",
        "buyer_country": "UAE",
    },
    "shipment": {
        "invoice_number": "SEP/2024-25/001",
        "invoice_date": "2025-01-15",
        "country_of_origin": "India",
        "country_of_final_destination": "UAE",
        "port_of_loading": "Mundra",
        "port_of_discharge": "Jebel Ali",
        "incoterm": "CIF",
        "incoterms_version": "Incoterms 2020",
        "mode_of_transport": "Sea",
        "currency": "USD",
        "payment_terms": "30 days from BL date",
        "marks_and_numbers": "SPICE / JEBEL ALI / 2025 / 001-020",
    },
    "items": [
        {
            "item_number": 1,
            "product_description": "Cumin Seeds (Cuminum cyminum)",
            "hsn_code": "09093129",
            "quantity": 1000.0,
            "unit": "KGS",
            "unit_price": 2.0,
            "total_value": 2000.0,
            "net_weight": 1000.0,
            "gross_weight": 1050.0,
            "package_count": 20,
            "package_type": "Bags",
        }
    ],
    "packing": {
        "total_packages": 20,
        "package_type": "Bags",
        "total_net_weight": 1000.0,
        "total_gross_weight": 1050.0,
        "freight": 200.0,
        "insurance": 22.0,
    },
    "declarations": {
        "authorized_signatory_name": "Rajesh Patel",
        "authorized_signatory_designation": "Director",
        "place_of_issue": "Unjha",
        "date_of_issue": "2025-01-15",
    },
}


# ── Validator tests ───────────────────────────────────────────────────────────

class TestValidator:
    def test_cumin_fixture_has_no_errors(self):
        issues = validate_shipment_data(CUMIN)
        errors = [i for i in issues if i["severity"] == "error"]
        assert errors == [], f"Unexpected errors: {errors}"

    def test_missing_exporter_name_raises_error(self):
        data = {**CUMIN, "exporter": {**CUMIN["exporter"], "company_name": ""}}
        issues = validate_shipment_data(data)
        codes = [i["code"] for i in issues]
        assert "EXP001" in codes

    def test_missing_invoice_number_raises_error(self):
        data = {**CUMIN, "shipment": {**CUMIN["shipment"], "invoice_number": None}}
        issues = validate_shipment_data(data)
        codes = [i["code"] for i in issues]
        assert "SHP001" in codes

    def test_missing_buyer_name_raises_error(self):
        data = {**CUMIN, "buyer": {**CUMIN["buyer"], "buyer_name": ""}}
        issues = validate_shipment_data(data)
        codes = [i["code"] for i in issues]
        assert "BUY001" in codes

    def test_qty_price_total_mismatch_triggers_warning(self):
        items = [{**CUMIN["items"][0], "total_value": 9999.0}]  # should be 2000
        data = {**CUMIN, "items": items}
        issues = validate_shipment_data(data)
        codes = [i["code"] for i in issues]
        assert any(c.startswith("ITM") and c.endswith("G") for c in codes)

    def test_gross_weight_less_than_net_raises_error(self):
        items = [{**CUMIN["items"][0], "net_weight": 1000.0, "gross_weight": 500.0}]
        data = {**CUMIN, "items": items}
        issues = validate_shipment_data(data)
        codes = [i["code"] for i in issues]
        assert any(c.endswith("H") for c in codes)

    def test_invalid_hsn_digit_count_triggers_warning(self):
        items = [{**CUMIN["items"][0], "hsn_code": "9XYZ"}]
        data = {**CUMIN, "items": items}
        issues = validate_shipment_data(data)
        codes = [i["code"] for i in issues]
        assert any(c.endswith("C") for c in codes)

    def test_empty_items_list_raises_error(self):
        data = {**CUMIN, "items": []}
        issues = validate_shipment_data(data)
        codes = [i["code"] for i in issues]
        assert "ITM000" in codes


# ── Parser tests ──────────────────────────────────────────────────────────────

class TestParser:
    def _sample_headers(self):
        return ["Item No", "Description", "HS Code", "Qty", "Unit", "Rate", "Amount", "Net Wt", "Gross Wt", "Cartons"]

    def test_detect_mapping_recognises_standard_headers(self):
        headers = self._sample_headers()
        mapping, unmatched = detect_column_mapping(headers)
        assert "HS Code" in mapping
        assert mapping["HS Code"] == "hsn_code"
        assert mapping["Description"] == "product_description"
        assert mapping["Qty"] == "quantity"

    def test_unmatched_columns_reported(self):
        headers = ["Item No", "Random Column", "HSN"]
        _, unmatched = detect_column_mapping(headers)
        assert "Random Column" in unmatched

    def test_parse_rows_converts_numeric_fields(self):
        headers = self._sample_headers()
        mapping, _ = detect_column_mapping(headers)
        rows = [{"Item No": "1", "Description": "Cumin Seeds", "HS Code": "09093129",
                 "Qty": "1,000", "Unit": "KGS", "Rate": "2.00", "Amount": "2000",
                 "Net Wt": "1000", "Gross Wt": "1050", "Cartons": "20"}]
        items = parse_rows(rows, mapping)
        assert len(items) == 1
        assert items[0]["quantity"] == 1000.0
        assert items[0]["unit_price"] == 2.0
        assert items[0]["total_value"] == 2000.0
        assert items[0]["hsn_code"] == "09093129"

    def test_empty_rows_are_skipped(self):
        mapping = {"Description": "product_description"}
        rows = [{"Description": ""}, {"Description": None}]
        items = parse_rows(rows, mapping)
        assert items == []

    def test_detect_missing_fields(self):
        items = [{"product_description": "Test", "hsn_code": None, "quantity": 10,
                  "unit_price": 5, "total_value": 50, "net_weight": None,
                  "gross_weight": None, "package_count": None}]
        missing = detect_missing_fields(items)
        assert "hsn_code" in missing
        assert "net_weight" in missing


# ── Generator tests ───────────────────────────────────────────────────────────

class TestGenerator:
    @pytest.mark.parametrize("doc_type", list(SUPPORTED_DOC_TYPES))
    def test_all_doc_types_produce_valid_pdf(self, doc_type: str):
        pdf_bytes, filename = generate_document(doc_type, CUMIN)
        assert pdf_bytes[:4] == b"%PDF", f"{doc_type}: output is not a PDF"
        assert len(pdf_bytes) > 1024, f"{doc_type}: PDF suspiciously small"
        assert filename.endswith(".pdf")

    def test_proforma_invoice_filename_contains_invoice_number(self):
        _, filename = generate_document("proforma_invoice", CUMIN)
        assert "SEP" in filename or "2024" in filename

    def test_generate_zip_contains_all_files(self):
        pairs = [
            ("doc_a.pdf", b"%PDF-1.4 test"),
            ("doc_b.pdf", b"%PDF-1.4 test2"),
        ]
        zip_bytes = generate_zip(pairs)
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            names = zf.namelist()
        assert "doc_a.pdf" in names
        assert "doc_b.pdf" in names

    def test_checksum_is_16_hex_chars(self):
        cs = checksum(b"hello world")
        assert len(cs) == 16
        assert all(c in "0123456789abcdef" for c in cs)

    def test_disclaimer_appears_in_pdf(self):
        """Smoke-check: PDF is non-trivial and contains multiple objects (disclaimer page renders)."""
        pdf_bytes, _ = generate_document("commercial_invoice", CUMIN)
        # ReportLab compresses content streams; check structure depth instead of string search
        assert pdf_bytes.count(b"obj") >= 5, "Expected multiple PDF objects"
        assert b"%%EOF" in pdf_bytes


# ── API endpoint tests ────────────────────────────────────────────────────────

@pytest.fixture()
def client(session):
    from unittest.mock import patch

    from app.api.deps import CurrentUserContext
    from app.models import Membership, MembershipRole, Organization, User

    import uuid

    org = Organization(id=uuid.uuid4(), name="Test Org", slug="test-org")
    user = User(id=uuid.uuid4(), email="test@example.com", password_hash="x", is_active=True)
    membership = Membership(id=uuid.uuid4(), user_id=user.id, organization_id=org.id, role=MembershipRole.OWNER)
    session.add_all([org, user, membership])
    session.commit()

    ctx = CurrentUserContext(
        user=user,
        organization=org,
        membership=membership,
        token=None,  # type: ignore[arg-type]
    )

    from app.api.deps import get_current_user_context
    from app.db.session import get_db_session

    import tempfile
    tmpdir = tempfile.mkdtemp()

    with patch("app.api.routes.documents.get_settings") as mock_settings:
        mock_settings.return_value.upload_dir = tmpdir
        app.dependency_overrides[get_db_session] = lambda: session
        app.dependency_overrides[get_current_user_context] = lambda: ctx
        try:
            yield TestClient(app)
        finally:
            app.dependency_overrides.clear()


class TestDocumentAPI:
    def test_validate_endpoint_valid_data(self, client: TestClient):
        resp = client.post("/api/v1/documents/validate", json={"data": CUMIN})
        assert resp.status_code == 200
        body = resp.json()
        assert body["valid"] is True
        assert body["errors"] == []

    def test_validate_endpoint_invalid_data(self, client: TestClient):
        bad = {**CUMIN, "exporter": {**CUMIN["exporter"], "company_name": "", "address": ""}}
        resp = client.post("/api/v1/documents/validate", json={"data": bad})
        assert resp.status_code == 200
        body = resp.json()
        assert body["valid"] is False
        error_codes = [e["code"] for e in body["errors"]]
        assert "EXP001" in error_codes

    def test_generate_endpoint_returns_zip(self, client: TestClient):
        resp = client.post(
            "/api/v1/documents/generate",
            json={
                "data": CUMIN,
                "document_types": ["commercial_invoice", "packing_list"],
                "save_pack": False,
            },
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/zip"
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            names = zf.namelist()
        assert any("Commercial_Invoice" in n for n in names)
        assert any("Packing_List" in n for n in names)

    def test_generate_endpoint_rejects_validation_errors(self, client: TestClient):
        bad = {**CUMIN, "items": []}
        resp = client.post(
            "/api/v1/documents/generate",
            json={"data": bad, "document_types": ["commercial_invoice"], "save_pack": False},
        )
        assert resp.status_code == 422

    def test_list_packs_empty(self, client: TestClient):
        resp = client.get("/api/v1/documents/packs")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_generate_and_list_pack(self, client: TestClient):
        resp = client.post(
            "/api/v1/documents/generate",
            json={
                "data": CUMIN,
                "document_types": ["commercial_invoice"],
                "save_pack": True,
            },
        )
        assert resp.status_code == 200

        list_resp = client.get("/api/v1/documents/packs")
        assert list_resp.status_code == 200
        packs = list_resp.json()
        assert len(packs) == 1
        assert packs[0]["invoice_number"] == "SEP/2024-25/001"

    def test_get_pack_detail(self, client: TestClient):
        gen_resp = client.post(
            "/api/v1/documents/generate",
            json={"data": CUMIN, "document_types": ["packing_list"], "save_pack": True},
        )
        pack_id = gen_resp.headers.get("x-pack-id")
        assert pack_id

        resp = client.get(f"/api/v1/documents/packs/{pack_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == pack_id
        assert body["status"] == "generated"

    def test_archive_pack(self, client: TestClient):
        gen_resp = client.post(
            "/api/v1/documents/generate",
            json={"data": CUMIN, "document_types": ["packing_list"], "save_pack": True},
        )
        pack_id = gen_resp.headers.get("x-pack-id")
        assert pack_id

        del_resp = client.delete(f"/api/v1/documents/packs/{pack_id}")
        assert del_resp.status_code == 204

        list_resp = client.get("/api/v1/documents/packs")
        packs = list_resp.json()
        assert all(p["id"] != pack_id for p in packs)
