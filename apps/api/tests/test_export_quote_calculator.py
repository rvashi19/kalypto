# ruff: noqa: E501
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from auth_helpers import authenticated_client
from fastapi.testclient import TestClient

from app.models import IncentiveRate, Organization
from app.services.export_quote_calc import QuoteInputs, ResolvedIncentive, calculate_quote

# Reference scenario from the FOB-CIF spreadsheet (Cumin, 28t).
CUMIN = dict(
    incoterm="CIF",
    quote_currency="INR",
    quantity=28000,
    unit_price=125,
    product_value=3_500_000,
    misc_origin_charges=165_900,  # aggregate origin/export expenses
    freight_cost=58_100,
    general_insurance=0,
)


def _calc(**overrides):
    data = {**CUMIN, **overrides}
    return calculate_quote(QuoteInputs(**data))


# ── calculation engine ─────────────────────────────────────────────────────────


def test_product_value_defaults_to_qty_times_price():
    result = calculate_quote(QuoteInputs(incoterm="FOB", quote_currency="INR", quantity=28000, unit_price=125))
    assert result["product_value"] == 3_500_000.0


def test_fob_cfr_cif_reference_values():
    r = _calc()
    assert r["fob_value"] == 3_665_900.0
    assert r["cfr_value"] == 3_724_000.0  # fob + freight
    assert r["cif_value"] == 3_724_000.0  # + 0 insurance
    assert r["fob_per_unit"] == 130.93
    assert r["cif_per_unit"] == 133.00


def test_landed_cost_with_duty_and_tax():
    r = _calc(import_duty_rate=5, destination_tax_rate=5, destination_handling_charges=10000)
    duty = round(3_724_000 * 0.05, 2)
    tax = round((3_724_000 + duty) * 0.05, 2)
    assert r["import_duty_amount"] == duty
    assert r["destination_tax_amount"] == tax
    assert r["total_landed_cost"] == round(3_724_000 + duty + tax + 10000, 2)


def test_user_provided_duty_amount_and_warning():
    r = _calc(import_duty_amount=100000)
    assert r["import_duty_amount"] == 100000.0
    assert r["buyer_landed_cost_breakdown"]["import_duty_user_provided"] is True
    assert any("user-provided" in w.lower() for w in r["warnings"])


def test_net_realization_without_incentives_warns():
    r = _calc(exporter_cost_of_goods=3_360_000, exporter_overheads=20000)
    # gross = cif invoice value; no incentives added
    assert r["incentive_amount"] == 0.0
    assert r["gross_exporter_realization"] == 3_724_000.0
    assert r["net_exporter_realization"] == round(3_724_000 - 3_360_000 - 20000, 2)
    assert any("without incentives" in w for w in r["warnings"])


def test_net_realization_with_incentives():
    r = _calc(
        incentives=[
            ResolvedIncentive(scheme="rodtep", rate=5.0, source="approved_source_backed"),
            ResolvedIncentive(scheme="drawback", rate=1.5, source="approved_source_backed"),
        ]
    )
    assert r["incentive_amount"] == round(3_665_900 * 0.05 + 3_665_900 * 0.015, 2)  # on FOB
    rodtep = next(i for i in r["incentive_breakdown"] if i["scheme"] == "rodtep")
    assert rodtep["amount_inr"] == 183_295.0
    assert rodtep["source"] == "approved_source_backed"


def test_user_provided_incentive_labelled():
    r = _calc(incentives=[ResolvedIncentive(scheme="rodtep", rate=5.0, source="user_provided")])
    assert any("user-provided" in w for w in r["warnings"])


def test_invalid_quantity_raises():
    with pytest.raises(ValueError):
        calculate_quote(QuoteInputs(incoterm="FOB", quote_currency="INR", quantity=0, unit_price=1))


def test_incoterm_invoice_basis():
    fob = _calc(incoterm="FOB")["invoice_value"]
    cif = _calc(incoterm="CIF")["invoice_value"]
    exw = _calc(incoterm="EXW")["invoice_value"]
    assert exw == 3_500_000.0 and fob == 3_665_900.0 and cif == 3_724_000.0


# ── endpoints ──────────────────────────────────────────────────────────────────


def _client(session, email: str = "eq@example.com") -> tuple[TestClient, dict[str, str]]:
    client, headers, _ = authenticated_client(
        session,
        email=email,
        organization_name="EQ Org",
        full_name="EQ",
    )
    return client, headers


def _payload(**overrides):
    return {
        "incoterm": "CIF", "quote_currency": "INR", "hsn_code": "0910.99",
        "quantity": 28000, "unit_price": 125, "misc_origin_charges": 165900,
        "freight_cost": 58100, **overrides,
    }


def test_calculate_endpoint_normalizes_hsn_and_computes(session):
    client, headers = _client(session)
    r = client.post("/api/v1/calculators/export-quote/calculate", headers=headers, json=_payload())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["hsn_code"] == "091099"  # normalized
    assert body["fob_value"] == 3_665_900.0
    assert body["cif_value"] == 3_724_000.0
    assert body["disclaimer"]


def test_calculate_uses_approved_incentives(session):
    client, headers = _client(session)
    org = session.scalars(select_org()).first()
    session.add(
        IncentiveRate(
            tenant_id=org.id, scheme="rodtep", hsn_code="091099", normalized_hsn_code="091099",
            digit_level=6, rate_type="percentage", rate_value=5.0, effective_from=datetime(2023, 4, 1, tzinfo=UTC),
            source_name="DGFT", approval_status="approved", is_active=True,
        )
    )
    session.commit()
    r = client.post("/api/v1/calculators/export-quote/calculate", headers=headers, json=_payload())
    body = r.json()
    assert body["incentive_amount"] == 183_295.0
    assert body["incentive_breakdown"][0]["source"] == "approved_source_backed"


def test_save_get_list_duplicate_flow(session):
    client, headers = _client(session)
    saved = client.post("/api/v1/calculators/export-quote/save", headers=headers, json=_payload(buyer_name="Al Maya"))
    assert saved.status_code == 201, saved.text
    quote_id = saved.json()["id"]
    assert saved.json()["calculation"]["fob_value"] == 3_665_900.0

    got = client.get(f"/api/v1/calculators/export-quote/{quote_id}", headers=headers)
    assert got.status_code == 200
    assert got.json()["calculation"]["cif_value"] == 3_724_000.0

    listed = client.get("/api/v1/calculators/export-quote", headers=headers)
    assert listed.status_code == 200 and len(listed.json()) >= 1

    dup = client.post(f"/api/v1/calculators/export-quote/{quote_id}/duplicate", headers=headers)
    assert dup.status_code == 201
    assert dup.json()["id"] != quote_id
    assert dup.json()["status"] == "draft"


def test_tenant_scoping_hides_other_quotes(session):
    client_a, headers_a = _client(session, "eqa@example.com")
    saved = client_a.post("/api/v1/calculators/export-quote/save", headers=headers_a, json=_payload())
    quote_id = saved.json()["id"]

    client_b, headers_b = _client(session, "eqb@example.com")
    blocked = client_b.get(f"/api/v1/calculators/export-quote/{quote_id}", headers=headers_b)
    assert blocked.status_code == 404


def test_invalid_quantity_endpoint(session):
    client, headers = _client(session)
    r = client.post("/api/v1/calculators/export-quote/calculate", headers=headers, json=_payload(quantity=0))
    assert r.status_code == 422


def select_org():
    from sqlalchemy import select

    return select(Organization).order_by(Organization.created_at)
