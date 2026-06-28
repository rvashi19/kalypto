# ruff: noqa: E501
"""Verified product -> HSN mapping layer.

These are curated, cross-checked answers (agent/LLM/admin verified) that search
consults FIRST. They fix the common case where a scraped source's description is
wrong or garbled: for a verified term we return the correct code with a clean
description and High confidence, and we also overwrite the master row's
description so detail views read correctly.
"""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import HsnCode, HsnProductAlias, HsnSourceEvidence
from app.services.hsn_normalization import (
    chapter_code,
    digit_level,
    heading_code,
    normalize_code,
    parent_code,
    subheading_code,
)

VERIFIED_SOURCE = "KALYPTO verified mapping (cross-checked)"


def _normalize_term(term: str) -> str:
    return " ".join((term or "").lower().split())


def load_verified_aliases(*, session: Session, raw_bytes: bytes, source: str = "agent_verified") -> dict[str, int]:
    """Idempotently load verified term->code rows, cleaning the master description."""
    rows = list(csv.DictReader(io.StringIO(raw_bytes.decode("utf-8-sig"))))
    aliases = created = updated = 0
    for row in rows:
        term = _normalize_term(row.get("term", ""))
        code_raw = (row.get("code") or "").strip()
        description = (row.get("description") or "").strip()
        if not term or not code_raw or not description:
            continue
        normalized = normalize_code(code_raw)
        try:
            level = digit_level(normalized)
        except Exception:  # noqa: BLE001
            continue

        existing = session.scalars(
            select(HsnCode).where(HsnCode.normalized_code == normalized)
        ).first()
        if existing is None:
            existing = HsnCode(
                code=code_raw,
                normalized_code=normalized,
                digit_level=level,
                description=description,
                chapter_code=chapter_code(normalized),
                heading_code=heading_code(normalized),
                subheading_code=subheading_code(normalized),
                parent_code=parent_code(normalized),
                source_name=VERIFIED_SOURCE,
                source_version="verified",
                is_active=True,
            )
            session.add(existing)
            session.flush()
            created += 1
        else:
            # Overwrite the scraped/garbled description with the verified clean one.
            existing.description = description
            existing.source_name = VERIFIED_SOURCE
            updated += 1
            session.query(HsnSourceEvidence).filter(
                HsnSourceEvidence.hsn_code_id == existing.id,
                HsnSourceEvidence.evidence_type == "manual_admin",
            ).delete(synchronize_session=False)

        session.add(
            HsnSourceEvidence(
                hsn_code_id=existing.id,
                source_name=VERIFIED_SOURCE,
                evidence_type="manual_admin",
                raw_text_excerpt=f"Verified mapping for '{term}': {description}",
                document_title="Verified product mapping",
                document_date=datetime.now(UTC),
                confidence_weight=95,
            )
        )

        alias = session.scalars(
            select(HsnProductAlias).where(HsnProductAlias.term == term)
        ).first()
        if alias is None:
            session.add(
                HsnProductAlias(term=term, normalized_code=normalized, source=source, confidence=96)
            )
            aliases += 1
        else:
            alias.normalized_code = normalized
            alias.source = source

    session.commit()
    return {"aliases": aliases, "codes_created": created, "codes_updated": updated}


def verified_matches(*, session: Session, query: str, include_inactive: bool = False) -> list[tuple[HsnCode, int]]:
    """Return (code, confidence) for verified aliases matching the query.

    Matches on exact term, then on the query containing a term or a term
    containing the query (longer terms win).
    """
    normalized_query = _normalize_term(query)
    if not normalized_query or normalized_query.isdigit():
        return []

    aliases = session.scalars(select(HsnProductAlias)).all()
    hits: list[tuple[str, str, int]] = []  # (term, code, confidence)
    for alias in aliases:
        term = alias.term
        if term == normalized_query:
            hits.append((term, alias.normalized_code, 99))
        elif term in normalized_query or normalized_query in term:
            hits.append((term, alias.normalized_code, alias.confidence))

    if not hits:
        return []
    # Exact-term (highest confidence) wins, then the most specific (longest) term.
    hits.sort(key=lambda h: (-h[2], -len(h[0])))
    seen: set[str] = set()
    out: list[tuple[HsnCode, int]] = []
    for _term, code, confidence in hits:
        if code in seen:
            continue
        seen.add(code)
        row = session.scalars(select(HsnCode).where(HsnCode.normalized_code == code)).first()
        if row is None or (not include_inactive and not row.is_active):
            continue
        out.append((row, confidence))
    return out
