from __future__ import annotations

from app.models import ExportShipment
from app.schemas.shipment import ChecklistItem, DocumentChecklist
from app.services.groq_client import call_groq

_SYSTEM_PROMPT = """You are an expert in Indian export trade documentation and compliance.

Given a shipment profile, return a JSON object with exactly these keys:
{
  "required": [...],
  "optional": [...],
  "country_specific": [...],
  "bank_payment": [...],
  "incentive_refund": [...]
}

Each item in every list must be:
{
  "document_type": "snake_case_identifier",
  "label": "Human readable document name",
  "required": true or false,
  "reason": "Why this document is needed for this shipment"
}

Base your response on:
- Incoterm (FOB/CIF/DDP changes document requirements significantly)
- Shipment mode (sea vs air vs courier has different BL/AWB requirements)
- Destination country (some countries need phytosanitary, fumigation, halal certs etc)
- Payment term (LC requires specific docs; TT/DP differs)
- Shipment stage (pre vs post changes what's available and what's needed)
- HSN code category (food/agri needs phyto/fumigation, chemicals need MSDS, etc)

Return ONLY the JSON object. No markdown."""


def generate_checklist(shipment: ExportShipment) -> DocumentChecklist:
    user_msg = (
        f"Product: {shipment.product_name}\n"
        f"HSN: {shipment.hsn_code}\n"
        f"Destination country: {shipment.destination_country}\n"
        f"Buyer country: {shipment.buyer_country}\n"
        f"Incoterm: {shipment.incoterm}\n"
        f"Payment term: {shipment.payment_term}\n"
        f"Shipment mode: {shipment.shipment_mode}\n"
        f"Container type: {shipment.container_type or 'N/A'}\n"
        f"Shipment stage: {shipment.shipment_stage}\n"
        f"FOB value: {shipment.fob_value} {shipment.invoice_currency}"
    )

    data = call_groq(system_prompt=_SYSTEM_PROMPT, user_message=user_msg)

    def parse_items(raw: list) -> list[ChecklistItem]:
        return [ChecklistItem(**item) for item in (raw or [])]

    return DocumentChecklist(
        required=parse_items(data.get("required", [])),
        optional=parse_items(data.get("optional", [])),
        country_specific=parse_items(data.get("country_specific", [])),
        bank_payment=parse_items(data.get("bank_payment", [])),
        incentive_refund=parse_items(data.get("incentive_refund", [])),
        disclaimer=(
            "This checklist is AI-generated based on the shipment profile. "
            "Always verify with your CHA, bank, and destination country requirements."
        ),
    )
