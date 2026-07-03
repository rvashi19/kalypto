from __future__ import annotations

from app.services import compliance_ai_extractor as ai_module


def test_chat_json_repairs_malformed_ai_json(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    def fake_chat_text(system: str, user: str) -> str:
        calls.append((system, user))
        if len(calls) == 1:
            return '{"requirements": [}'
        return (
            '{"requirements": [], "missing_questions": ["HSN?"], '
            '"buyer_questions": [], "cha_questions": [], "ambiguities": [], '
            '"evidence_summary": "Repaired."}'
        )

    monkeypatch.setattr(ai_module, "_chat_text", fake_chat_text)

    result = ai_module._chat_json("schema", "source text")

    assert result["missing_questions"] == ["HSN?"]
    assert len(calls) == 2
    assert "repair" in calls[1][0].lower()
