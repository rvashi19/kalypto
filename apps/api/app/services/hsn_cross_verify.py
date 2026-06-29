# ruff: noqa: E501
"""Cross-verify an HSN code against authentic ITC-HS website data.

An LLM suggestion is only trusted when an independent authentic source agrees:
we confirm the code is a real published ITC-HS code and that its official
description plausibly matches the product. Sources used:

  1. Local master  - our reviewed/scraped ITC-HS rows (EximGuru-derived).
  2. EximGuru live - a fresh lookup of that exact code on the website.

The result is a status (cross_verified / exists_weak_match / unverified) plus the
per-source descriptions and agreement scores, so the answer is never LLM-only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import HsnCode
from app.services.hsn_normalization import normalize_code
from app.services.hsn_scraper import HsnScrapeError, fetch_code_description

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOP = {"of", "the", "and", "or", "for", "with", "other", "a", "an", "in", "to", "not"}
_MATCH_THRESHOLD = 0.34


@dataclass
class SourceCheck:
    source: str
    description: str
    match: float


@dataclass
class CrossVerifyResult:
    code: str
    status: str  # cross_verified / exists_weak_match / unverified
    sources: list[SourceCheck] = field(default_factory=list)
    best_match: float = 0.0

    @property
    def authentic_count(self) -> int:
        return len(self.sources)


def _tokens(text: str) -> set[str]:
    return {t for t in _TOKEN_RE.findall((text or "").lower()) if t not in _STOP and len(t) > 1}


def _overlap(product_terms: set[str], description: str) -> float:
    desc = _tokens(description)
    if not product_terms or not desc:
        return 0.0
    hit = sum(1 for t in product_terms if t in desc or any(w.startswith(t) or t.startswith(w) for w in desc))
    return round(hit / len(product_terms), 3)


def cross_verify_code(
    *, session: Session, code: str, product: str, llm_description: str | None = None
) -> CrossVerifyResult:
    normalized = normalize_code(code)
    product_terms = _tokens(product) | _tokens(llm_description or "")
    sources: list[SourceCheck] = []

    row = (
        session.scalars(select(HsnCode).where(HsnCode.normalized_code == normalized)).first()
        if normalized
        else None
    )
    if row is not None:
        sources.append(SourceCheck("local_master", row.description, _overlap(product_terms, row.description)))

    try:
        live_desc, exact = fetch_code_description(normalized)
    except HsnScrapeError:
        live_desc, exact = None, False
    if live_desc:
        label = "eximguru_live" if exact else "eximguru_live_heading"
        sources.append(SourceCheck(label, live_desc, _overlap(product_terms, live_desc)))

    best = max((s.match for s in sources), default=0.0)
    if not sources:
        status = "unverified"
    elif best >= _MATCH_THRESHOLD:
        status = "cross_verified"
    else:
        status = "exists_weak_match"

    return CrossVerifyResult(code=normalized or code, status=status, sources=sources, best_match=best)
