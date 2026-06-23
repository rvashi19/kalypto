# ruff: noqa: E501
from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import ComplianceChatMessage, ComplianceChatSession
from app.schemas.compliance import (
    ComplianceCheckerRequest,
    ComplianceCheckerResponse,
    ComplianceCheckerSections,
    ComplianceSourceReference,
    ComplianceStatus,
    ConfidenceLevel,
    ProductSummary,
)
from app.services.compliance_normalization import SUPPORTED_CATEGORIES, SUPPORTED_COUNTRIES
from app.services.compliance_retrieval import EvidenceReviewContext, RequirementMatch
from app.services.compliance_store import get_compliance_knowledge_store

DISCLAIMER = (
    "This is compliance assistance based on available source-backed records. It is not legal, "
    "customs, or regulatory advice. Verify requirements with the importer, customs broker, "
    "or official authority before shipment."
)
INSUFFICIENT_MESSAGE = (
    "Insufficient verified data available. Please confirm with importer, customs broker, "
    "or regulatory authority."
)

CATEGORY_QUESTIONS = {
    "spices": [
        "Is the spice whole, ground, blended, or processed?",
        "Is the shipment retail packed or bulk/B2B?",
        "Does the buyer require aflatoxin, pesticide residue, organic, halal, or kosher evidence?",
        "Is fumigation or phytosanitary documentation already available?",
    ],
    "dry fruits": [
        "Are the dry fruits raw, roasted, salted, sweetened, or otherwise processed?",
        "Is the shipment retail packed or bulk/B2B?",
        "Does the buyer require aflatoxin, pesticide residue, organic, halal, or kosher evidence?",
        "Is fumigation or phytosanitary documentation already available?",
    ],
    "beverages": [
        "Is it alcoholic or non-alcoholic?",
        "Is it for retail sale or bulk/B2B processing?",
        "What is the packaging type and net quantity?",
        "Does it contain dairy, animal-origin, caffeine, additives, or nutrition/health claims?",
    ],
    "textiles": [
        "What is the material composition?",
        "Is it adult, children, or baby textile?",
        "Has it received any chemical treatment?",
        "Is retail labeling already prepared?",
        "Is it for retail sale or wholesale/importer relabeling?",
    ],
}

SECTION_BY_TYPE = {
    "import_document": "required_import_documents",
    "certificate": "certificates_required",
    "labeling": "labeling_requirements",
    "restriction": "restriction_alerts",
    "inspection": "inspection_testing_requirements",
    "buyer_question": "buyer_side_questions",
}


