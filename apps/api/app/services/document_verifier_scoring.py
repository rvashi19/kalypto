# ruff: noqa: E501
"""Scoring for the AI Document Verifier (pre-filing / pre-claim audit checker).

Single source of truth for all scoring weights and rules — do not scatter scoring
values elsewhere. The score estimates document consistency based on uploaded files
and source-backed KALYPTO checks; it is guidance for manual review, never a claim
of legal/customs approval or 100% accuracy.

Resolved/ignored rule (documented, keep consistent with tests + docs):
  * resolved issues carry NO penalty (the user fixed them),
  * ignored issues carry HALF penalty (accepted risk — still visible, still costs),
  * open issues carry full penalty.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

# ── All scoring weights in ONE place ─────────────────────────────────────────
SCORING_WEIGHTS: dict[str, Any] = {
    # penalty per open issue, by severity
    "issue_severity": {"critical": 25, "high": 15, "medium": 7, "low": 2, "info": 0},
    # multiplier applied to an issue's penalty based on its review status
    "issue_status_multiplier": {"open": 1.0, "ignored": 0.5, "resolved": 0.0},
    # penalty per missing requested document, by priority
    "missing_document": {"critical": 25, "high": 15, "medium": 7, "low": 2},
    # extraction-confidence penalties (confidence is on a 0-100 scale)
    "low_confidence_threshold": 60,
    "low_confidence_penalty_important": 5,
    "low_confidence_penalty_critical": 10,
    # fields treated as critical for confidence purposes
    "critical_fields": {"hsn_code", "fob_value", "total_invoice_value", "claim_fob_value", "incentive_hsn"},
    # score bands -> label
    "bands": [
        (90, "Strong consistency — manual review still recommended"),
        (75, "Mostly consistent — review flagged issues"),
        (50, "Needs correction before filing/claiming"),
        (0, "High risk — do not file/claim before review"),
    ],
}

DISCLAIMER = (
    "This score estimates document consistency based on uploaded files and "
    "source-backed KALYPTO checks. Manual review with a CHA/customs broker is "
    "still required."
)

# Core documents the checker expects for a filing-ready pack:
# (document_type, priority, required_for, reason, related_fields)
CORE_EXPECTED_DOCUMENTS: list[tuple[str, str, str, str, list[str]]] = [
    (
        "commercial_invoice", "critical", "filing",
        "Upload the Commercial Invoice to verify invoice value, HSN, and buyer details.",
        ["invoice_number", "total_invoice_value", "hsn_code", "buyer_name"],
    ),
    (
        "shipping_bill", "critical", "claim",
        "Upload the Shipping Bill to verify FOB value and claim details.",
        ["shipping_bill_number", "fob_value", "claim_fob_value", "incentive_hsn"],
    ),
    (
        "packing_list", "high", "consistency",
        "Upload the Packing List to verify package count, net weight, and gross weight.",
        ["number_of_packages", "net_weight", "gross_weight"],
    ),
    (
        "bill_of_lading", "high", "consistency",
        "Upload the Bill of Lading or Air Waybill to verify shipment details.",
        ["bl_awb_number", "container_number", "port_of_loading", "port_of_discharge"],
    ),
    (
        "certificate_of_origin", "medium", "filing",
        "Upload the Certificate of Origin to verify the origin country.",
        ["country_of_origin"],
    ),
    (
        "letter_of_credit", "low", "optional_review",
        "Upload the Letter of Credit or Purchase Order to verify buyer/payment terms.",
        ["payment_terms", "po_number", "buyer_name"],
    ),
]

# document types that satisfy another expected type (e.g. AWB satisfies BL slot)
DOCUMENT_TYPE_EQUIVALENTS: dict[str, set[str]] = {
    "bill_of_lading": {"bill_of_lading", "airway_bill"},
    "letter_of_credit": {"letter_of_credit", "purchase_order"},
    "commercial_invoice": {"commercial_invoice", "invoice_packing_list", "proforma_invoice"},
    "packing_list": {"packing_list", "invoice_packing_list"},
}

READINESS_LABELS = {
    "ready_for_manual_review": "Ready for manual review",
    "needs_minor_review": "Needs minor review",
    "needs_corrections": "Needs correction",
    "high_risk_do_not_file_without_review": "High risk — review required before filing",
    "waiting_for_required_documents": "Waiting for required documents",
}


@dataclass(frozen=True, slots=True)
class ScoringResult:
    overall_score: int
    document_completeness_score: int
    field_consistency_score: int
    extraction_confidence_score: int
    claim_filing_risk_score: int
    score_label: str
    readiness_status: str
    score_explanation: str
    score_breakdown: dict[str, int] = field(default_factory=dict)
    penalty_breakdown: list[dict[str, Any]] = field(default_factory=list)
    recommended_next_actions: list[str] = field(default_factory=list)

    def as_json(self) -> dict[str, Any]:
        return {
            "overall_score": self.overall_score,
            "document_completeness_score": self.document_completeness_score,
            "field_consistency_score": self.field_consistency_score,
            "extraction_confidence_score": self.extraction_confidence_score,
            "claim_filing_risk_score": self.claim_filing_risk_score,
            "score_label": self.score_label,
            "readiness_status": self.readiness_status,
            "readiness_label": READINESS_LABELS.get(self.readiness_status, self.readiness_status),
            "score_explanation": self.score_explanation,
            "score_breakdown": self.score_breakdown,
            "penalty_breakdown": self.penalty_breakdown,
            "recommended_next_actions": self.recommended_next_actions,
            "disclaimer": DISCLAIMER,
        }


def _clamp(value: float) -> int:
    return int(max(0, min(100, round(value))))


def score_label(score: int) -> str:
    for threshold, label in SCORING_WEIGHTS["bands"]:
        if score >= threshold:
            return str(label)
    return str(SCORING_WEIGHTS["bands"][-1][1])


def build_requested_documents(
    *,
    uploaded_types: set[str],
    ccr_required_types: set[str],
    document_type_labels: dict[str, str],
) -> list[dict[str, Any]]:
    """Build the requested-document list (core pack + CCR-required certificates)."""
    requested: list[dict[str, Any]] = []
    for doc_type, priority, required_for, reason, related_fields in CORE_EXPECTED_DOCUMENTS:
        satisfied_by = DOCUMENT_TYPE_EQUIVALENTS.get(doc_type, {doc_type})
        status = "uploaded" if uploaded_types & satisfied_by else "missing"
        requested.append(
            {
                "document_type": doc_type,
                "label": document_type_labels.get(doc_type, doc_type),
                "reason": reason,
                "priority": priority,
                "related_fields": related_fields,
                "required_for": required_for,
                "status": status,
            }
        )
    for doc_type in sorted(ccr_required_types):
        if any(item["document_type"] == doc_type for item in requested):
            continue
        label = document_type_labels.get(doc_type, doc_type)
        requested.append(
            {
                "document_type": doc_type,
                "label": label,
                "reason": f"Upload the {label} because CCR source-backed data indicates it may be required.",
                "priority": "high",
                "related_fields": [],
                "required_for": "CCR",
                "status": "uploaded" if doc_type in uploaded_types else "missing",
            }
        )
    return requested


def calculate_scores(
    *,
    issues: list[Any],
    requested_documents: list[dict[str, Any]],
    extracted_fields: Sequence[Any],
    documents_count: int,
) -> ScoringResult:
    """Compute overall + category scores from issues, requested docs, and field confidence.

    `issues` items need .severity/.status/.title/.issue_type; `extracted_fields`
    items need .field_key/.field_label/.confidence_score (0-100 scale).
    """
    weights = SCORING_WEIGHTS
    penalties: list[dict[str, Any]] = []

    # 1) Issue penalties (field consistency + claim risk), honoring resolved/ignored rule.
    consistency_penalty = 0.0
    for issue in issues:
        base = weights["issue_severity"].get(issue.severity, weights["issue_severity"]["medium"])
        multiplier = weights["issue_status_multiplier"].get(issue.status, 1.0)
        amount = base * multiplier
        if amount > 0:
            penalties.append(
                {
                    "category": "field_consistency",
                    "points": amount,
                    "reason": f"{issue.severity.title()} issue{' (ignored — accepted risk)' if issue.status == 'ignored' else ''}: {issue.title}",
                }
            )
        consistency_penalty += amount

    # 2) Missing requested documents (document completeness).
    completeness_penalty = 0.0
    missing_docs = [doc for doc in requested_documents if doc["status"] == "missing"]
    for doc in missing_docs:
        amount = weights["missing_document"].get(doc["priority"], weights["missing_document"]["medium"])
        completeness_penalty += amount
        penalties.append(
            {
                "category": "document_completeness",
                "points": amount,
                "reason": f"{doc['label']} is missing ({doc['priority']} priority).",
            }
        )

    # 3) Extraction confidence.
    confidence_penalty = 0.0
    threshold = weights["low_confidence_threshold"]
    for extracted in extracted_fields:
        if extracted.confidence_score >= threshold:
            continue
        is_critical = extracted.field_key in weights["critical_fields"]
        amount = (
            weights["low_confidence_penalty_critical"]
            if is_critical
            else weights["low_confidence_penalty_important"]
        )
        confidence_penalty += amount
        penalties.append(
            {
                "category": "extraction_confidence",
                "points": amount,
                "reason": f"Low-confidence extraction for {extracted.field_label} ({int(extracted.confidence_score)}%).",
            }
        )

    field_consistency_score = _clamp(100 - consistency_penalty)
    document_completeness_score = _clamp(100 - completeness_penalty)
    extraction_confidence_score = _clamp(100 - confidence_penalty)
    # Claim/filing risk combines everything that would worry a CHA before filing/claiming.
    claim_filing_risk_score = _clamp(100 - (consistency_penalty + completeness_penalty))
    overall = _clamp(100 - (consistency_penalty + completeness_penalty + confidence_penalty))

    # Readiness status.
    critical_missing = any(doc["priority"] == "critical" for doc in missing_docs)
    if documents_count == 0 or critical_missing:
        readiness = "waiting_for_required_documents"
    elif overall >= 90:
        readiness = "ready_for_manual_review"
    elif overall >= 75:
        readiness = "needs_minor_review"
    elif overall >= 50:
        readiness = "needs_corrections"
    else:
        readiness = "high_risk_do_not_file_without_review"

    # Explanation: top penalty reasons, largest first.
    top = sorted(penalties, key=lambda p: p["points"], reverse=True)[:4]
    if top:
        explanation = "Score reduced because " + "; ".join(p["reason"].rstrip(".") for p in top) + "."
    else:
        explanation = "No score reductions found. Manual review is still recommended before filing."

    # Recommended next actions.
    actions: list[str] = []
    for doc in sorted(missing_docs, key=lambda d: ["critical", "high", "medium", "low"].index(d["priority"]))[:3]:
        actions.append(doc["reason"])
    open_issues = [issue for issue in issues if issue.status == "open"]
    for issue in sorted(open_issues, key=lambda i: weights["issue_severity"].get(i.severity, 0), reverse=True)[:3]:
        actions.append(f"Resolve: {issue.title}.")
    low_conf = [p for p in penalties if p["category"] == "extraction_confidence"]
    if low_conf:
        actions.append("Review low-confidence extractions against the original documents.")
    actions.append("Manual review with a CHA/customs broker is recommended before filing.")

    return ScoringResult(
        overall_score=overall,
        document_completeness_score=document_completeness_score,
        field_consistency_score=field_consistency_score,
        extraction_confidence_score=extraction_confidence_score,
        claim_filing_risk_score=claim_filing_risk_score,
        score_label=score_label(overall),
        readiness_status=readiness,
        score_explanation=explanation,
        score_breakdown={
            "document_completeness": document_completeness_score,
            "field_consistency": field_consistency_score,
            "extraction_confidence": extraction_confidence_score,
            "claim_filing_risk": claim_filing_risk_score,
        },
        penalty_breakdown=penalties,
        recommended_next_actions=actions,
    )
