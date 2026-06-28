# ruff: noqa: E501
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.main import app
from app.models import HsnClassificationQuery, HsnCode, Membership, MembershipRole
from app.services.hsn_import import import_hsn_snapshot
from app.services.hsn_normalization import (
    InvalidHsnCodeError,
    digit_level,
    hierarchy,
    normalize_code,
    normalize_strict,
)
from app.services.hsn_search import search_hsn

SAMPLE_CSV = Path(__file__).resolve().parents[1] / "app" / "scripts" / "data" / "hsn_sample.csv"


def _seed(session, *, source_version="itchs-2022", commit=True):
    return import_hsn_snapshot(
        session=session,
        raw_bytes=SAMPLE_CSV.read_bytes(),
        import_type="csv",
        source_name="DGFT ITC(HS) sample",
        source_url="https://www.dgft.gov.in/CP/",
        source_document_title="ITC(HS) 2022 schedule (sample)",
        source_document_date="2022-01-01",
        source_version=source_version,
        created_by="test",
        commit=commit,
    )


# ── normalization ──────────────────────────────────────────────────────────────


def test_normalize_strips_non_digits():
    assert normalize_code("0910.30.10") == "09103010"
    assert normalize_code(" 6205 20 ") == "620520"


def test_leading_zero_preserved():
    assert normalize_code("09103010") == "09103010"
    assert normalize_strict("091030") == "091030"
    assert len(normalize_code("09")) == 2


def test_invalid_code_handling():
    with pytest.raises(InvalidHsnCodeError):
        normalize_strict("abc")
    with pytest.raises(InvalidHsnCodeError):
        normalize_strict("123")  # 3 digits is not a valid level


@pytest.mark.parametrize(
    "code,level,chapter,heading,sub,parent",
    [
        ("09", 2, "09", None, None, None),
        ("0910", 4, "09", "0910", None, "09"),
        ("091030", 6, "09", "0910", "091030", "0910"),
        ("09103010", 8, "09", "0910", "091030", "091030"),
    ],
)
def test_hierarchy_levels(code, level, chapter, heading, sub, parent):
    assert digit_level(code) == level
    h = hierarchy(code)
    assert h["chapter_code"] == chapter
    assert h["heading_code"] == heading
    assert h["subheading_code"] == sub
    assert h["parent_code"] == parent


# ── import ─────────────────────────────────────────────────────────────────────


def test_import_creates_rows_and_hierarchy(session):
    result = _seed(session)
    assert result.job.status == "completed"
    assert result.job.records_created > 0
    turmeric = session.scalars(
        select(HsnCode).where(HsnCode.normalized_code == "09103010")
    ).first()
    assert turmeric is not None
    assert turmeric.digit_level == 8
    assert turmeric.chapter_code == "09"
    assert turmeric.parent_code == "091030"
    assert turmeric.code == "09103010"  # leading zero preserved


def test_import_idempotent_no_duplicates(session):
    first = _seed(session)
    total_after_first = session.scalar(select(func.count()).select_from(HsnCode))
    second = _seed(session)
    total_after_second = session.scalar(select(func.count()).select_from(HsnCode))
    assert total_after_first == total_after_second
    assert second.job.records_created == 0
    assert second.job.records_updated == first.job.records_created


def test_inactive_handling(session):
    _seed(session)
    code = session.scalars(select(HsnCode).where(HsnCode.normalized_code == "62052000")).first()
    code.is_active = False
    session.commit()
    active = search_hsn(session=session, query="62052000")
    assert active == [] or all(m.code.normalized_code != "62052000" for m in active)
    with_inactive = search_hsn(session=session, query="62052000", include_inactive=True)
    assert any(m.code.normalized_code == "62052000" for m in with_inactive)


def test_source_evidence_returned(session):
    _seed(session)
    code = session.scalars(select(HsnCode).where(HsnCode.normalized_code == "09103010")).first()
    from app.models import HsnSourceEvidence

    evidence = session.scalars(
        select(HsnSourceEvidence).where(HsnSourceEvidence.hsn_code_id == code.id)
    ).all()
    assert evidence
    assert evidence[0].evidence_type == "master_description"
    assert evidence[0].source_name == "DGFT ITC(HS) sample"


# ── search ─────────────────────────────────────────────────────────────────────


def test_exact_code_search(session):
    _seed(session)
    matches = search_hsn(session=session, query="09103010")
    assert matches
    assert matches[0].code.normalized_code == "09103010"
    assert matches[0].match_reason == "Exact HSN code match"
    assert matches[0].confidence_label == "High"


def test_prefix_search(session):
    _seed(session)
    matches = search_hsn(session=session, query="0910")
    codes = {m.code.normalized_code for m in matches}
    assert "0910" in codes
    assert "091030" in codes
    assert "09103010" in codes


def test_text_search_returns_ranked(session):
    _seed(session)
    matches = search_hsn(session=session, query="turmeric powder")
    assert matches
    assert any("turmeric" in m.code.description.lower() for m in matches)


