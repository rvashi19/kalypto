from __future__ import annotations

from app.models import ExportShipment, ShipmentDocument
from app.schemas.shipment import DiscrepancyItem, IncentiveEstimate, VerificationReport
from app.services.groq_client import call_groq

_SYSTEM_PROMPT = """You are an expert Indian export documentation auditor.

Given a shipment profile and a list of uploaded documents with their extracted fields,
return a JSON object with exactly this structure:
{
  "overall_risk": "low | medium | high | critical",
  "missing_documents": ["list of document labels that are missing but required"],
  "discrepancies": [
    {
      "field": "field name (e.g. buyer_name, hsn_code, fob_value)",
      "severity": "info | warn | critical",
      "document_a": "Document A name",
      "document_b": "Document B name",
      "value_a": "value in document A",
      "value_b": "value in document B",
      "message": "What the mismatch means",
      "suggested_fix": "How to fix it"
    }
  ],
  "incentive_estimates": [
    {
      "scheme": "RoDTEP | Duty Drawback | IGST Refund | RoSCTL",
      "eligible": true or false,
      "estimated_amount": numeric or null,
      "rate_percent": numeric or null,
      "notes": "explanation",
      "action_items": ["list of actions exporter must take"]
    }
  ],
  "ebrc_gst_reminders": ["list of eBRC and GST refund action reminders"],
  "finance_readiness_score": integer 0-100,
  "finance_readiness_notes": "explanation of the score",
  "recommendations": ["prioritized list of recommended actions"],
  "disclaimer": "Standard AI disclaimer"
}

Check these mismatches across documents:
- Buyer name consistency
- Product description consistency
- HSN code consistency
- FOB/CIF value consistency
- Port of loading/destination consistency
- Invoice number and date references
- Quantity and weight consistency
- Incoterm consistency
- Payment term consistency

Return ONLY the JSON object."""


def run_verification(
    shipment: ExportShipment,
    documents: list[ShipmentDocument],
) -> VerificationReport:
    doc_summary = "\n".join(
        f"- {doc.document_type} ({doc.file_name}): {doc.extracted_fields or 'No fields extracted yet'}"
        for doc in documents
    )

    user_msg = (
        f"Shipment profile:\n"
        f"  Product: {shipment.product_name}\n"
        f"  HSN: {shipment.hsn_code}\n"
        f"  Destination: {shipment.destination_country}\n"
        f"  Buyer country: {shipment.buyer_country}\n"
        f"  Incoterm: {shipment.incoterm}\n"
        f"  Payment term: {shipment.payment_term}\n"
        f"  Shipment mode: {shipment.shipment_mode}\n"
        f"  Shipment stage: {shipment.shipment_stage}\n"
        f"  FOB value: {shipment.fob_value} {shipment.invoice_currency}\n"
        f"  Exporter: {shipment.exporter_name}\n\n"
        f"Uploaded documents:\n{doc_summary if documents else 'None uploaded yet'}"
    )

    data = call_groq(system_prompt=_SYSTEM_PROMPT, user_message=user_msg)

    return VerificationReport(
        shipment_id=shipment.id,
        overall_risk=data.get("overall_risk", "medium"),
        missing_documents=data.get("missing_documents", []),
        discrepancies=[DiscrepancyItem(**d) for d in data.get("discrepancies", [])],
        incentive_estimates=[IncentiveEstimate(**e) for e in data.get("incentive_estimates", [])],
        ebrc_gst_reminders=data.get("ebrc_gst_reminders", []),
        finance_readiness_score=data.get("finance_readiness_score", 0),
        finance_readiness_notes=data.get("finance_readiness_notes", ""),
        recommendations=data.get("recommendations", []),
        disclaimer=data.get(
            "disclaimer",
            "This report is AI-generated. Verify all findings with your CHA, bank, and DGFT before acting.",
        ),
    )
