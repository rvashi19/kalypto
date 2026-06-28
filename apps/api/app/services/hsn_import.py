# ruff: noqa: E501
"""Idempotent import of official HSN/ITC(HS) snapshot files into the HSN master.

Supported inputs: CSV, JSON, XLSX (openpyxl). Re-importing the same snapshot
upserts in place (keyed by normalized_code + source_version) so repeated imports
never create duplicate rows. Leading zeros are preserved.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import HsnCode, HsnImportJob, HsnSourceEvidence
from app.services.hsn_normalization import (
    InvalidHsnCodeError,
    chapter_code,
    digit_level,
    heading_code,
    normalize_code,
    parent_code,
    subheading_code,
)

# Column aliases tolerated in official snapshot exports.
_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "code": ("code", "hsn_code", "hs_code", "hscode", "itc_hs", "itchs", "tariff_item"),
    "description": ("description", "desc", "product_description", "commodity", "goods_description"),
    "unit_of_quantity": ("unit_of_quantity", "uqc", "unit", "uom"),
    "section_name": ("section_name", "section"),
    "chapter_name": ("chapter_name", "chapter_description"),
    "import_policy": ("import_policy", "policy", "import_status"),
    "export_policy": ("export_policy", "export_status"),
    "policy_condition": ("policy_condition", "policy_conditions", "conditions", "nature_of_restriction"),
}

_PARSE_ERROR = "Could not parse row"


@dataclass
class ImportResult:
    job: HsnImportJob
    errors: list[dict[str, Any]] = field(default_factory=list)


def compute_checksum(raw_bytes: bytes) -> str:
    return hashlib.sha256(raw_bytes).hexdigest()


def _pick(row: dict[str, Any], field_name: str) -> str | None:
    lowered = {str(k).strip().lower(): v for k, v in row.items()}
    for alias in _FIELD_ALIASES[field_name]:
        if alias in lowered and lowered[alias] not in (None, ""):
            return str(lowered[alias]).strip()
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


def parse_rows(raw_bytes: bytes, import_type: str) -> list[dict[str, Any]]:
    """Return a list of raw dict rows from the uploaded file."""
    import_type = import_type.lower()
    if import_type == "csv":
        text = raw_bytes.decode("utf-8-sig")
        return list(csv.DictReader(io.StringIO(text)))
    if import_type == "json":
        data = json.loads(raw_bytes.decode("utf-8"))
        if isinstance(data, dict) and "records" in data:
            data = data["records"]
        if not isinstance(data, list):
            raise ValueError("JSON import must be a list of records or {records: [...]}.")
        return data
    if import_type == "xlsx":
        from openpyxl import load_workbook

        workbook = load_workbook(io.BytesIO(raw_bytes), read_only=True, data_only=True)
        sheet = workbook.active
        rows_iter = sheet.iter_rows(values_only=True)
        header = [str(cell).strip() if cell is not None else "" for cell in next(rows_iter)]
        records: list[dict[str, Any]] = []
        for row in rows_iter:
            if all(cell is None for cell in row):
                continue
            # Keep leading zeros: format numeric codes as plain strings.
            cells = ["" if cell is None else (str(int(cell)) if isinstance(cell, float) and cell.is_integer() else str(cell)) for cell in row]
            records.append(dict(zip(header, cells, strict=False)))
        return records
    raise ValueError(f"Unsupported import_type for parsing: {import_type}")


def import_hsn_snapshot(
    *,
    session: Session,
    raw_bytes: bytes,
    import_type: str,
    source_name: str,
    source_url: str | None,
    source_document_title: str | None,
    source_document_date: str | None,
    source_version: str | None,
    created_by: str | None = None,
    commit: bool = True,
) -> ImportResult:
    """Idempotent upsert of an HSN snapshot. Tracks an HsnImportJob."""
    checksum = compute_checksum(raw_bytes)
    doc_date = _parse_date(source_document_date)
    job = HsnImportJob(
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
        return ImportResult(job=job, errors=[{"row": 0, "message": str(error)}])

    created = updated = seen = 0
    for index, row in enumerate(rows, start=2):
        seen += 1
        try:
            raw_code = _pick(row, "code")
            description = _pick(row, "description")
            if not raw_code:
                raise ValueError("Missing HSN code value.")
            if not description:
                raise ValueError("Missing description value.")
            normalized = normalize_code(raw_code)
            level = digit_level(normalized)  # validates 2/4/6/8
        except (InvalidHsnCodeError, ValueError) as error:
            errors.append({"row": index, "message": str(error)})
            continue

        existing = session.scalars(
            select(HsnCode).where(HsnCode.normalized_code == normalized)
        ).first()

        values = {
            "code": raw_code,
            "normalized_code": normalized,
            "digit_level": level,
            "description": description,
            "chapter_code": chapter_code(normalized),
            "heading_code": heading_code(normalized),
            "subheading_code": subheading_code(normalized),
            "parent_code": parent_code(normalized),
            "unit_of_quantity": _pick(row, "unit_of_quantity"),
            "section_name": _pick(row, "section_name"),
            "chapter_name": _pick(row, "chapter_name"),
            "import_policy": _pick(row, "import_policy"),
            "export_policy": _pick(row, "export_policy"),
            "policy_condition": _pick(row, "policy_condition"),
            "source_name": source_name,
            "source_url": source_url,
            "source_document_title": source_document_title,
            "source_document_date": doc_date,
            "source_version": source_version,
            "is_active": True,
        }

        if existing is None:
            code = HsnCode(**values)
            session.add(code)
            session.flush()
            created += 1
        else:
            for key, value in values.items():
                setattr(existing, key, value)
            code = existing
            updated += 1
            # Avoid duplicate evidence rows on re-import.
            session.query(HsnSourceEvidence).filter(
                HsnSourceEvidence.hsn_code_id == code.id,
                HsnSourceEvidence.evidence_type == "master_description",
            ).delete(synchronize_session=False)

        session.add(
            HsnSourceEvidence(
                hsn_code_id=code.id,
                source_name=source_name,
                source_url=source_url,
                evidence_type="master_description",
                raw_text_excerpt=description[:2000],
                document_title=source_document_title,
                document_date=doc_date,
                checksum=checksum,
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
    return ImportResult(job=job, errors=errors)
