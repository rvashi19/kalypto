# ruff: noqa: E501
from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.main import app
from app.models import IncentiveRate, IncentiveSource, Organization
from app.services import incentive_sources
from app.services.incentive_import import import_incentive_snapshot
from app.services.incentive_search import search_incentives
from app.services.incentive_sources import is_due, refresh_source, register_source

_CSV_NO_STATUS = (
    b"scheme,hsn_code,rate_value,effective_from,source_name\n"
    b"rodtep,12119030,1.4,2023-04-01,DGFT RoDTEP\n"
)


def _tenant(session) -> Organization:
    org = Organization(name="Demo", slug=f"demo-{datetime.now(UTC).timestamp()}")
    session.add(org)
    session.flush()
    return org


def test_official_import_defaults_to_pending_and_hidden(session):
    org = _tenant(session)
    import_incentive_snapshot(
        session=session, tenant_id=org.id, raw_bytes=_CSV_NO_STATUS, import_type="csv", source_name="DGFT"
    )
    row = session.scalars(select(IncentiveRate).where(IncentiveRate.normalized_hsn_code == "12119030")).first()
    assert row.approval_status == "pending"
    # Hidden from normal users until approved.
    assert search_incentives(session=session, tenant_id=org.id, hsn_code="12119030") == []


def test_changed_approved_rate_goes_to_needs_review(session):
    org = _tenant(session)
    approved = (
        b"scheme,hsn_code,rate_value,effective_from,source_name,approval_status\n"
        b"rodtep,12119030,1.4,2023-04-01,DGFT,approved\n"
    )
    import_incentive_snapshot(session=session, tenant_id=org.id, raw_bytes=approved, import_type="csv", source_name="DGFT")
    assert search_incentives(session=session, tenant_id=org.id, hsn_code="12119030")  # visible

    changed = (
        b"scheme,hsn_code,rate_value,effective_from,source_name\n"
        b"rodtep,12119030,2.0,2023-04-01,DGFT\n"
    )
    import_incentive_snapshot(session=session, tenant_id=org.id, raw_bytes=changed, import_type="csv", source_name="DGFT")
    row = session.scalars(select(IncentiveRate).where(IncentiveRate.normalized_hsn_code == "12119030")).first()
    assert row.approval_status == "needs_review"
    assert search_incentives(session=session, tenant_id=org.id, hsn_code="12119030") == []  # hidden again


def test_anomaly_note_flags_out_of_range(session):
    org = _tenant(session)
    bad = (
        b"scheme,hsn_code,rate_value,effective_from,source_name\n"
        b"rodtep,12119030,150,2023-04-01,DGFT\n"
    )
    import_incentive_snapshot(session=session, tenant_id=org.id, raw_bytes=bad, import_type="csv", source_name="DGFT")
    row = session.scalars(select(IncentiveRate).where(IncentiveRate.normalized_hsn_code == "12119030")).first()
    assert row.review_note and "0" in row.review_note


def test_register_source_and_due(session):
    org = _tenant(session)
    source = register_source(
        session=session,
        tenant_id=org.id,
        scheme="rodtep",
        source_name="DGFT RoDTEP Appendix 4R",
        source_type="csv",
        source_url="https://www.dgft.gov.in/rodtep.csv",
        refresh_interval_days=3,
        created_by="test",
    )
    assert source.last_status == "registered"
    assert is_due(source) is True  # never fetched


def test_refresh_source_imports_pending(session, monkeypatch):
    org = _tenant(session)
    source = register_source(
        session=session,
        tenant_id=org.id,
        scheme="rodtep",
        source_name="DGFT RoDTEP",
        source_type="csv",
        source_url="https://www.dgft.gov.in/rodtep.csv",
        refresh_interval_days=3,
    )
    monkeypatch.setattr(incentive_sources, "_download", lambda url: _CSV_NO_STATUS)
    outcome = refresh_source(session=session, source=source)
    assert outcome.result.job.records_created == 1
    row = session.scalars(select(IncentiveRate).where(IncentiveRate.source_id == source.id)).first()
    assert row is not None
    assert row.approval_status == "pending"
    assert source.last_status == "completed"
    assert source.last_records == 1
    assert is_due(source) is False  # just fetched


# ── endpoints ──────────────────────────────────────────────────────────────────


def _admin_client() -> tuple[TestClient, dict[str, str]]:
    client = TestClient(app)
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "srcadmin@example.com",
            "password": "StrongPassword123!",
            "organization_name": "Src Admin Org",
            "full_name": "Src Admin",
        },
    )
    assert response.status_code == 201
    return client, {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_sources_register_list_endpoints():
    client, headers = _admin_client()
    created = client.post(
        "/api/v1/incentives/sources",
        headers=headers,
        json={
            "source_name": "DGFT RoDTEP Appendix 4R",
            "scheme": "rodtep",
            "source_url": "https://www.dgft.gov.in/rodtep.csv",
            "source_type": "csv",
            "refresh_interval_days": 3,
        },
    )
    assert created.status_code == 201
    listed = client.get("/api/v1/incentives/sources", headers=headers)
    assert listed.status_code == 200
    assert any(s["due_for_refresh"] for s in listed.json())


def test_pending_queue_approve_and_reject_flow():
    client, headers = _admin_client()
    files = {"file": ("rates.csv", _CSV_NO_STATUS, "text/csv")}
    imported = client.post(
        "/api/v1/incentives/import", headers=headers, files=files, data={"source_name": "DGFT", "import_type": "csv"}
    )
    assert imported.status_code == 201
    pending = client.get("/api/v1/incentives/pending", headers=headers)
    assert pending.status_code == 200
    assert len(pending.json()) >= 1
    rate_id = pending.json()[0]["id"]

    approved = client.post(f"/api/v1/incentives/{rate_id}/approve", headers=headers)
    assert approved.status_code == 200
    assert approved.json()["approval_status"] == "approved"
    # Now visible in normal search.
    search = client.get("/api/v1/incentives/search", headers=headers, params={"hsn_code": "12119030"})
    assert search.json()["count"] == 1


def test_bulk_approve_pending():
    client, headers = _admin_client()
    csv = (
        b"scheme,hsn_code,rate_value,effective_from,source_name\n"
        b"rodtep,12119030,1.4,2023-04-01,DGFT\n"
        b"drawback,10063020,2.2,2023-04-01,CBIC\n"
    )
    client.post(
        "/api/v1/incentives/import",
        headers=headers,
        files={"file": ("rates.csv", csv, "text/csv")},
        data={"source_name": "DGFT", "import_type": "csv"},
    )
    assert len(client.get("/api/v1/incentives/pending", headers=headers).json()) == 2
    result = client.post("/api/v1/incentives/bulk-approve", headers=headers, json={})
    assert result.status_code == 200
    assert result.json()["approved"] == 2
    assert client.get("/api/v1/incentives/pending", headers=headers).json() == []
    assert client.get(
        "/api/v1/incentives/search", headers=headers, params={"hsn_code": "12119030"}
    ).json()["count"] == 1


def test_empty_state_when_no_approved_source():
    client, headers = _admin_client()
    response = client.get("/api/v1/incentives/search", headers=headers, params={"hsn_code": "99011100"})
    body = response.json()
    assert body["count"] == 0
    assert body["message"]


def test_total_sources_table_isolated(session):
    org = _tenant(session)
    register_source(
        session=session, tenant_id=org.id, scheme=None, source_name="X", source_type="csv"
    )
    assert session.scalar(select(func.count()).select_from(IncentiveSource)) >= 1
