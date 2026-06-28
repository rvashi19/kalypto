# ruff: noqa: E501
"""Deterministic HSN classification search.

Ranking priority (no LLM):
  1. exact HSN code match
  2. prefix HSN code match
  3. full-text description match (all query tokens present)
  4. token overlap
Confidence is derived from match strength, code level, and presence of source
evidence. This search depends only on the HSN master and never on RateTable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import HsnClassificationQuery, HsnCode, HsnSourceEvidence
from app.services.hsn_normalization import digit_level, hierarchy, normalize_code

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "and", "or", "the", "of", "for", "with", "a", "an", "in", "to", "from",
    "made", "type", "kind", "other", "item", "product", "products", "goods",
}

# Keyword cues used only to raise deterministic warning flags — not to classify.
_MATERIAL_CUES = {
    "cotton", "wool", "silk", "polyester", "nylon", "aluminium", "aluminum", "steel",
    "iron", "plastic", "pvc", "glass", "wood", "wooden", "rubber", "leather", "brass",
    "copper", "ceramic", "paper", "bamboo", "jute", "cement", "stone",
}
_FORM_CUES = {
    "powder", "powdered", "ground", "whole", "liquid", "paste", "granule", "granules",
    "sheet", "sheets", "roll", "block", "bar", "pellet", "flake", "flakes", "solid",
    "frozen", "dried", "fresh", "raw", "refined", "woven", "knitted",
}
_USE_CUES = {
    "industrial", "household", "medical", "surgical", "automotive", "kitchen",
    "packaging", "decorative", "agricultural", "edible", "beverage", "food", "machine",
    "electrical", "construction",
}
_FOOD_AGRI_CUES = {
    "rice", "wheat", "spice", "spices", "turmeric", "chilli", "chili", "tea", "coffee",
    "fruit", "vegetable", "grain", "pulses", "juice", "drink", "beverage", "milk", "sugar",
}
_TEXTILE_CUES = {"shirt", "fabric", "cloth", "garment", "textile", "yarn", "apparel", "trouser", "saree"}
_MACHINERY_CUES = {"motor", "pump", "machine", "engine", "part", "parts", "component", "gear", "bearing"}
_CHEMICAL_CUES = {"acid", "oxide", "chemical", "compound", "solvent", "polymer", "resin", "reagent"}

# Colloquial / brand terms → official tariff description words, so everyday searches
# match ITC-HS wording (e.g. "iphone" → "telephone smartphones"). Whole-word only.
_SYNONYMS: dict[str, str] = {
    "iphone": "telephones cellular networks",
    "smartphone": "telephones cellular networks",
    "android": "telephones cellular networks",
    "cellphone": "telephones cellular networks",
    "mobile": "telephones cellular networks",
    "phone": "telephone",
    "laptop": "portable automatic data processing computers",
    "notebook": "portable automatic data processing computers",
    "macbook": "portable automatic data processing computers",
    "computer": "automatic data processing",
    "pc": "automatic data processing",
    "desktop": "automatic data processing",
    "tv": "television",
    "car": "motor vehicle",
    "motorbike": "motorcycle",
    "scooter": "motorcycle",
    "shoe": "footwear",
    "shoes": "footwear",
    "sandal": "footwear",
    "bag": "handbag",
    "purse": "handbag",
    "medicine": "medicament",
    "drug": "medicament",
    "tablet": "medicament",
    "capsule": "medicament",
    "biscuit": "biscuits",
    "cookie": "biscuits",
    "soda": "aerated waters beverage",
    "cola": "aerated waters beverage",
    "softdrink": "aerated waters beverage",
}


def _expand_synonyms(text: str) -> str:
    expanded: list[str] = []
    for word in _TOKEN_RE.findall((text or "").lower()):
        expanded.append(word)
        if word in _SYNONYMS:
            expanded.append(_SYNONYMS[word])
    return " ".join(expanded) if expanded else (text or "")


@dataclass
class HsnMatch:
    code: HsnCode
    score: float
    match_reason: str
    evidence_count: int = 0
    warning_flags: list[str] = field(default_factory=list)
    confidence_label: str = "Low"
    verification_recommended: bool = True


def _tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN_RE.findall((text or "").lower()) if t not in _STOPWORDS and len(t) > 1]


def _looks_like_code(raw: str) -> bool:
    cleaned = (raw or "").strip()
    if not cleaned:
        return False
    digits = normalize_code(cleaned)
    non_digit = sum(1 for c in cleaned if not c.isdigit() and not c.isspace())
    return len(digits) >= 2 and non_digit == 0


def _label_for(score: float) -> str:
    if score >= 85:
        return "High"
    if score >= 55:
        return "Medium"
    return "Low"


def _query_warnings(query: str) -> list[str]:
    tokens = set(_tokenize(query))
    flags: list[str] = []
    if not (tokens & _MATERIAL_CUES):
        flags.append("material missing")
    if not (tokens & _FORM_CUES):
        flags.append("form missing")
    if not (tokens & _USE_CUES):
        flags.append("use-case missing")
    if tokens & _FOOD_AGRI_CUES:
        flags.append("food/agri ambiguity")
    if tokens & _TEXTILE_CUES:
        flags.append("textile composition ambiguity")
    if tokens & _MACHINERY_CUES:
        flags.append("machinery part ambiguity")
    if tokens & _CHEMICAL_CUES:
        flags.append("chemical composition ambiguity")
    # Brand-name heuristic: a capitalized non-dictionary token with no generic material/form cue.
    has_generic = bool(tokens & (_MATERIAL_CUES | _FORM_CUES | _FOOD_AGRI_CUES | _TEXTILE_CUES | _MACHINERY_CUES | _CHEMICAL_CUES))
    if any(word[:1].isupper() for word in (query or "").split()) and not has_generic and len(tokens) <= 2:
        flags.append("brand name without generic product description")
    return flags


def _evidence_counts(session: Session, code_ids: list[UUID]) -> dict[UUID, int]:
    if not code_ids:
        return {}
    rows = session.execute(
        select(HsnSourceEvidence.hsn_code_id, func.count())
        .where(HsnSourceEvidence.hsn_code_id.in_(code_ids))
        .group_by(HsnSourceEvidence.hsn_code_id)
    ).all()
    return {row[0]: row[1] for row in rows}


def search_hsn(
    *,
    session: Session,
    query: str,
    limit: int = 20,
    digit_level_filter: int | None = None,
    include_inactive: bool = False,
) -> list[HsnMatch]:
    """Return ranked HSN matches. Pure master lookup — no RateTable involved."""
    raw = (query or "").strip()
    if not raw:
        return []

    base = select(HsnCode)
    if not include_inactive:
        base = base.where(HsnCode.is_active.is_(True))
    if digit_level_filter is not None:
        base = base.where(HsnCode.digit_level == digit_level_filter)

    results: dict[UUID, HsnMatch] = {}

    if _looks_like_code(raw):
        normalized = normalize_code(raw)
        exact = session.scalars(base.where(HsnCode.normalized_code == normalized)).all()
        for code in exact:
            results[code.id] = HsnMatch(code=code, score=98.0, match_reason="Exact HSN code match")
        prefix_rows = session.scalars(
            base.where(HsnCode.normalized_code.like(f"{normalized}%")).limit(limit * 3)
        ).all()
        for code in prefix_rows:
            if code.id in results:
                continue
            # Deeper codes under the prefix rank slightly lower than the prefix node itself.
            score = 82.0 - min(len(code.normalized_code) - len(normalized), 6)
            results[code.id] = HsnMatch(code=code, score=score, match_reason="HSN code prefix match")
    else:
        tokens = _tokenize(_expand_synonyms(raw))
        if tokens:
            # Candidate set: every row whose description contains any query token
            # (plus a singular/plural stem so "shirts" matches "shirt", etc.).
            # Score them all (capped for safety) so the best matches are never dropped.
            from sqlalchemy import or_

            like_terms: set[str] = set()
            for token in tokens:
                like_terms.add(token)
                if len(token) > 3 and token.endswith("s"):
                    like_terms.add(token[:-1])
            candidate_query = base.where(
                or_(*[func.lower(HsnCode.description).like(f"%{term}%") for term in like_terms])
            ).limit(3000)
            candidates = session.scalars(candidate_query).all()
            token_count = len(tokens)

            for code in candidates:
                desc = (code.description or "").lower()
                desc_words = set(_tokenize(desc))
                word_hits = sub_hits = 0
                for token in tokens:
                    if any(w == token or w.startswith(token) or token.startswith(w) for w in desc_words):
                        word_hits += 1
                        sub_hits += 1
                    elif token in desc:
                        sub_hits += 1
                if sub_hits == 0:
                    continue
                word_cov = word_hits / token_count
                sub_cov = sub_hits / token_count
                level_bonus = {8: 8, 6: 5, 4: 2, 2: 0}.get(code.digit_level, 0)
                score = 30.0 + 52.0 * word_cov + 10.0 * sub_cov + level_bonus
                if word_hits == token_count:
                    score += 8.0  # every query word present as a whole word
                score = min(score, 96.0)
                reason = (
                    "Full description match" if word_hits == token_count else "Partial description match"
                )
                results[code.id] = HsnMatch(code=code, score=round(score, 2), match_reason=reason)

    matches = sorted(results.values(), key=lambda m: (-m.score, m.code.digit_level, m.code.normalized_code))
    # Collapse to one row per HSN code (defensive against legacy duplicate versions).
    seen_codes: set[str] = set()
    deduped: list[HsnMatch] = []
    for match in matches:
        if match.code.normalized_code in seen_codes:
            continue
        seen_codes.add(match.code.normalized_code)
        deduped.append(match)
    matches = deduped[:limit]

    evidence = _evidence_counts(session, [m.code.id for m in matches])
    query_flags = _query_warnings(raw)
    is_text_query = not _looks_like_code(raw)

    # "multiple plausible" when several top results are close in score.
    close_top = sum(1 for m in matches if matches and m.score >= matches[0].score - 8)
    multiple_plausible = is_text_query and close_top >= 3

    for index, match in enumerate(matches):
        match.evidence_count = evidence.get(match.code.id, 0)
        flags = list(query_flags) if is_text_query else []
        if multiple_plausible and index < close_top:
            flags.append("multiple plausible HSN codes")
        match.warning_flags = flags

        score = match.score
        # Strong 8-digit description match needs evidence to reach High.
        if match.match_reason == "Full description match" and match.code.digit_level == 8 and match.evidence_count == 0:
            score = min(score, 78.0)
        if multiple_plausible and index < close_top and score >= 85:
            score = 80.0  # downgrade conflicting High matches to Medium
        match.score = round(score, 2)
        match.confidence_label = _label_for(match.score)
        match.verification_recommended = (
            match.confidence_label != "High" or bool(match.warning_flags)
        )

    return matches


def record_query(
    *,
    session: Session,
    query: str,
    tenant_id: UUID | None,
    user_id: UUID | None,
    top: HsnMatch | None,
) -> None:
    """Persist the search for audit/analytics. Best-effort, non-fatal."""
    normalized = normalize_code(query) if _looks_like_code(query) else (query or "").strip().lower()
    session.add(
        HsnClassificationQuery(
            tenant_id=tenant_id,
            user_id=user_id,
            query_text=(query or "")[:512],
            normalized_query=normalized[:512],
            selected_hsn_code=top.code.code if top else None,
            confidence=top.score if top else None,
            status="searched",
        )
    )


def derive_levels(normalized: str) -> dict[str, object]:
    """Convenience hierarchy + level dict for response building."""
    return {"digit_level": digit_level(normalized), **hierarchy(normalized)}