@pytest.mark.parametrize(
    "product,expected_substr",
    [
        ("turmeric powder", "turmeric"),
        ("cotton shirt", "shirt"),
        ("aluminium beverage can", "aluminium"),
        ("carbonated soft drink", "carbonated"),
        ("basmati rice", "basmati"),
        ("plastic bottle", "plastic"),
        ("electric motor part", "motor"),
    ],
)
def test_sample_products_find_a_match(session, product, expected_substr):
    _seed(session)
    matches = search_hsn(session=session, query=product)
    assert matches, f"no match for {product}"
    assert any(expected_substr in m.code.description.lower() for m in matches)


def test_confidence_scoring(session):
    _seed(session)
    exact = search_hsn(session=session, query="09103010")[0]
    assert exact.confidence_label == "High"
    broad = search_hsn(session=session, query="rice")
    # broad single-word product → not High
    assert broad
    assert broad[0].confidence_label in {"Low", "Medium"}


def test_warning_flags_present_for_vague_query(session):
    _seed(session)
    matches = search_hsn(session=session, query="shirt")
    assert matches
    assert "textile composition ambiguity" in matches[0].warning_flags


def test_search_does_not_depend_on_rate_table(session):
    # RateTable is empty in a fresh DB; search must still return HSN results.
    _seed(session)
    from app.models import RateTable

    assert session.scalar(select(func.count()).select_from(RateTable)) == 0
    matches = search_hsn(session=session, query="cotton shirt")
    assert matches


# ── endpoint / auth tests ──────────────────────────────────────────────────────


def _admin_client() -> tuple[TestClient, dict[str, str], str]:
    client = TestClient(app)
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "hsnadmin@example.com",
            "password": "StrongPassword123!",
            "organization_name": "HSN Admin Org",
            "full_name": "HSN Admin",
        },
    )
    assert response.status_code == 201
    token = response.json()["access_token"]
    return client, {"Authorization": f"Bearer {token}"}, token


def test_admin_only_import_endpoint(session):
    client, headers, _ = _admin_client()
    files = {"file": ("hsn_sample.csv", SAMPLE_CSV.read_bytes(), "text/csv")}
    data = {"source_name": "DGFT ITC(HS) sample", "source_version": "itchs-2022", "import_type": "csv"}

    # Owner (admin) can import.
    ok = client.post("/api/v1/hsn/import", headers=headers, files=files, data=data)
    assert ok.status_code == 201, ok.text
    assert ok.json()["records_created"] > 0

    # Downgrade the membership to read_only; same token should now be rejected.
    membership = session.scalars(select(Membership)).first()
    membership.role = MembershipRole.READ_ONLY
    session.commit()
    forbidden = client.post(
        "/api/v1/hsn/import",
        headers=headers,
        files={"file": ("hsn_sample.csv", SAMPLE_CSV.read_bytes(), "text/csv")},
        data=data,
    )
    assert forbidden.status_code == 403


def test_search_endpoint_and_query_logged(session):
    client, headers, _ = _admin_client()
    files = {"file": ("hsn_sample.csv", SAMPLE_CSV.read_bytes(), "text/csv")}
    data = {"source_name": "DGFT ITC(HS) sample", "source_version": "itchs-2022", "import_type": "csv"}
    client.post("/api/v1/hsn/import", headers=headers, files=files, data=data)

    response = client.get("/api/v1/hsn/search", headers=headers, params={"q": "basmati rice"})
    assert response.status_code == 200
    body = response.json()
    assert body["count"] >= 1
    assert body["disclaimer"]
    assert session.scalar(select(func.count()).select_from(HsnClassificationQuery)) >= 1


def test_detail_endpoint_incentive_decoupled(session):
    client, headers, _ = _admin_client()
    files = {"file": ("hsn_sample.csv", SAMPLE_CSV.read_bytes(), "text/csv")}
    data = {"source_name": "DGFT ITC(HS) sample", "source_version": "itchs-2022", "import_type": "csv"}
    client.post("/api/v1/hsn/import", headers=headers, files=files, data=data)

    response = client.get("/api/v1/hsn/09103010", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["normalized_code"] == "09103010"
    assert body["incentive_rate_available"] is False  # HSN exists even with no rate
    assert body["source_evidence"]

    missing = client.get("/api/v1/hsn/99999999", headers=headers)
    assert missing.status_code == 404
    assert "does not mean the HSN does not exist" in missing.json()["detail"]


def test_verification_request_creation():
    client, headers, _ = _admin_client()
    response = client.post(
        "/api/v1/hsn/verify",
        headers=headers,
        json={
            "product_description": "Hand-knotted woollen carpet",
            "selected_hsn_code": "5701",
            "alternative_hsn_codes": ["570110"],
            "user_notes": "Unsure on knot count classification.",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "requested"
    assert body["selected_hsn_code"] == "5701"
    assert body["disclaimer"]
