from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

Severity = Literal["info", "warn", "critical"]


@dataclass(frozen=True, slots=True)
class StructuredDocument:
    document_type: str
    file_name: str
    fields: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ReconciliationInput:
    hsn_code: str
    buyer_country: str
    incoterm: str
    fob_value: Decimal | None
    shipment_stage: str
    shipping_bill_no: str | None
    shipment_date: datetime | None
    documents: list[StructuredDocument]
    verified_rates: dict[str, Decimal] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ReconciliationIssue:
    type: str
    severity: Severity
    message: str
    suggested_fix: str
    lock_risk: bool = False
    potential_amount: Decimal | None = None


@dataclass(frozen=True, slots=True)
class ReconciliationResult:
    issues: list[ReconciliationIssue]
    potential_amount: Decimal


def _clean(value: Any) -> str:
    return str(value or "").strip().casefold()


def _values(documents: list[StructuredDocument], field_name: str) -> dict[str, str]:
    return {
        document.file_name: str(document.fields[field_name]).strip()
        for document in documents
        if document.fields.get(field_name) not in (None, "")
    }


def _cross_document_issue(
    documents: list[StructuredDocument],
    field_name: str,
    label: str,
) -> ReconciliationIssue | None:
    values = _values(documents, field_name)
    if len({_clean(value) for value in values.values()}) <= 1:
        return None
    rendered = ", ".join(f"{name}: {value}" for name, value in values.items())
    return ReconciliationIssue(
        type=f"{field_name}_mismatch",
        severity="critical",
        message=f"{label} is inconsistent across uploaded documents ({rendered}).",
        suggested_fix=f"Correct the {label.lower()} before customs or bank submission.",
        lock_risk=True,
    )


def reconcile_shipment(payload: ReconciliationInput) -> ReconciliationResult:
    issues: list[ReconciliationIssue] = []
    available_types = {document.document_type for document in payload.documents}
    required = {"commercial_invoice", "packing_list"}
    if payload.shipment_stage == "post_shipment":
        required.update({"shipping_bill", "bl_awb"})
    for document_type in sorted(required - available_types):
        issues.append(
            ReconciliationIssue(
                type="missing_document",
                severity="critical",
                message=f"Required document is missing: {document_type.replace('_', ' ')}.",
                suggested_fix="Upload the final issued document and rerun reconciliation.",
                lock_risk=document_type == "shipping_bill",
            )
        )

    for field_name, label in (
        ("invoice_number", "Invoice number"),
        ("hsn_code", "HSN code"),
        ("buyer_name", "Buyer name"),
        ("fob_value", "FOB value"),
        ("incoterm", "Incoterm"),
        ("igst_amount", "IGST amount"),
    ):
        issue = _cross_document_issue(payload.documents, field_name, label)
        if issue is not None:
            issues.append(issue)

    document_hsn = _values(payload.documents, "hsn_code")
    if any(_clean(value) != _clean(payload.hsn_code) for value in document_hsn.values()):
        issues.append(
            ReconciliationIssue(
                type="shipment_hsn_mismatch",
                severity="critical",
                message="The shipment HSN does not match one or more uploaded documents.",
                suggested_fix="Confirm classification with your CHA and align every document.",
                lock_risk=True,
            )
        )

    ad_codes = _values(payload.documents, "ad_code")
    if not ad_codes:
        issues.append(
            ReconciliationIssue(
                type="ad_code_missing",
                severity="warn",
                message="No AD code was found in the extracted shipment documents.",
                suggested_fix=(
                    "Confirm AD code registration and include it where the filing requires it."
                ),
            )
        )
    elif any(not value.isdigit() or len(value) not in {7, 14} for value in ad_codes.values()):
        issues.append(
            ReconciliationIssue(
                type="ad_code_format",
                severity="warn",
                message="An extracted AD code does not match the configured basic format check.",
                suggested_fix="Verify the exact AD code with the authorized dealer bank and CHA.",
            )
        )

    potential = Decimal("0")
    if payload.fob_value is not None:
        for scheme, rate in payload.verified_rates.items():
            amount = (payload.fob_value * rate / Decimal("100")).quantize(Decimal("0.01"))
            potential += amount
            issues.append(
                ReconciliationIssue(
                    type="claim_status_unconfirmed",
                    severity="info",
                    message=(
                        f"{scheme} has a verified rate record, but claimed/received data is not "
                        "available for this shipment."
                    ),
                    suggested_fix=(
                        "Add the filed and received claim amounts before treating this estimate "
                        "as money at risk."
                    ),
                    potential_amount=amount,
                )
            )

    return ReconciliationResult(issues=issues, potential_amount=potential)
