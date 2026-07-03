# ruff: noqa: E501
"""AI extraction abstraction for the Country Compliance Checker.

Core product rule: official source evidence is the source of truth. The LLM is
ONLY an extraction/summarisation assistant. It must:
  * extract requirement cards strictly from the supplied official source text
  * summarise official evidence
  * generate missing-information / buyer / CHA questions
  * flag ambiguity or conflicts

It must NOT: invent requirements, cite sources not supplied, use model memory as
authority, or claim legal certainty. Everything it produces is stored as
`review_status="pending_review"` at Low/Medium confidence until a human approves it.

Provider is swappable via AI_PROVIDER (auto|groq|openai|xai). "auto" falls through
groq -> openai -> xai based on whichever key is configured. Future providers plug in
by extending `_resolve_provider`.
"""

from __future__ import annotations

import importlib
import json
import re
from dataclasses import dataclass, field
from typing import Any

from app.core.settings import get_settings


class ComplianceAIError(RuntimeError):
    """Raised when AI extraction is unavailable or fails."""


@dataclass(frozen=True, slots=True)
class ExtractedRequirement:
    requirement_type: str  # document/label/certificate/inspection/license/restriction/buyer_question/warning
    title: str
    summary: str
    detail: str
    mandatory_or_conditional: str  # mandatory | conditional
    trigger_conditions: list[str] = field(default_factory=list)
    evidence_excerpt: str = ""
    confidence_label: str = "Low"  # Low | Medium | High (High never auto-applied)


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    requirements: list[ExtractedRequirement]
    missing_questions: list[str]
    buyer_questions: list[str]
    cha_questions: list[str]
    ambiguities: list[str]
    evidence_summary: str


_SYSTEM = """You are a compliance evidence extraction assistant for export documentation.

You are given the TEXT of an OFFICIAL government/regulatory source. Extract only what is
explicitly supported by that text. You are an assistant, NOT an authority.

Return STRICT JSON only, matching:
{
  "requirements": [
    {
      "requirement_type": "document|label|certificate|inspection|license|restriction|buyer_question|warning",
      "title": "short title",
      "summary": "one-line plain-English summary for an exporter",
      "detail": "clear guidance derived ONLY from the source text",
      "mandatory_or_conditional": "mandatory|conditional",
      "trigger_conditions": ["condition that makes this apply, if conditional"],
      "evidence_excerpt": "verbatim excerpt from the source text supporting this",
      "confidence_label": "Low|Medium"
    }
  ],
  "missing_questions": ["information needed from the user that the source does not resolve"],
  "buyer_questions": ["questions the exporter should confirm with the importer/buyer"],
  "cha_questions": ["questions for the CHA/customs broker"],
  "ambiguities": ["conflicts, unclear scope, or version/date ambiguity found in the source"],
  "evidence_summary": "2-4 sentence neutral summary of what this source establishes"
}

Hard rules:
- Use ONLY the provided source text. Do NOT add requirements from prior knowledge.
- Every requirement MUST have an evidence_excerpt copied from the source text.
- Never output confidence_label "High" — human review assigns high confidence.
- Do NOT claim legal or customs certainty.
- If the text contains no concrete requirement, return an empty "requirements" list.
- Return JSON only, no markdown fences, no commentary.
"""


def _resolve_provider() -> tuple[str, str, str | None, str]:
    """Return (name, api_key, base_url, model). Honors AI_PROVIDER; 'auto' falls through."""
    s = get_settings()
    choice = (s.ai_provider or "auto").lower()

    def groq() -> tuple[str, str, str | None, str] | None:
        return ("groq", s.groq_api_key, None, s.groq_model) if s.groq_api_key else None

    def openai() -> tuple[str, str, str | None, str] | None:
        return ("openai", s.openai_api_key, None, s.openai_model) if s.openai_api_key else None

    def xai() -> tuple[str, str, str | None, str] | None:
        return ("xai", s.xai_api_key, s.xai_base_url, s.xai_model) if s.xai_api_key else None

    explicit = {"groq": groq, "openai": openai, "xai": xai}
    if choice in explicit:
        resolved = explicit[choice]()
        if resolved is None:
            raise ComplianceAIError(f"AI_PROVIDER={choice} but its API key is not configured.")
        return resolved

    for factory in (groq, openai, xai):  # auto fallback order
        resolved = factory()
        if resolved is not None:
            return resolved
    raise ComplianceAIError(
        "No LLM provider configured. Set GROQ_API_KEY, OPENAI_API_KEY, or XAI_API_KEY."
    )


def is_ai_configured() -> bool:
    try:
        _resolve_provider()
        return True
    except ComplianceAIError:
        return False


def _extract_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    cleaned = cleaned.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    match = re.search(r"\{[\s\S]*\}", cleaned)
    if not match:
        raise ComplianceAIError("AI did not return JSON.")
    try:
        data = json.loads(match.group())
    except json.JSONDecodeError as error:
        raise ComplianceAIError(f"AI returned malformed JSON: {error}") from error
    if not isinstance(data, dict):
        raise ComplianceAIError("AI returned JSON, but it was not an object.")
    return data


