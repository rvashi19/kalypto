# ruff: noqa: E501
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.main import app
from app.models import (
    HsnCode,
    IncentiveRate,
    IncentiveSourceEvidence,
    Membership,
    MembershipRole,
    Organization,
)
from app.services.hsn_normalization import InvalidHsnCodeError
from app.services.incentive_import import import_incentive_snapshot
from app.services.incentive_search import search_incentives

SAMPLE = Path(__file__).resolve().parents[1] / "app" / "scripts" / "data" / "incentive_sample.csv"


def _tenant(session) -> Organization:
    org = Organization(name="Demo", slug=f"demo-{datetime.now(UTC).timestamp()}")
    session.add(org)
    session.flush()
    return org


def _seed(session, tenant_id):
    return import_incentive_snapshot(
        session=session,
        tenant_id=tenant_id,
        raw_bytes=SAMPLE.read_bytes(),
        import_type="csv",
        source_name="sample",
        created_by="test",
    )


# ── normalization / validation ─────────────────────────────────────────────────


def test_minimum_hsn_validation(session):
    org = _tenant(session)
    with pytest.raises(InvalidHsnCodeError):
        search_incentives(session=session, tenant_id=org.id, hsn_code="1")


def test_no_product_text_classification(session):
    """Incentive Finder must not classify product text — a non-numeric query is rejected."""
    org = _tenant(session)
    with pytest.raises(InvalidHsnCodeError):
        search_incentives(session=session, tenant_id=org.id, hsn_code="turmeric")


# ── search visibility ──────────────────────────────────────────────────────────


def test_exact_approved_record_visible(session):
    org = _tenant(session)
    _seed(session, org.id)
    matches = search_incentives(session=session, tenant_id=org.id, hsn_code="12119030")
    assert len(matches) == 1
    assert matches[0].row.scheme == "rodtep"
    assert matches[0].row.approval_status == "approved"
    assert matches[0].match_level == "exact"


def test_pending_hidden_from_normal_user(session):
    org = _tenant(session)
    _seed(session, org.id)
    # 76129010 has only an expired RoDTEP + pending Drawback -> nothing visible.
    matches = search_incentives(session=session, tenant_id=org.id, hsn_code="76129010")
    assert matches == []


def test_expired_hidden_from_normal_user(session):
    org = _tenant(session)
    _seed(session, org.id)
    rows = search_incentives(session=session, tenant_id=org.id, hsn_code="76129010")
    assert all(r.row.approval_status == "approved" for r in rows) or rows == []
    assert rows == []  # the only RoDTEP row here is approved-but-expired -> hidden


def test_rejected_hidden_from_normal_user(session):
    org = _tenant(session)
    _seed(session, org.id)
    assert search_incentives(session=session, tenant_id=org.id, hsn_code="52010020") == []


def test_admin_sees_pending_and_expired(session):
    org = _tenant(session)
    _seed(session, org.id)
    matches = search_incentives(
        session=session, tenant_id=org.id, hsn_code="76129010", include_unapproved=True
    )
    statuses = {m.row.approval_status for m in matches}
    assert len(matches) == 2
    assert "pending" in statuses


def test_prefix_fallback(session):
    org = _tenant(session)
    csv = (
        b"scheme,hsn_code,rate_value,effective_from,source_name,approval_status\n"
        b"rodtep,1211,1.1,2023-04-01,DGFT,approved\n"
    )
    import_incentive_snapshot(
        session=session, tenant_id=org.id, raw_bytes=csv, import_type="csv", source_name="x"
    )
    matches = search_incentives(session=session, tenant_id=org.id, hsn_code="12119099")
    assert len(matches) == 1
    assert matches[0].row.normalized_hsn_code == "1211"
    assert matches[0].match_level == "prefix"


