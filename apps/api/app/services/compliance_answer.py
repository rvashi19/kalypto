# ruff: noqa: E501
from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import ComplianceChatMessage, ComplianceChatSession
from app.schemas.compliance import (
    ComplianceCheckerRequest,
    ComplianceCheckerResponse,
    ComplianceCheckerSections,
    ComplianceSourceReference,
    ConfidenceLevel,
    ProductSummary,
)
from app.services.compliance_retrieval import RequirementMatch
from app.services.compliance_store import get_compliance_knowledge_store

DISCLAIMER = (
    "This is compliance assistance based on available stored sources. Verify with your customs "
    "broker, importer, CHA, freight forwarder, or the destination regulatory authority before shipment."
)

CATEGORY_QUESTIONS = {
    "food/agri": [
        "Is the shipment retail packed or bulk/B2B?",
        "Is the product raw or processed?",
        "Does it contain animal-origin ingredients?",
        "Does the buyer require organic, halal, or kosher certification?",
        "Is a phytosanitary, fumigation, or food safety certificate already available?",
    ],
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

    def answer(self, *, payload: ComplianceCheckerRequest, tenant_id: UUID, user_id: UUID) -> ComplianceCheckerResponse:
        store = get_compliance_knowledge_store(self.session, tenant_id)
        matches = store.retrieve(
            product=payload.product,
            hsn_code=payload.hsn_code,
            destination_country=payload.destination_country,
            category=payload.category,
        )
        response = self._build_response(payload=payload, matches=matches)
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
    ) -> ComplianceCheckerResponse:
        assumptions = self._assumptions(payload)
        sections = self._sections(payload, assumptions, matches)
        unresolved_questions = self._unresolved_questions(payload)
        follow_up_questions = self._follow_up_questions(payload)

        if not matches:
            response = ComplianceCheckerResponse(
                status="insufficient_data",
                answer=(
                    "Insufficient verified data available for this country/category/product combination. "
                    "Add official source records through the compliance ingestion endpoint or verify manually "
                    "with the buyer/importer and destination authority."
                ),
                follow_up_questions=follow_up_questions,
                sections=sections,
                confidence_level="Low",
                confidence_explanation="No verified stored compliance records were retrieved.",
                unresolved_questions=unresolved_questions or follow_up_questions,
                disclaimer=DISCLAIMER,
            )
            return response

        confidence_level, confidence_explanation = self._confidence(matches, unresolved_questions)
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
            unresolved_questions=unresolved_questions,
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
            grouped[section_name].append(requirement.requirement_text)
            source_key = (requirement.source_name, requirement.source_url)
            sources[source_key] = ComplianceSourceReference(
                source_name=requirement.source_name,
                source_url=requirement.source_url,
                last_scraped_date=requirement.last_scraped_at.astimezone(UTC).date().isoformat(),
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
            "Records are operator-seeded or ingested from verified source pages; missing facts require manual verification.",
        ]
        if not payload.hsn_code:
            assumptions.append("HSN is not confirmed; classification must be verified before relying on this result.")
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
            questions.insert(0, "What is the confirmed HSN code? If unknown, describe the product for classification review.")
        return questions[:6]

    @staticmethod
    def _unresolved_questions(payload: ComplianceCheckerRequest) -> list[str]:
        unresolved = []
        if not payload.hsn_code:
            unresolved.append("Confirm the HSN classification with your CHA/customs broker.")
        if payload.category in {"food/agri", "spices", "dry fruits", "beverages"}:
            unresolved.append("Confirm whether the destination buyer/importer needs product registration before shipment.")
        if payload.category == "textiles":
            unresolved.append("Confirm final fiber composition, care label, and children/baby use case before retail shipment.")
        return unresolved

    @staticmethod
    def _confidence(
        matches: list[RequirementMatch],
        unresolved_questions: list[str],
    ) -> tuple[ConfidenceLevel, str]:
        average = sum(match.score for match in matches) / len(matches)
        if average >= 80 and not unresolved_questions:
            return "High", "Official or high-confidence records matched the country, category, and product context."
        if average >= 55:
            return "Medium", "Stored records matched the country/category, but product-specific details still need confirmation."
        return "Low", "Records were found, but confidence is limited by generic matching or unresolved product details."

    @staticmethod
    def _format_answer(
        *,
        sections: ComplianceCheckerSections,
        confidence_level: str,
        confidence_explanation: str,
    ) -> str:
        def lines(title: str, values: list[str]) -> list[str]:
            if not values:
                return [title, "- No verified stored requirement found; verification required."]
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
            *lines("6. Inspection / Testing Requirements", sections.inspection_testing_requirements),
            "",
            *lines("7. Buyer-Side Questions to Confirm", sections.buyer_side_questions),
            "",
            "8. Source References",
            *[
                f"- {source.source_name}: {source.source_url} (last scraped {source.last_scraped_date})"
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