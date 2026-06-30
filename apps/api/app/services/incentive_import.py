# ruff: noqa: E501
"""Idempotent import of official incentive/rate snapshot files.

Keyed on (tenant, scheme, normalized HSN, effective_from) so re-importing the same
snapshot upserts in place. Approved records are not blindly downgraded on re-import.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import IncentiveImportJob, IncentiveRate, IncentiveSourceEvidence
from app.services.hsn_import import compute_checksum, parse_rows
from app.services.hsn_normalization import InvalidHsnCodeError, digit_level, normalize_code

_REQUIRED = ("scheme", "hsn_code", "rate_value", "effective_from", "source_name")
_EVIDENCE_TYPE = {
    "rodtep": "rodtep_schedule",
    "drawback": "drawback_schedule",
    "rosctl": "rosctl_schedule",
}


@dataclass
class IncentiveImportResult:
    job: IncentiveImportJob
    errors: list[dict[str, Any]] = field(default_factory=list)


def _pick(row: dict[str, Any], *names: str) -> str | None:
    lowered = {str(k).strip().lower(): v for k, v in row.items()}
    for name in names:
        if name in lowered and lowered[name] not in (None, ""):
            return str(lowered[name]).strip()
    return None


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def _to_float(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return None


def import_incentive_snapshot(
    *,
    session: Session,
    tenant_id: UUID | None,
    raw_bytes: bytes,
    import_type: str,
    source_name: str,
    scheme: str | None = None,
    source_url: str | None = None,
    source_document_title: str | None = None,
    source_document_date: str | None = None,
    source_version: str | None = None,
    created_by: str | None = None,
    commit: bool = True,
) -> IncentiveImportResult:
    checksum = compute_checksum(raw_bytes)
    doc_date = _parse_date(source_document_date)
    job = IncentiveImportJob(
        scheme=scheme,
        source_name=source_name,
        source_url=source_url,
        import_type=import_type.lower(),
        status="running",
        checksum=checksum,
        started_at=datetime.now(UTC),
        created_by=created_by,
    )
    session.add(job)
    session.flush()

    errors: list[dict[str, Any]] = []
    try:
        rows = parse_rows(raw_bytes, import_type)
    except Exception as error:  # noqa: BLE001
        job.status = "failed"
        job.error_message = str(error)
        job.completed_at = datetime.now(UTC)
        if commit:
            session.commit()
        return IncentiveImportResult(job=job, errors=[{"row": 0, "message": str(error)}])

    created = updated = seen = 0
    for index, row in enumerate(rows, start=2):
        seen += 1
        try:
            row_scheme = (_pick(row, "scheme") or scheme or "").strip().lower()
            raw_code = _pick(row, "hsn_code", "hsn", "code")
            rate_value = _to_float(_pick(row, "rate_value", "rate"))
            effective_from = _parse_date(_pick(row, "effective_from", "effective_date"))
            row_source = _pick(row, "source_name", "source") or source_name
            if not row_scheme:
                raise ValueError("Missing scheme.")
            if not raw_code:
                raise ValueError("Missing hsn_code.")
            if rate_value is None:
                raise ValueError("Missing or invalid rate_value.")
            if effective_from is None:
                raise ValueError("Missing or invalid effective_from (use YYYY-MM-DD).")
            normalized = normalize_code(raw_code)
            level = digit_level(normalized)
        except (InvalidHsnCodeError, ValueError) as error:
            errors.append({"row": index, "message": str(error)})
            continue

        incoming_status = (_pick(row, "approval_status", "review_status") or "").strip().lower() or "pending"
        values = {
            "hsn_code": raw_code,
            "normalized_hsn_code": normalized,
            "digit_level": level,
            "product_description": _pick(row, "product_description", "description"),
            "rate_type": (_pick(row, "rate_type") or "percentage").lower(),
            "rate_value": rate_value,
            "cap_value": _to_float(_pick(row, "cap_value", "cap")),
            "cap_unit": _pick(row, "cap_unit"),
            "unit_of_quantity": _pick(row, "unit_of_quantity", "uqc", "unit"),
            "condition_text": _pick(row, "condition_text", "conditions", "condition"),
            "effective_to": _parse_date(_pick(row, "effective_to")),
            "source_name": row_source,
            "source_url": _pick(row, "source_url") or source_url,
            "source_document_title": _pick(row, "source_document_title") or source_document_title,
            "source_document_date": _parse_date(_pick(row, "source_document_date")) or doc_date,
            "source_version": _pick(row, "source_version") or source_version,
        }

        existing = session.scalars(
            select(IncentiveRate).where(
                IncentiveRate.tenant_id == tenant_id,
                IncentiveRate.scheme == row_scheme,
                IncentiveRate.normalized_hsn_code == normalized,
                IncentiveRate.effective_from == effective_from,
            )
        ).first()

        if existing is None:
            rate = IncentiveRate(
                tenant_id=tenant_id,
                scheme=row_scheme,
                effective_from=effective_from,
                approval_status=incoming_status,
                is_active=True,
                **values,
            )
            session.add(rate)
            session.flush()
            created += 1
        else:
            for key, value in values.items():
                setattr(existing, key, value)
            # Never blindly downgrade an approved record on re-import.
            if not (existing.approval_status == "approved" and incoming_status in ("", "pending")):
                existing.approval_status = incoming_status
                if incoming_status != "approved":
                    existing.verified_by = None
                    existing.verified_at = None
            existing.is_active = True
            rate = existing
            updated += 1
            session.query(IncentiveSourceEvidence).filter(
                IncentiveSourceEvidence.incentive_rate_id == rate.id,
                IncentiveSourceEvidence.evidence_type != "manual_admin",
            ).delete(synchronize_session=False)

        session.add(
            IncentiveSourceEvidence(
                incentive_rate_id=rate.id,
                source_name=row_source,
                source_url=values["source_url"],
                document_title=values["source_document_title"],
                document_date=values["source_document_date"],
                raw_text_excerpt=(values["condition_text"] or values["product_description"] or "")[:2000] or None,
                checksum=checksum,
                evidence_type=_EVIDENCE_TYPE.get(row_scheme, "notification"),
                confidence_weight=80,
            )
        )

    job.records_seen = seen
    job.records_created = created
    job.records_updated = updated
    job.status = "completed"
    job.error_message = json.dumps(errors)[:4000] if errors else None
    job.completed_at = datetime.now(UTC)

    if commit:
        session.commit()
    else:
        session.flush()
    return IncentiveImportResult(job=job, errors=errors)