def test_source_evidence_recorded(session):
    org = _tenant(session)
    _seed(session, org.id)
    rate = session.scalars(
        select(IncentiveRate).where(IncentiveRate.normalized_hsn_code == "12119030")
    ).first()
    evidence = session.scalars(
        select(IncentiveSourceEvidence).where(IncentiveSourceEvidence.incentive_rate_id == rate.id)
    ).all()
    assert evidence
    assert evidence[0].evidence_type == "rodtep_schedule"


def test_import_idempotent(session):
    org = _tenant(session)
    first = _seed(session, org.id)
    total_after_first = session.scalar(select(func.count()).select_from(IncentiveRate))
    second = _seed(session, org.id)
    total_after_second = session.scalar(select(func.count()).select_from(IncentiveRate))
    assert total_after_first == total_after_second
    assert second.job.records_created == 0
    assert second.job.records_updated == first.job.records_created


def test_reimport_identical_keeps_approved(session):
    org = _tenant(session)
    _seed(session, org.id)
    # An identical re-import (no field changes) must not knock an approved rate back to review.
    _seed(session, org.id)
    row = session.scalars(
        select(IncentiveRate).where(IncentiveRate.normalized_hsn_code == "12119030")
    ).first()
    assert row.approval_status == "approved"


# ── endpoint tests ─────────────────────────────────────────────────────────────


def _admin_client() -> tuple[TestClient, dict[str, str]]:
    client = TestClient(app)
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "incadmin@example.com",
            "password": "StrongPassword123!",
            "organization_name": "Incentive Admin Org",
            "full_name": "Inc Admin",
        },
    )
    assert response.status_code == 201
    return client, {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_search_endpoint_hsn_exists_no_rate_message(session):
    client, headers = _admin_client()
    session.add(
        HsnCode(
            code="09103030",
            normalized_code="09103030",
            digit_level=8,
            description="Turmeric powder",
            source_name="seed",
            is_active=True,
        )
    )
    session.commit()
    response = client.get(
        "/api/v1/incentives/search", headers=headers, params={"hsn_code": "09103030"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 0
    assert body["hsn_exists"] is True
    assert "HSN exists" in body["message"]


def test_admin_only_import_endpoint(session):
    client, headers = _admin_client()
    files = {"file": ("incentive_sample.csv", SAMPLE.read_bytes(), "text/csv")}
    data = {"source_name": "sample", "import_type": "csv"}
    ok = client.post("/api/v1/incentives/import", headers=headers, files=files, data=data)
    assert ok.status_code == 201, ok.text
    assert ok.json()["records_created"] > 0

    membership = session.scalars(select(Membership)).first()
    membership.role = MembershipRole.READ_ONLY
    session.commit()
    forbidden = client.post(
        "/api/v1/incentives/import",
        headers=headers,
        files={"file": ("incentive_sample.csv", SAMPLE.read_bytes(), "text/csv")},
        data=data,
    )
    assert forbidden.status_code == 403


def test_detail_and_approve_flow(session):
    client, headers = _admin_client()
    files = {"file": ("incentive_sample.csv", SAMPLE.read_bytes(), "text/csv")}
    client.post(
        "/api/v1/incentives/import",
        headers=headers,
        files=files,
        data={"source_name": "sample", "import_type": "csv"},
    )
    # Pending drawback on 76129010: admin can see it and approve it.
    admin_search = client.get(
        "/api/v1/incentives/search",
        headers=headers,
        params={"hsn_code": "76129010", "include_unapproved": "true"},
    )
    pending = next(r for r in admin_search.json()["results"] if r["approval_status"] == "pending")
    detail = client.get(f"/api/v1/incentives/{pending['id']}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["source_evidence"]
    approved = client.post(f"/api/v1/incentives/{pending['id']}/approve", headers=headers)
    assert approved.status_code == 200
    assert approved.json()["approval_status"] == "approved"


def test_legacy_shipments_hsn_rates_still_works():
    client, headers = _admin_client()
    response = client.get("/api/v1/shipments/hsn-rates", headers=headers, params={"hsn": "12119030"})
    assert response.status_code == 200
    assert "found" in response.json()
