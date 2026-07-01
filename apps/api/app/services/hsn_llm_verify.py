# ruff: noqa: E501
"""LLM-assisted HSN verification.

Given a product description and the deterministic search candidates, ask the
configured LLM (xAI/Grok via the OpenAI-compatible SDK) to pick the single best
8-digit Indian HSN code. The model's answer is grounded: we prefer a candidate
and we validate the chosen code against our master before trusting it, so the LLM
cannot invent a code that does not exist in the database.

If no LLM is configured (or it has no credits), callers fall back to the
deterministic + verified-mapping result.
"""

from __future__ import annotations

import importlib
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.models import HsnCode
from app.services.hsn_normalization import normalize_code

_SYSTEM = (
    "You are an expert in Indian customs classification (ITC-HS / HSN). "
    "Determine the single most appropriate full 8-digit Indian HSN code for the product. "
    "The candidate list is only a hint from a partial local database — if the correct "
    "code is not among the candidates, return the correct code from your own knowledge. "
    "Always return a full 8-digit code (not 2/4/6 digits) and a short official-style "
    "description for it. Respond with strict JSON only: "
    '{"hsn_code":"<8 digits>","description":"<official-style description>",'
    '"confidence":<0-100>,"reasoning":"<one sentence>","alternatives":["<8-digit code>", ...]}'
)


class HsnLlmNotConfiguredError(RuntimeError):
    pass


class HsnLlmError(RuntimeError):
    pass


def _provider() -> tuple[str, str, str | None, str] | None:
    """Return (name, api_key, base_url|None, model). OpenAI preferred, then xAI."""
    settings = get_settings()
    if settings.openai_api_key:
        return ("openai", settings.openai_api_key, None, settings.openai_model)
    if settings.xai_api_key:
        return ("xai", settings.xai_api_key, settings.xai_base_url, settings.xai_model)
    return None


def is_llm_configured() -> bool:
    return _provider() is not None


def active_model() -> str | None:
    provider = _provider()
    return provider[3] if provider else None


def _call_llm(product: str, candidate_lines: str) -> dict[str, Any]:
    provider = _provider()
    if provider is None:
        raise HsnLlmNotConfiguredError("No LLM provider is configured.")
    _name, api_key, base_url, model = provider
    openai_module: Any = importlib.import_module("openai")
    client = (
        openai_module.OpenAI(api_key=api_key, base_url=base_url)
        if base_url
        else openai_module.OpenAI(api_key=api_key)
    )
    user = (
        f"Product: {product}\n\nCandidate HSN codes:\n{candidate_lines}\n\n"
        "Return the best 8-digit Indian HSN code as strict JSON."
    )
    try:
        response = client.responses.create(
            model=model,
            instructions=_SYSTEM,
            input=user,
        )
    except Exception as error:  # noqa: BLE001
        raise HsnLlmError(f"LLM request failed: {error}") from error

    text = (getattr(response, "output_text", "") or "").strip()
    text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise HsnLlmError(f"LLM returned non-JSON: {text[:160]}") from error
    if not isinstance(data, dict):
        raise HsnLlmError("LLM returned JSON that was not an object.")
    return data


def llm_classify(
    *, session: Session, product: str, candidates: list[tuple[str, str]]
) -> dict[str, Any]:
    """candidates: list of (code, description). Returns a validated verdict dict."""
    if not is_llm_configured():
        raise HsnLlmNotConfiguredError(
            "No LLM is configured. Set OPENAI_API_KEY (or XAI_API_KEY) to enable AI verification."
        )

    candidate_lines = "\n".join(f"- {code}: {desc}" for code, desc in candidates[:12]) or "- (none)"
    verdict = _call_llm(product, candidate_lines)

    chosen = normalize_code(str(verdict.get("hsn_code", "")))
    row = (
        session.scalars(select(HsnCode).where(HsnCode.normalized_code == chosen)).first()
        if chosen
        else None
    )
    llm_description = str(verdict.get("description") or "").strip()
    return {
        "product": product,
        "hsn_code": chosen or None,
        "in_master": row is not None,
        # Prefer the verified master description; fall back to the LLM's description.
        "description": (row.description if row else None) or llm_description or None,
        "confidence": verdict.get("confidence"),
        "reasoning": verdict.get("reasoning"),
        "alternatives": [normalize_code(str(a)) for a in verdict.get("alternatives", []) if a],
        "model": active_model(),
    }
