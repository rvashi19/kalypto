from auth_helpers import authenticated_client
from fastapi.testclient import TestClient


def _authenticated_client(session) -> tuple[TestClient, dict[str, str]]:
    client, headers, _ = authenticated_client(
        session,
        email="workflow@example.com",
        organization_name="Workflow Exports",
        full_name="Workflow Owner",
    )
    return client, headers


def test_shipment_create_generate_and_download_workflow(session) -> None:
    client, headers = _authenticated_client(session)
    created = client.post(
        "/api/v1/shipments",
        headers=headers,
        json={
            "exporter_name": "Workflow Exports",
            "product_name": "Cotton shirts",
            "hsn_code": "620520",
            "destination_country": "United Kingdom",
            "buyer_country": "United Kingdom",
            "incoterm": "FOB",
            "payment_term": "TT advance",
            "shipment_mode": "sea",
            "shipment_stage": "pre_shipment",
            "fob_value": 100000,
            "invoice_currency": "INR",
        },
    )
    assert created.status_code == 201
    shipment_id = created.json()["id"]

    generated = client.post(
        f"/api/v1/shipments/{shipment_id}/documents/generate/commercial_invoice",
        headers=headers,
    )
    assert generated.status_code == 201
    document = generated.json()
    assert document["mime_type"] == "application/pdf"

    downloaded = client.get(
        f"/api/v1/shipments/{shipment_id}/documents/{document['id']}/download",
        headers=headers,
    )
    assert downloaded.status_code == 200
    assert downloaded.content.startswith(b"%PDF")

    reconciled = client.post(
        f"/api/v1/shipments/{shipment_id}/reconcile",
        headers=headers,
    )
    assert reconciled.status_code == 200
    assert reconciled.json()["discrepancies"]

    dashboard = client.get("/api/v1/dashboard/discrepancies", headers=headers)
    assert dashboard.status_code == 200
    assert dashboard.json()["total"] == len(reconciled.json()["discrepancies"])


def test_csv_import_reports_invalid_rows_without_losing_valid_rows(session) -> None:
    client, headers = _authenticated_client(session)
    csv_content = (
        "exporter_name,product_name,hsn_code,destination_country,buyer_country,"
        "incoterm,payment_term,shipment_mode,shipment_stage,invoice_currency\n"
        "Workflow Exports,Tea,0902,Canada,Canada,FOB,TT advance,sea,pre_shipment,INR\n"
        "Workflow Exports,,0902,Canada,Canada,FOB,TT advance,sea,pre_shipment,INR\n"
    )

    response = client.post(
        "/api/v1/shipments/import",
        headers=headers,
        files={"file": ("shipments.csv", csv_content, "text/csv")},
    )

    assert response.status_code == 200
    assert response.json()["created"] == 1
    assert response.json()["failed"] == 1


def test_operator_rate_import_drives_hsn_lookup(session) -> None:
    client, headers = _authenticated_client(session)
    csv_content = (
        "scheme,hsn,rate,source,effective_date,version_stamp,confidence,review_status\n"
        "RoDTEP,0902,1.25,Operator notification,2026-01-01T00:00:00Z,v1,verified,approved\n"
    )
    imported = client.post(
        "/api/v1/rates/import",
        headers=headers,
        files={"file": ("rates.csv", csv_content, "text/csv")},
    )
    assert imported.status_code == 200
    assert imported.json()["created"] == 1

    lookup = client.get(
        "/api/v1/shipments/hsn-rates?hsn=090240&fob_value=100000",
        headers=headers,
    )
    assert lookup.status_code == 200
    assert lookup.json()["rodtep_rate"] == 1.25
    assert lookup.json()["rate_evidence"][0]["source"] == "Operator notification"
