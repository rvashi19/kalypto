# ruff: noqa: E501
"""GPT-assisted anomaly detection for imported incentive rates.

The LLM is used ONLY to flag suspicious rows for human review (e.g. a rate that
looks implausible for the scheme/product). It is never a source of truth and never
changes a rate value or approves anything — it only writes a review note.
"""

from __future__ import annotations

import importlib
import json
from typing import Any

from sqlalchemy.orm import Session

from app.models import IncentiveRate
from app.services.hsn_llm_verify import HsnLlmNotConfiguredError, _provider, is_llm_configured

_SYSTEM = (
    "You are auditing Indian export incentive rates (RoDTEP/Drawback/RoSCTL). For each row "
    "decide only whether the rate looks anomalous for that scheme and product (e.g. clearly "
    "out of the usual range, or mismatched). Do not invent correct values. Respond with strict "
    'JSON only: {"flags":[{"index":<int>,"suspicious":<bool>,"reason":"<short>"}]}'
)


def anomaly_check(*, session: Session, rates: list[IncentiveRate], limit: int = 40) -> dict[str, Any]:
    if not is_llm_configured():
        raise HsnLlmNotConfiguredError("No LLM configured. Set OPENAI_API_KEY to enable anomaly checks.")
    provider = _provider()
    assert provider is not None
    _name, api_key, base_url, model = provider

    batch = rates[:limit]
    lines = "\n".join(
        f"{i}. scheme={r.scheme} hsn={r.hsn_code} rate={float(r.rate_value)}{'%' if r.rate_type == 'percentage' else ''} desc={(r.product_description or '')[:60]}"
        for i, r in enumerate(batch)
    )
    openai_module: Any = importlib.import_module("openai")
    client = (
        openai_module.OpenAI(api_key=api_key, base_url=base_url)
        if base_url
        else openai_module.OpenAI(api_key=api_key)
    )
    response = client.responses.create(
        model=model,
        instructions=_SYSTEM,
        input=f"Rows:\n{lines}\n\nReturn the flags JSON.",
    )
    text = (getattr(response, "output_text", "") or "").strip()
    text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {"checked": len(batch), "flagged": 0, "model": model}

    flagged = 0
    for flag in data.get("flags", []):
        if not flag.get("suspicious"):
            continue
        idx = flag.get("index")
        if not isinstance(idx, int) or idx < 0 or idx >= len(batch):
            continue
        row = batch[idx]
        note = f"AI anomaly flag: {flag.get('reason', 'suspicious rate')}"
        row.review_note = note if not row.review_note else f"{row.review_note}; {note}"
        flagged += 1
    session.commit()
    return {"checked": len(batch), "flagged": flagged, "model": model}
