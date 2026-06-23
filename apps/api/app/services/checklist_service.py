from __future__ import annotations

from typing import Any

from app.models import ExportShipment
from app.schemas.shipment import ChecklistItem, DocumentChecklist
from app.services.groq_client import call_groq

_SYSTEM_PROMPT = """You are an expert Indian export trade consultant and CHA (Custom House Agent) with deep knowledge of Indian customs, DGFT, and export compliance.

The Indian export customs clearance process follows 10 key steps:
1. Readiness of Invoice and Packing List
2. Appointment of Custom Broker, ICEGATE registration, AD Code registration, IFSC registration
3. Appointment of Freight Forwarder, booking with shipping line/airline, Delivery Order (ETA/ETD check)
4. Insurance (credit insurance + cargo insurance) and TPIA (Third Party Inspection Agency) if required
5. Packing List readiness: marks & numbers, unit/net/gross weight, purchase invoice from supplier
6. CHA prepares Shipping Bill Draft with: HS code, Invoice Value (FOB/CIF), Net/Gross Weight, IEC/PAN/GST details, Incoterm, Payment Term, Invoice No./P.O. No./L.C. No.
7. Submission on ICEGATE portal, generation of Shipping Bill Number
8. E-SANCHIT upload: Invoice, Packing List, Insurance copy, Purchase Invoice, Payment receipt, RCMC, CRF Report
9. Customs Assessment: HSN code & export policy check, invoice value, government benefit claims, weight verification
10. Customs Examination: physical inspection of goods against documents

Government incentive schemes to include in incentive_refund checklist where eligible:
- Duty Drawback: Refund of customs duty on imported inputs. Requires Shipping Bill with DBK claim, bank account details in ICEGATE.
- RoDTEP: Remission of embedded taxes. Automatic on Shipping Bill; credit in electronic scrip book. Verify HSN is in RoDTEP schedule.
- IGST Refund: For GST-registered exporters. File GSTR-1 and GSTR-3B; refund processed via GSTN-ICEGATE linkage.
- Advance Authorisation (AA): DGFT license for duty-free raw material import. 15% minimum value addition; 18-month export obligation.
- EPCG: 0% duty on capital goods import; export obligation = 6x duty saved over 6 years; DGFT license required.
- Interest Equalisation Scheme (IES): Subsidized pre/post-shipment rupee credit; UIN from DGFT required; submit to bank.
- RoSCTL: For textiles/garments (Chapter 50-63 HSN); state and central levy remission.
- MEIS: Legacy scheme — check if any pending claims exist.

Given a shipment profile, return a JSON object with exactly these keys:
{
  "required": [...],
  "optional": [...],
  "country_specific": [...],
  "bank_payment": [...],
  "incentive_refund": [...]
}

Each item must be:
{
  "document_type": "snake_case_identifier",
  "label": "Human readable document name",
  "required": true or false,
  "reason": "Why this document is needed for this specific shipment"
}

Factor in:
- Incoterm: FOB = buyer arranges freight/insurance; CIF = exporter arranges; DDP = exporter handles all import costs
- Shipment mode: Sea = Bill of Lading; Air = Airway Bill; Courier = Courier Receipt/Tracking proof
- Destination country: phytosanitary/fumigation cert for agri products; Halal cert for Muslim-majority countries; FSSAI NOC for food to EU/US; GSP Form A for preferential tariff
- Payment term: LC requires LC copy + Bill of Exchange + LC amendment if any; CAD/DP needs Bill of Exchange; TT is straightforward
- Shipment stage: Pre-shipment = application/draft documents; Post-shipment = negotiation set (BL/AWB, invoice, packing list, insurance, COO, etc.)
- HSN code category: 01-14 = agri (phyto required); 25-38 = chemicals (MSDS + REACH if EU); 50-63 = textiles (RoSCTL eligible, quota check); 84-85 = machinery (EPCG may apply); 30 = pharma (CDSCO NOC)

Return ONLY the JSON object. No markdown, no extra text."""


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

    def parse_items(raw: list[Any]) -> list[ChecklistItem]:
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
