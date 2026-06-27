from fastapi.testclient import TestClient

from app.main import app


def _authenticated_client(email: str = "quote@example.com") -> tuple[TestClient, dict[str, str]]:
    client = TestClient(app)
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "StrongPassword123!",
            "organization_name": "Quote Exports",
            "full_name": "Quote Owner",
        },
    )
    assert response.status_code == 201
    token = response.json()["access_token"]
    return client, {"Authorization": f"Bearer {token}"}


def test_export_quote_uses_tenant_verified_rates() -> None:
    client, headers = _authenticated_client()
    csv_content = (
        "scheme,hsn,rate,source,effective_date,version_stamp,confidence,review_status\n"
        "RoDTEP,0904,1.40,Operator notification,2026-01-01T00:00:00Z,v1,verified,approved\n"
        "Duty Drawback,0904,0.75,Drawback schedule,2026-01-01T00:00:00Z,v1,verified,approved\n"
    )
    imported = client.post(
        "/api/v1/rates/import",
        headers=headers,
        files={"file": ("rates.csv", csv_content, "text/csv")},
    )
    assert imported.status_code == 200

    response = client.post(
        "/api/v1/tools/export-quote",
        headers=headers,
        json={
            "product_name": "Ground spices",
            "hsn_code": "09042220",
            "destination_country": "USA",
            "incoterm": "CIF",
            "quote_currency": "USD",
            "fob_value": 10000,
            "freight_value": 1200,
            "insurance_value": 100,
            "destination_charges_value": 250,
            "destination_duty_percent": 4,
            "domestic_charges_inr": 30000,
            "exchange_rate_to_inr": 83,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["cif_value"] == 11300
    assert body["buyer_landed_estimate"] == 12002
    assert body["fob_value_inr"] == 830000
    assert body["incentive_total_inr"] == 17845
    assert body["exporter_net_realization_inr"] == 817845
    assert {item["scheme"] for item in body["incentive_estimates"]} == {
        "RoDTEP",
        "Duty Drawback",
    }
    assert "Decision-support only" in body["disclaimer"]


def test_export_quote_requires_exchange_rate_for_incentive_amounts() -> None:
    client, headers = _authenticated_client("quote-no-fx@example.com")
    csv_content = (
        "scheme,hsn,rate,source,effective_date,version_stamp,confidence\n"
        "RoDTEP,6109,1.10,Operator notification,2026-01-01T00:00:00Z,v1,verified\n"
    )
    client.post(
        "/api/v1/rates/import",
        headers=headers,
        files={"file": ("rates.csv", csv_content, "text/csv")},
    )

    response = client.post(
        "/api/v1/tools/export-quote",
        headers=headers,
        json={
            "product_name": "Cotton shirts",
            "hsn_code": "610910",
            "destination_country": "UK",
            "quote_currency": "GBP",
            "fob_value": 5000,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["fob_value_inr"] is None
    assert body["incentive_total_inr"] == 0
    assert body["incentive_estimates"] == []
    assert any("exchange rate" in warning.lower() for warning in body["warnings"])