class CountryComplianceCheckerService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def answer(
        self, *, payload: ComplianceCheckerRequest, tenant_id: UUID, user_id: UUID
    ) -> ComplianceCheckerResponse:
        if (
            payload.destination_country not in SUPPORTED_COUNTRIES
            or payload.category not in SUPPORTED_CATEGORIES
        ):
            response = self._unsupported_scope_response(payload)
            chat_session = self._record_chat(
                payload=payload,
                tenant_id=tenant_id,
                user_id=user_id,
                response=response,
                matches=[],
            )
            response.session_id = str(chat_session.id)
            self.session.commit()
            return response

        store = get_compliance_knowledge_store(self.session, tenant_id)
        matches = store.retrieve(
            product=payload.product,
            hsn_code=payload.hsn_code,
            destination_country=payload.destination_country,
            category=payload.category,
        )
        context = store.review_context(
            destination_country=payload.destination_country,
            category=payload.category,
        )
        response = self._build_response(payload=payload, matches=matches, context=context)
        chat_session = self._record_chat(
            payload=payload,
            tenant_id=tenant_id,
            user_id=user_id,
            response=response,
            matches=matches,
        )
        response.session_id = str(chat_session.id)
        self.session.commit()
        return response

    def _build_response(
        self,
        *,
        payload: ComplianceCheckerRequest,
        matches: list[RequirementMatch],
        context: EvidenceReviewContext,
    ) -> ComplianceCheckerResponse:
        assumptions = self._assumptions(payload)
        sections = self._sections(payload, assumptions, matches)
        unresolved_questions = self._unresolved_questions(payload, matches)
        follow_up_questions = self._follow_up_questions(payload)

        if not matches:
            status_value: ComplianceStatus = (
                "needs_review"
                if context.pending_records or context.stale_records
                else "insufficient_verified_data"
            )
            explanation = "No approved, fresh, source-backed compliance evidence was retrieved."
            if context.stale_records:
                unresolved_questions.append(
                    "Approved evidence exists but is stale and requires review before use."
                )
            if context.pending_records:
                unresolved_questions.append(
                    "Pending or unreviewed evidence exists but is not used in final answers."
                )
            return ComplianceCheckerResponse(
                status=status_value,
                answer=INSUFFICIENT_MESSAGE,
                follow_up_questions=follow_up_questions,
                sections=sections,
                confidence_level="Low",
                confidence_explanation=explanation,
                last_checked_date=None,
                unresolved_questions=unresolved_questions or follow_up_questions,
                disclaimer=DISCLAIMER,
            )

        confidence_level, confidence_explanation = self._confidence(matches, unresolved_questions)
        last_checked_date = self._last_checked_date(matches)
        answer = self._format_answer(
            sections=sections,
            confidence_level=confidence_level,
            confidence_explanation=confidence_explanation,
        )
        return ComplianceCheckerResponse(
            status="answered",
            answer=answer,
            follow_up_questions=follow_up_questions,
            sections=sections,
            confidence_level=confidence_level,
            confidence_explanation=confidence_explanation,
            last_checked_date=last_checked_date,
            unresolved_questions=unresolved_questions,
            disclaimer=DISCLAIMER,
        )

    def _unsupported_scope_response(
        self, payload: ComplianceCheckerRequest
    ) -> ComplianceCheckerResponse:
        assumptions = self._assumptions(payload)
        sections = self._sections(payload, assumptions, [])
        unresolved = [
            "Current V0 scope supports Canada, United Arab Emirates, and UK.",
            "Current V0 categories support beverages, dry fruits, spices, and textiles.",
        ]
        return ComplianceCheckerResponse(
            status="unsupported_scope",
            answer=INSUFFICIENT_MESSAGE,
            follow_up_questions=[],
            sections=sections,
            confidence_level="Low",
            confidence_explanation="The requested country or category is outside the current V0 source-backed scope.",
            last_checked_date=None,
            unresolved_questions=unresolved,
            disclaimer=DISCLAIMER,
        )

    def _sections(
        self,
        payload: ComplianceCheckerRequest,
        assumptions: list[str],
        matches: list[RequirementMatch],
    ) -> ComplianceCheckerSections:
        grouped: dict[str, list[str]] = defaultdict(list)
        sources: dict[tuple[str, str], ComplianceSourceReference] = {}
        for match in matches:
            requirement = match.requirement
            section_name = SECTION_BY_TYPE.get(requirement.requirement_type, "buyer_side_questions")
            grouped[section_name].append(requirement.extracted_requirement)
            source_key = (requirement.source_name, requirement.source_url)
            sources[source_key] = ComplianceSourceReference(
                source_name=requirement.source_name,
                source_url=requirement.source_url,
                last_checked_date=self._date_string(requirement.last_checked_at),
                expires_at=self._date_string(requirement.expires_at),
                source_authority_level=requirement.source_authority_level,
            )

        buyer_questions = list(grouped["buyer_side_questions"])
        for question in CATEGORY_QUESTIONS.get(payload.category, []):
            if question not in buyer_questions:
                buyer_questions.append(question)

        return ComplianceCheckerSections(
            product_summary=ProductSummary(
                product=payload.product,
                hsn=payload.hsn_code,
                destination=payload.destination_country,
                category=payload.category,
                assumptions=assumptions,
            ),
            required_import_documents=grouped["required_import_documents"],
            certificates_required=grouped["certificates_required"],
            labeling_requirements=grouped["labeling_requirements"],
            restriction_alerts=grouped["restriction_alerts"],
            inspection_testing_requirements=grouped["inspection_testing_requirements"],
            buyer_side_questions=buyer_questions,
            source_references=sorted(sources.values(), key=lambda source: source.source_name),
        )

    @staticmethod
    def _assumptions(payload: ComplianceCheckerRequest) -> list[str]:
        assumptions = [
            "Exporter is in India and the destination-country importer/buyer will complete importer-side filings.",
            "Only active, approved, non-stale source-backed records are used for final answers.",
        ]
        if not payload.hsn_code:
            assumptions.append(
                "HSN is not confirmed; classification must be verified before relying on this result."
            )
        for key, value in payload.details.items():
            if value not in (None, ""):
                assumptions.append(f"{key.replace('_', ' ').title()}: {value}")
        return assumptions

    @staticmethod
    def _follow_up_questions(payload: ComplianceCheckerRequest) -> list[str]:
        known_details = {key for key, value in payload.details.items() if value not in (None, "")}
        questions = []
        for question in CATEGORY_QUESTIONS.get(payload.category, []):
            normalized_question = question.lower()
            if "retail" in normalized_question and "retail_or_bulk" in known_details:
                continue
            if "packaging" in normalized_question and "packaging_type" in known_details:
                continue
            if "material" in normalized_question and "material_composition" in known_details:
                continue
            questions.append(question)
        if not payload.hsn_code:
            questions.insert(
                0,
                "What is the confirmed HSN code? If unknown, describe the product for classification review.",
            )
        return questions[:6]

    @staticmethod
    def _unresolved_questions(
        payload: ComplianceCheckerRequest, matches: list[RequirementMatch]
    ) -> list[str]:
        unresolved = []
        if not payload.hsn_code:
            unresolved.append("Confirm the HSN classification with your CHA/customs broker.")
        if payload.category in {"spices", "dry fruits", "beverages"}:
            unresolved.append(
                "Confirm whether the destination buyer/importer needs product registration before shipment."
            )
        if payload.category == "textiles":
            unresolved.append(
                "Confirm final fiber composition, care label, and children/baby use case before retail shipment."
            )
        for match in matches:
            unresolved.extend(match.requirement.unresolved_questions)
        return list(dict.fromkeys(unresolved))

    @staticmethod
    def _confidence(
        matches: list[RequirementMatch],
        unresolved_questions: list[str],
    ) -> tuple[ConfidenceLevel, str]:
        average = sum(match.score for match in matches) / len(matches)
        if average >= 80 and not unresolved_questions:
            return (
                "High",
                "Approved, fresh source-backed records matched the country, category, and product context.",
            )
        if average >= 55:
            return (
                "Medium",
                "Approved source-backed records matched, but product-specific or buyer-side checks remain.",
            )
        return (
            "Low",
            "Records were found, but confidence is limited by generic matching or unresolved product details.",
        )

    @staticmethod
    def _format_answer(
        *,
        sections: ComplianceCheckerSections,
        confidence_level: str,
        confidence_explanation: str,
    ) -> str:
        def lines(title: str, values: list[str]) -> list[str]:
            if not values:
                return [title, "- No approved fresh requirement found; verification required."]
            return [title, *[f"- {value}" for value in values]]

        summary = sections.product_summary
        parts = [
            "Country Compliance Requirement Checker Result",
            "",
            "1. Product Summary",
            f"- Product: {summary.product}",
            f"- HSN: {summary.hsn or 'Not confirmed'}",
            f"- Destination: {summary.destination}",
            f"- Category: {summary.category}",
            *[f"- Assumption: {assumption}" for assumption in summary.assumptions],
            "",
            *lines("2. Required Import Documents", sections.required_import_documents),
            "",
            *lines("3. Certificates Required", sections.certificates_required),
            "",
            *lines("4. Labeling Requirements", sections.labeling_requirements),
            "",
            *lines("5. Restrictions / Prohibited Alerts", sections.restriction_alerts),
            "",
            *lines(
                "6. Inspection / Testing Requirements", sections.inspection_testing_requirements
            ),
            "",
            *lines("7. Buyer-Side Questions to Confirm", sections.buyer_side_questions),
            "",
            "8. Source References",
            *[
                f"- {source.source_name}: {source.source_url} (last checked {source.last_checked_date or 'unknown'})"
                for source in sections.source_references
            ],
            "",
            "9. Confidence Level",
            f"- {confidence_level}: {confidence_explanation}",
            "",
            "10. Disclaimer",
            f"- {DISCLAIMER}",
        ]
        return "\n".join(parts)

    @staticmethod
    def _date_string(value: datetime | None) -> str | None:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC).date().isoformat()

    @classmethod
    def _last_checked_date(cls, matches: list[RequirementMatch]) -> str | None:
        values = [
            match.requirement.last_checked_at
            for match in matches
            if match.requirement.last_checked_at
        ]
        if not values:
            return None
        return cls._date_string(max(values))

    def _record_chat(
        self,
        *,
        payload: ComplianceCheckerRequest,
        tenant_id: UUID,
        user_id: UUID,
        response: ComplianceCheckerResponse,
        matches: list[RequirementMatch],
    ) -> ComplianceChatSession:
        chat_session = ComplianceChatSession(
            tenant_id=tenant_id,
            user_id=user_id,
            product=payload.product,
            hsn_code=payload.hsn_code,
            destination_country=payload.destination_country,
            category=payload.category,
            details=payload.details,
        )
        self.session.add(chat_session)
        self.session.flush()
        retrieved_ids = [str(match.requirement.id) for match in matches]
        self.session.add_all(
            [
                ComplianceChatMessage(
                    tenant_id=tenant_id,
                    session_id=chat_session.id,
                    role="user",
                    message=json.dumps(payload.model_dump(mode="json")),
                    retrieved_requirement_ids=None,
                ),
                ComplianceChatMessage(
                    tenant_id=tenant_id,
                    session_id=chat_session.id,
                    role="assistant",
                    message=response.answer,
                    retrieved_requirement_ids=retrieved_ids,
                ),
            ],
        )
        return chat_session