def _chat_text(system: str, user: str) -> str:
    name, api_key, base_url, model = _resolve_provider()

    if name == "groq":
        from groq import Groq  # noqa: PLC0415

        client = Groq(api_key=api_key)
        try:
            completion = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.1,
                response_format={"type": "json_object"},
            )
        except Exception as error:  # pragma: no cover - network
            raise ComplianceAIError(f"AI request failed: {error}") from error
        return (completion.choices[0].message.content or "").strip()

    openai_module: Any = importlib.import_module("openai")
    client = (
        openai_module.OpenAI(api_key=api_key, base_url=base_url)
        if base_url
        else openai_module.OpenAI(api_key=api_key)
    )
    try:
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
    except Exception as e:  # pragma: no cover - network
        raise ComplianceAIError(f"AI request failed: {e}") from e
    return (completion.choices[0].message.content or "").strip()


def _repair_json(*, system: str, invalid_response: str, parse_error: str) -> dict[str, Any]:
    repair_system = (
        "You repair malformed JSON for a compliance extraction pipeline. "
        "Return only valid JSON. Do not add new facts or requirements."
    )
    repair_user = (
        "The previous assistant response failed JSON parsing.\n"
        f"Parse error: {parse_error}\n\n"
        "Original system instruction/schema:\n"
        f"{system[:6000]}\n\n"
        "Invalid response to repair:\n"
        f"{invalid_response[:12000]}"
    )
    repaired = _chat_text(repair_system, repair_user)
    return _extract_json_object(repaired)


def _chat_json(system: str, user: str) -> dict[str, Any]:
    text = _chat_text(system, user)
    try:
        return _extract_json_object(text)
    except ComplianceAIError as error:
        try:
            return _repair_json(
                system=system,
                invalid_response=text,
                parse_error=str(error),
            )
        except ComplianceAIError as repair_error:
            raise ComplianceAIError(
                f"AI returned invalid JSON and repair failed: {repair_error}"
            ) from repair_error


class ComplianceAIExtractor:
    """Provider-swappable AI assistant. All output is advisory / pending_review."""

    def extract_requirements_from_source_text(
        self,
        *,
        source_text: str,
        country: str,
        product_category: str,
        hsn_code: str | None = None,
        product_description: str | None = None,
    ) -> ExtractionResult:
        context = (
            f"Destination country: {country}\n"
            f"Product category: {product_category}\n"
            f"HSN: {hsn_code or 'unknown'}\n"
            f"Product: {product_description or 'unspecified'}\n\n"
            f"OFFICIAL SOURCE TEXT (truncated):\n{source_text[:16000]}"
        )
        raw = _chat_json(_SYSTEM, context)
        requirements = [
            ExtractedRequirement(
                requirement_type=str(r.get("requirement_type") or "document"),
                title=str(r.get("title") or "").strip(),
                summary=str(r.get("summary") or "").strip(),
                detail=str(r.get("detail") or "").strip(),
                mandatory_or_conditional=str(r.get("mandatory_or_conditional") or "conditional"),
                trigger_conditions=[str(c) for c in (r.get("trigger_conditions") or [])],
                evidence_excerpt=str(r.get("evidence_excerpt") or "").strip(),
                # Never trust an AI "High"; cap at Medium until human review.
                confidence_label="Medium" if str(r.get("confidence_label")).lower() == "medium" else "Low",
            )
            for r in (raw.get("requirements") or [])
            # Guardrail: drop any card without evidence — no uncited requirements.
            if str(r.get("evidence_excerpt") or "").strip() and str(r.get("title") or "").strip()
        ]
        return ExtractionResult(
            requirements=requirements,
            missing_questions=[str(q) for q in (raw.get("missing_questions") or [])],
            buyer_questions=[str(q) for q in (raw.get("buyer_questions") or [])],
            cha_questions=[str(q) for q in (raw.get("cha_questions") or [])],
            ambiguities=[str(q) for q in (raw.get("ambiguities") or [])],
            evidence_summary=str(raw.get("evidence_summary") or "").strip(),
        )

    def generate_missing_questions(
        self, *, country: str, product_category: str, hsn_code: str | None, product_description: str
    ) -> list[str]:
        system = (
            "You generate clarifying questions an exporter must answer before compliance can be "
            "determined. Return STRICT JSON: {\"questions\": [\"...\"]}. Do not answer them."
        )
        user = (
            f"Destination: {country}\nCategory: {product_category}\nHSN: {hsn_code or 'unknown'}\n"
            f"Product description: {product_description}\n"
            "List up to 6 specific missing-information questions."
        )
        raw = _chat_json(system, user)
        return [str(q) for q in (raw.get("questions") or [])][:6]

    def summarize_evidence(self, *, source_text: str) -> str:
        system = (
            "Summarise the official source text neutrally in 2-4 sentences. Use only the text. "
            "Return STRICT JSON: {\"summary\": \"...\"}."
        )
        raw = _chat_json(system, source_text[:16000])
        return str(raw.get("summary") or "").strip()

    def flag_ambiguity(self, *, source_text: str) -> list[str]:
        system = (
            "Identify ambiguities, conflicts, or version/date uncertainty in the official source "
            "text. Return STRICT JSON: {\"ambiguities\": [\"...\"]}. Use only the text."
        )
        raw = _chat_json(system, source_text[:16000])
        return [str(a) for a in (raw.get("ambiguities") or [])]


def get_compliance_ai_extractor() -> ComplianceAIExtractor:
    return ComplianceAIExtractor()
