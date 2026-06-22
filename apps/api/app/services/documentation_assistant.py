from __future__ import annotations

import importlib
from textwrap import dedent
from typing import Any

from app.core.settings import get_settings

DOCUMENTATION_CONTEXT = dedent(
    """
    Product name: KALYPTO.

    KALYPTO is a multi-tenant SaaS platform for Indian exporters.

    Phase 0 features currently available:
    - organization signup
    - owner login/logout with JWT authentication
    - protected dashboard shell
    - tenant-scoped access patterns
    - append-only audit logging
    - demo seed account support
    - docker-compose local development
    - Render deployment for api, web, postgres, and redis

    Phase 0 does not yet include:
    - shipment or GST CSV uploads
    - reconciliation engine workflows in the UI
    - incentive discrepancy dashboards
    - PDF document generation flows
    - direct government portal integrations
    - automatic filing to ICEGATE, DGFT, or GST systems

    Legal and domain guardrails:
    - The platform must never auto-file anything to a government portal.
    - HSN classification and incentive rates are decision-support only.
    - Operators must verify rates with their CHA or customs broker.
    - If a feature is not implemented yet, say so clearly instead of inventing behavior.

    Current live deployment expectations:
    - The frontend calls the backend API on /api/v1.
    - The health check endpoint is /api/v1/health.
    - The AI documentation helper requires XAI_API_KEY to be configured on the API service.
    - The AI helper is for product guidance and onboarding, not legal advice.
    """
).strip()

SYSTEM_PROMPT = dedent(
    """
    You are KALYPTO's AI documentation helper.

    Your job:
    - explain what the currently deployed product does
    - help users onboard, navigate, and understand the dashboard
    - answer using the provided KALYPTO documentation context
    - be honest about features that are not built yet

    Rules:
    - do not invent tax, customs, or legal rules
    - do not claim a feature exists unless it is described in the context
    - if the question asks for a missing feature, say it is not yet implemented
    - if the question asks for legal or customs certainty, advise verification with a CA, CHA, or customs broker
    - keep answers concise and practical
    """
).strip()


class DocumentationAssistantNotConfiguredError(RuntimeError):
    """Raised when the assistant is requested before XAI_API_KEY is configured."""


class DocumentationAssistantService:
    def __init__(self) -> None:
        self.settings = get_settings()

    @property
    def is_configured(self) -> bool:
        return bool(self.settings.xai_api_key)

    def status_message(self) -> str:
        if self.is_configured:
            return "AI documentation helper is ready."
        return "Set XAI_API_KEY on the API service to enable the AI documentation helper."

    def answer(self, question: str) -> str:
        if not self.is_configured:
            raise DocumentationAssistantNotConfiguredError(self.status_message())

        openai_module: Any = importlib.import_module("openai")
        client = openai_module.OpenAI(
            api_key=self.settings.xai_api_key,
            base_url=self.settings.xai_base_url,
        )

        response = client.responses.create(
            model=self.settings.xai_model,
            instructions=f"{SYSTEM_PROMPT}\n\nReference context:\n{DOCUMENTATION_CONTEXT}",
            input=question,
        )
        answer = (response.output_text or "").strip()
        if answer:
            return answer

        raise RuntimeError("The AI documentation helper returned an empty response.")
