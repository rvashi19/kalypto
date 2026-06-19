from __future__ import annotations

import json

from groq import Groq

from app.core.settings import get_settings


class GroqClientError(Exception):
    pass


def call_groq(*, system_prompt: str, user_message: str) -> dict:
    settings = get_settings()
    if not settings.groq_api_key:
        raise GroqClientError("GROQ_API_KEY is not configured.")

    client = Groq(api_key=settings.groq_api_key)
    try:
        completion = client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
        )
    except Exception as e:
        raise GroqClientError(f"Groq API request failed: {e}") from e

    content = completion.choices[0].message.content or ""
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        raise GroqClientError(f"Groq returned invalid JSON: {e}") from e
