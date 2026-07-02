# ruff: noqa: E501
"""/compliance/check orchestration (Country Compliance Checker v1).

Search approved local requirements first -> answer with citations. If none, create a
retrieval job (non-blocking) and return retrieval_queued. Persists a ComplianceCheckSession.
Reuses the existing knowledge store, normalization, and freshness logic; does not modify
the legacy CountryComplianceCheckerService.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import ComplianceCheckSession, ComplianceRetrievalJob
from app.schemas.compliance import (
    ComplianceCheckRequest,
    ComplianceCheckResponse,
    ComplianceRequirementCard,
    ComplianceSourceReference,
)
from app.services.compliance_answer import CATEGORY_QUESTIONS, DISCLAIMER
from app.services.compliance_normalization import (
    SUPPORTED_CATEGORIES,
    SUPPORTED_COUNTRIES,
)
from app.services.compliance_retrieval import RequirementMatch
from app.services.compliance_store import get_compliance_knowledge_store

NO_SOURCE_MESSAGE = (
    "No verified official requirement found in the current knowledge base or "
    "official-source search."
)

WARNINGS = [
    "This is source-backed guidance, not legal/customs filing advice.",
    "Verify with importer, CHA/customs broker, and relevant authority before shipment.",
    "Requirements may vary by product composition, end use, packaging, and destination regulations.",
]

# requirement_type (normalized) -> user-facing group
GROUP_BY_TYPE = {
    "import_document": "documents",
    "labeling": "labels",
    "certificate": "certificates",
    "inspection": "inspections",
    "restriction": "restrictions",
    "buyer_question": "buyer_questions",
}
GROUPS = ("documents", "labels", "certificates", "inspections", "licences", "restrictions")


def _cha_questions(payload: ComplianceCheckRequest) -> list[str]:
    questions = [
        "Confirm the exact HSN classification and applicable export duty/cess for this product.",
        "Is any DGFT export licence, LUT, or restricted/prohibited-item clearance required?",
        "Confirm port of loading, customs formalities, and any pre-shipment inspection at origin.",
    ]
    if not payload.hsn_code:
        questions.insert(0, "HSN is not confirmed — please classify before filing the shipping bill.")
    return questions


def _missing_questions(payload: ComplianceCheckRequest) -> list[str]:
    questions: list[str] = []
    if not payload.hsn_code:
        questions.append(
            "What is the confirmed HSN code? If unknown, describe the product for classification."
        )
    if len(payload.product_description.strip()) < 12:
        questions.append(
            "Provide a fuller product description (composition, processing, packaging, end use)."
        )
    for q in CATEGORY_QUESTIONS.get(payload.product_category, []):
        questions.append(q)
    return list(dict.fromkeys(questions))[:6]


def _confidence(matches: list[RequirementMatch]) -> tuple[str, float]:
    if not matches:
        return "Low", 0.0
    avg = sum(m.score for m in matches) / len(matches)
    if avg >= 80:
        return "High", round(avg, 1)
    if avg >= 55:
        return "Medium", round(avg, 1)
    return "Low", round(avg, 1)


def _date_string(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).date().isoformat()


class ComplianceCheckService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def check(
        self, *, payload: ComplianceCheckRequest, tenant_id: UUID, user_id: UUID | None
    ) -> ComplianceCheckResponse:
        supported = (
            payload.destination_country in SUPPORTED_COUNTRIES
            and payload.product_category in SUPPORTED_CATEGORIES
        )
        missing_questions = _missing_questions(payload)
        buyer_questions = list(CATEGORY_QUESTIONS.get(payload.product_category, []))
        cha_questions = _cha_questions(payload)

        matches: list[RequirementMatch] = []
        if supported:
            store = get_compliance_knowledge_store(self.session, tenant_id)
            matches = store.retrieve(
                product=payload.product_description,
                hsn_code=payload.hsn_code,
                destination_country=payload.destination_country,
                category=payload.product_category,
            )

        grouped, sources = self._group(matches)
        confidence_label, confidence_score = _confidence(matches)

        retrieval_job_id: UUID | None = None
        if matches:
            status = "answered"
            answer_summary = (
                f"{sum(len(v) for v in grouped.values())} approved, source-backed requirement(s) "
                f"found for {payload.product_category} to {payload.destination_country}."
            )
        else:
            # No approved local answer. Queue official-source retrieval if requested.
            if payload.start_retrieval and supported:
                job = ComplianceRetrievalJob(
                    tenant_id=tenant_id,
                    requested_by_user_id=user_id,
                    origin_country=payload.origin_country,
                    destination_country=payload.destination_country,
                    product_category=payload.product_category,
                    hsn_code=payload.hsn_code,
                    product_description=payload.product_description,
                    status="queued",
                )
                self.session.add(job)
                self.session.flush()
                retrieval_job_id = job.id
                status = "retrieval_queued"
                answer_summary = (
                    "No approved compliance requirement found yet. Official-source retrieval "
                    "has been queued; results require review before becoming approved guidance."
                )
            else:
                status = "no_verified_source"
                answer_summary = NO_SOURCE_MESSAGE

        session_row = ComplianceCheckSession(
            tenant_id=tenant_id,
            user_id=user_id,
            origin_country=payload.origin_country,
            destination_country=payload.destination_country,
            hsn_code=payload.hsn_code,
            product_description=payload.product_description,
            product_category=payload.product_category,
            input_facts_json=dict(payload.facts),
            missing_questions_json=missing_questions,
            answer_summary_json={"summary": answer_summary, "groups": {k: [c.model_dump() for c in v] for k, v in grouped.items()}},
            source_ids_json=[m.requirement.id for m in matches],
            confidence_label=confidence_label,
            retrieval_job_id=retrieval_job_id,
            status=status,
        )
        self.session.add(session_row)
        self.session.flush()

        response = ComplianceCheckResponse(
            session_id=str(session_row.id),
            status=status,
            answer_summary=answer_summary,
            requirements=grouped,
            missing_questions=missing_questions,
            buyer_questions=buyer_questions,
            cha_questions=cha_questions,
            confidence_label=confidence_label,
            confidence_score=confidence_score,
            sources=sources,
            warnings=list(WARNINGS),
            retrieval_job_id=str(retrieval_job_id) if retrieval_job_id else None,
            disclaimer=DISCLAIMER,
        )
        self.session.commit()
        return response

    @staticmethod
    def _group(
        matches: list[RequirementMatch],
    ) -> tuple[dict[str, list[ComplianceRequirementCard]], list[ComplianceSourceReference]]:
        grouped: dict[str, list[ComplianceRequirementCard]] = {g: [] for g in GROUPS}
        grouped["buyer_questions"] = []
        sources: dict[tuple[str, str], ComplianceSourceReference] = {}
        for match in matches:
            req = match.requirement
            group = GROUP_BY_TYPE.get(req.requirement_type, "documents")
            grouped.setdefault(group, []).append(
                ComplianceRequirementCard(
                    requirement_type=req.requirement_type,
                    title=req.extracted_requirement[:120],
                    detail=req.extracted_requirement,
                    source_name=req.source_name,
                    source_url=req.source_url,
                    last_checked_date=_date_string(req.last_checked_at),
                    confidence_label=(
                        "High" if match.score >= 80 else "Medium" if match.score >= 55 else "Low"
                    ),
                )
            )
            key = (req.source_name, req.source_url)
            sources[key] = ComplianceSourceReference(
                source_name=req.source_name,
                source_url=req.source_url,
                last_checked_date=_date_string(req.last_checked_at),
                expires_at=_date_string(req.expires_at),
                source_authority_level=req.source_authority_level,
            )
        return grouped, sorted(sources.values(), key=lambda s: s.source_name)
