# ruff: noqa: E501
"""AI Document Verifier extraction, comparison, and report services."""

from __future__ import annotations

import importlib
import io
import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.models import ComplianceRequirement
from app.models.document_verifier import (
    DocumentExtractedField,
    DocumentVerificationIssue,
    DocumentVerificationReport,
    DocumentVerificationRun,
    VerificationDocument,
)
from app.services.storage import storage

DOCUMENT_TYPE_LABELS = {
    "commercial_invoice": "Commercial Invoice",
    "proforma_invoice": "Proforma Invoice",
    "packing_list": "Packing List",
    "invoice_packing_list": "Invoice-cum-Packing List",
    "shipping_bill": "Shipping Bill / Bill of Export",
    "bill_of_lading": "Bill of Lading",
    "airway_bill": "Air Waybill",
    "certificate_of_origin": "Certificate of Origin",
    "insurance_certificate": "Insurance Certificate",
    "fumigation_certificate": "Fumigation Certificate",
    "phytosanitary_certificate": "Phytosanitary Certificate",
    "inspection_certificate": "Inspection Certificate",
    "purchase_order": "Purchase Order",
    "letter_of_credit": "Letter of Credit",
    "export_quote": "Export Quote",
    "unknown": "Unknown Document",
}

FIELD_LABELS = {
    "exporter_name": "Exporter Name",
    "exporter_address": "Exporter Address",
    "iec": "IEC",
    "gstin": "GSTIN",
    "buyer_name": "Buyer Name",
    "consignee_name": "Consignee Name",
    "notify_party": "Notify Party",
    "bank_details": "Bank Details",
    "invoice_number": "Invoice Number",
    "invoice_date": "Invoice Date",
    "po_number": "PO Number",
    "shipment_date": "Shipment Date",
    "bl_awb_number": "BL/AWB Number",
    "shipping_bill_number": "Shipping Bill Number",
    "container_number": "Container Number",
    "seal_number": "Seal Number",
    "vessel_flight_name": "Vessel / Flight Name",
    "port_of_loading": "Port of Loading",
    "port_of_discharge": "Port of Discharge",
    "final_destination": "Final Destination",
    "country_of_origin": "Country of Origin",
    "destination_country": "Destination Country",
    "hsn_code": "HSN / HS Code",
    "product_description": "Product Description",
    "grade_specification": "Grade / Specification",
    "item_count_size": "Item Count / Size",
    "quantity": "Quantity",
    "unit": "Unit",
    "net_weight": "Net Weight",
    "gross_weight": "Gross Weight",
    "number_of_packages": "Number of Packages",
    "package_type": "Package Type",
    "marks_and_numbers": "Marks and Numbers",
    "currency": "Currency",
    "unit_price": "Unit Price",
    "total_invoice_value": "Total Invoice Value",
    "fob_value": "FOB Value",
    "freight": "Freight",
    "insurance": "Insurance",
    "cif_value": "CIF Value",
    "incoterm": "Incoterm",
    "payment_terms": "Payment Terms",
    "rodtep_claim": "RoDTEP Claim",
    "duty_drawback_claim": "Duty Drawback Claim",
    "rosctl_claim": "RoSCTL Claim",
    "scheme_code": "Scheme Code",
    "incentive_hsn": "HSN Used For Incentive",
    "claim_fob_value": "FOB Value Used For Claim",
}

FIELD_ALIASES = {
    "hsn": "hsn_code",
    "hs_code": "hsn_code",
    "itc_hs": "hsn_code",
    "invoice_no": "invoice_number",
    "invoice_num": "invoice_number",
    "invoice_value": "total_invoice_value",
    "total_value": "total_invoice_value",
    "bl_number": "bl_awb_number",
    "awb_number": "bl_awb_number",
    "packages": "number_of_packages",
    "package_count": "number_of_packages",
}

EXACT_FIELDS = {
    "invoice_number",
    "hsn_code",
    "incentive_hsn",
    "iec",
    "gstin",
    "container_number",
    "seal_number",
    "bl_awb_number",
    "shipping_bill_number",
}

NUMERIC_FIELDS = {
    "quantity",
    "net_weight",
    "gross_weight",
    "number_of_packages",
    "unit_price",
    "total_invoice_value",
    "fob_value",
    "freight",
    "insurance",
    "cif_value",
    "claim_fob_value",
}

COMPARE_FIELDS = [
    "invoice_number",
    "hsn_code",
    "incentive_hsn",
    "product_description",
    "quantity",
    "unit",
    "net_weight",
    "gross_weight",
    "number_of_packages",
    "package_type",
    "currency",
    "total_invoice_value",
    "fob_value",
    "incoterm",
    "port_of_loading",
    "port_of_discharge",
    "country_of_origin",
    "destination_country",
    "container_number",
    "seal_number",
]

ALLOWED_EXTENSIONS = {"pdf", "xlsx", "csv", "jpg", "jpeg", "png"}
ALLOWED_MIME_PREFIXES = {"application/pdf", "image/"}
ALLOWED_MIME_EXACT = {
    "text/csv",
    "application/csv",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/octet-stream",
}


class DocumentVerifierError(RuntimeError):
    """Raised for expected verifier failures."""


@dataclass(slots=True)
class ExtractedFieldValue:
    field_key: str
    field_label: str
    raw_value: str | None
    normalized_value: str | None
    confidence_score: float = 0
    page_number: int | None = None
    table_reference: str | None = None
    evidence_excerpt: str | None = None


@dataclass(slots=True)
class DocumentExtractionResult:
    document_type: str = "unknown"
    fields: list[ExtractedFieldValue] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    parser_used: str = "heuristic"


def allowed_file(filename: str, mime_type: str | None) -> tuple[bool, str]:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    configured = {
        item.strip().lower()
        for item in get_settings().document_verifier_allowed_types.split(",")
        if item.strip()
    }
    allowed_extensions = configured or ALLOWED_EXTENSIONS
    if ext not in allowed_extensions:
        return False, ext
    mime = (mime_type or "").lower()
    if mime in ALLOWED_MIME_EXACT or any(mime.startswith(prefix) for prefix in ALLOWED_MIME_PREFIXES):
        return True, ext
    if not mime:
        return True, ext
    return False, ext


def max_file_bytes() -> int:
    return max(1, get_settings().document_verifier_max_file_mb) * 1024 * 1024


def storage_key(tenant_id: UUID, run_id: UUID, document_id: UUID, filename: str) -> str:
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", filename).strip("._") or "upload"
    return f"document-verifier/{tenant_id}/{run_id}/{document_id}/{safe_name}"


def extract_document_text(file_bytes: bytes, file_type: str) -> tuple[str, str]:
    if file_type == "pdf":
        import pdfplumber

        pages: list[str] = []
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for index, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                for table_index, table in enumerate(page.extract_tables() or [], start=1):
                    rows = ["\t".join(str(cell or "").strip() for cell in row) for row in table]
                    text += f"\n[TABLE {table_index}]\n" + "\n".join(rows)
                pages.append(f"--- PAGE {index} ---\n{text}")
        return "\n\n".join(pages), "pdfplumber"

    if file_type == "xlsx":
        import openpyxl

        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
        lines: list[str] = []
        for ws in wb.worksheets:
            lines.append(f"--- SHEET {ws.title} ---")
            for row in ws.iter_rows(values_only=True):
                cells = [str(cell).strip() if cell is not None else "" for cell in row]
                if any(cells):
                    lines.append("\t".join(cells))
        return "\n".join(lines), "openpyxl"

    if file_type == "csv":
        return file_bytes.decode("utf-8-sig", errors="replace"), "csv"

    if file_type in {"jpg", "jpeg", "png"}:
        return "", "image-no-ocr"

    raise DocumentVerifierError(f"Unsupported file type: {file_type}")


def _document_type_from_text(text: str, file_type: str) -> str:
    lower = text.lower()
    if not text and file_type in {"jpg", "jpeg", "png"}:
        return "unknown"
    if "shipping bill" in lower or "bill of export" in lower:
        return "shipping_bill"
    if "bill of lading" in lower:
        return "bill_of_lading"
    if "air waybill" in lower or "airway bill" in lower:
        return "airway_bill"
    if "certificate of origin" in lower:
        return "certificate_of_origin"
    if "phytosanitary" in lower:
        return "phytosanitary_certificate"
    if "fumigation" in lower:
        return "fumigation_certificate"
    if "insurance certificate" in lower:
        return "insurance_certificate"
    if "inspection certificate" in lower:
        return "inspection_certificate"
    if "letter of credit" in lower:
        return "letter_of_credit"
    if "purchase order" in lower or re.search(r"\bpo\s*(no|number)\b", lower):
        return "purchase_order"
    if "packing list" in lower and "invoice" in lower:
        return "invoice_packing_list"
    if "packing list" in lower:
        return "packing_list"
    if "proforma invoice" in lower:
        return "proforma_invoice"
    if "commercial invoice" in lower or "invoice" in lower:
        return "commercial_invoice"
    if "quote" in lower or "costing" in lower:
        return "export_quote"
    return "unknown"


def _first_match(text: str, patterns: list[str]) -> tuple[str, str] | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            value = next((g for g in match.groups() if g), "").strip(" :#\t\r\n")
            if value:
                start = max(0, match.start() - 80)
                end = min(len(text), match.end() + 80)
                return value, text[start:end].strip()
    return None


def _page_for_excerpt(text: str, excerpt: str | None) -> int | None:
    if not excerpt:
        return None
    index = text.find(excerpt[:40])
    if index < 0:
        return None
    prior = text[:index]
    pages = re.findall(r"--- PAGE (\d+) ---", prior)
    return int(pages[-1]) if pages else None


def _normalize(field_key: str, value: str | None) -> str | None:
    if value is None:
        return None
    clean = " ".join(str(value).strip().split())
    if not clean:
        return None
    if field_key in {"hsn_code", "incentive_hsn"}:
        digits = re.sub(r"\D+", "", clean)
        return digits or None
    if field_key in {"iec", "gstin", "invoice_number", "bl_awb_number", "shipping_bill_number", "container_number", "seal_number"}:
        return re.sub(r"\s+", "", clean).upper()
    if field_key in {"incoterm"}:
        incoterms = {"EXW", "FCA", "FAS", "FOB", "CFR", "CIF", "CPT", "CIP", "DAP", "DPU", "DDP"}
        upper = clean.upper()
        for term in incoterms:
            if term in upper:
                return term
        return upper[:3]
    if field_key in {"currency"}:
        upper = clean.upper()
        if "USD" in upper or "$" in upper:
            return "USD"
        if "EUR" in upper:
            return "EUR"
        if "INR" in upper or "RS" in upper:
            return "INR"
        return upper[:3]
    if field_key in NUMERIC_FIELDS:
        number = re.search(r"-?\d[\d,]*(?:\.\d+)?", clean)
        return number.group(0).replace(",", "") if number else None
    if field_key.endswith("date"):
        # Keep date normalization conservative; never invent a day/month.
        iso = re.search(r"\d{4}-\d{2}-\d{2}", clean)
        return iso.group(0) if iso else clean
    return clean.lower() if field_key in {"product_description", "package_type"} else clean.upper()


def _canonical_field_key(field_key: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", field_key.strip().lower()).strip("_")
    return FIELD_ALIASES.get(normalized, normalized)


FIELD_PATTERNS = {
    "invoice_number": [r"invoice\s*(?:no\.?|number|#)?\s*[:#-]\s*([A-Z0-9./-]+)"],
    "invoice_date": [r"invoice\s*date\s*[:#-]\s*([A-Z0-9,./ -]+)"],
    "po_number": [r"(?:po|purchase order)\s*(?:no\.?|number|#)?\s*[:#-]\s*([A-Z0-9./-]+)"],
    "shipping_bill_number": [r"shipping\s*bill\s*(?:no\.?|number|#)?\s*[:#-]\s*([A-Z0-9./-]+)"],
    "bl_awb_number": [r"(?:bl|b/l|awb|air waybill|airway bill)\s*(?:no\.?|number|#)?\s*[:#-]\s*([A-Z0-9./-]+)"],
    "container_number": [r"container\s*(?:no\.?|number|#)?\s*[:#-]\s*([A-Z]{3,4}\s*\d{6,7})"],
    "seal_number": [r"seal\s*(?:no\.?|number|#)?\s*[:#-]\s*([A-Z0-9./-]+)"],
    "iec": [r"\bIEC\s*(?:no\.?|number)?\s*[:#-]\s*([A-Z0-9]{8,12})"],
    "gstin": [r"\bGSTIN\s*[:#-]\s*([0-9A-Z]{15})"],
    "hsn_code": [r"\b(?:HSN|HS|ITC\s*HS)\s*(?:code)?\s*[:#-]?\s*([0-9]{4,10})"],
    "incentive_hsn": [r"(?:claim|scheme|rodtep|drawback)[^\n]{0,80}\b(?:HSN|HS)\s*(?:code)?\s*[:#-]?\s*([0-9]{4,10})"],
    "product_description": [r"(?:description of goods|product description|goods description)\s*[:#-]\s*([^\n]+)"],
    "quantity": [r"\bquantity\s*[:#-]\s*([0-9,.]+)\s*([A-Z]{2,5})?"],
    "unit": [r"\bquantity\s*[:#-]\s*[0-9,.]+\s*([A-Z]{2,5})"],
    "net_weight": [r"net\s*weight\s*[:#-]\s*([0-9,.]+)\s*(?:kg|kgs|mt)?"],
    "gross_weight": [r"gross\s*weight\s*[:#-]\s*([0-9,.]+)\s*(?:kg|kgs|mt)?"],
    "number_of_packages": [r"(?:number of packages|total packages|packages)\s*[:#-]\s*([0-9,.]+)"],
    "currency": [r"\bcurrency\s*[:#-]\s*([A-Z]{3})"],
    "total_invoice_value": [r"(?:total invoice value|invoice value|total amount)\s*[:#-]\s*([A-Z$ ]*\d[\d,.]*)"],
    "fob_value": [r"\bFOB\s*(?:value)?\s*[:#-]\s*([A-Z$ ]*\d[\d,.]*)"],
    "freight": [r"\bfreight\s*[:#-]\s*([A-Z$ ]*\d[\d,.]*)"],
    "insurance": [r"\binsurance\s*[:#-]\s*([A-Z$ ]*\d[\d,.]*)"],
    "cif_value": [r"\bCIF\s*(?:value)?\s*[:#-]\s*([A-Z$ ]*\d[\d,.]*)"],
    "incoterm": [r"\b(?:incoterm|terms of delivery)\s*[:#-]\s*([A-Z]{3})"],
    "port_of_loading": [r"port of loading\s*[:#-]\s*([^\n]+)"],
    "port_of_discharge": [r"port of discharge\s*[:#-]\s*([^\n]+)"],
    "country_of_origin": [r"country of origin\s*[:#-]\s*([^\n]+)"],
    "destination_country": [r"(?:destination country|country of final destination)\s*[:#-]\s*([^\n]+)"],
}


def _heuristic_extract(text: str, file_type: str) -> DocumentExtractionResult:
    document_type = _document_type_from_text(text, file_type)
    normalized_text = re.sub(r"([A-Za-z][A-Za-z0-9 /_.-]{1,80}):\s*[,	]\s*", r"\1: ", text)
    fields: list[ExtractedFieldValue] = []
    for field_key, patterns in FIELD_PATTERNS.items():
        field_key = _canonical_field_key(field_key)
        matched = _first_match(normalized_text, patterns)
        if matched:
            raw_value, excerpt = matched
            fields.append(
                ExtractedFieldValue(
                    field_key=field_key,
                    field_label=FIELD_LABELS.get(field_key, field_key.replace("_", " ").title()),
                    raw_value=raw_value,
                    normalized_value=_normalize(field_key, raw_value),
                    confidence_score=70,
                    page_number=_page_for_excerpt(normalized_text, excerpt),
                    evidence_excerpt=excerpt[:600],
                )
            )
    warnings = []
    if file_type in {"jpg", "jpeg", "png"}:
        warnings.append("Image OCR is not configured; manual verification is required.")
    return DocumentExtractionResult(
        document_type=document_type,
        fields=fields,
        warnings=warnings,
        parser_used="heuristic",
    )


_AI_SYSTEM = """You extract evidence from uploaded export shipment documents.

Use only the supplied document text. Do not infer values from memory.
Return strict JSON matching:
{
  "document_type": "commercial_invoice|proforma_invoice|packing_list|invoice_packing_list|shipping_bill|bill_of_lading|airway_bill|certificate_of_origin|insurance_certificate|phytosanitary_certificate|fumigation_certificate|inspection_certificate|purchase_order|letter_of_credit|export_quote|unknown",
  "fields": [
    {
      "field_key": "invoice_number",
      "field_label": "Invoice Number",
      "raw_value": "...",
      "normalized_value": "...",
      "confidence_score": 0.0,
      "page_number": 1,
      "table_reference": null,
      "evidence_excerpt": "..."
    }
  ],
  "warnings": []
}

Only include fields that are visibly supported by the text. Every field must include an evidence_excerpt.
Use null for page_number/table_reference when unknown. Return JSON only.
"""


def _resolve_provider() -> tuple[str, str, str | None, str] | None:
    settings = get_settings()
    choice = (settings.ai_provider or "auto").lower()
    candidates = {
        "groq": ("groq", settings.groq_api_key, "https://api.groq.com/openai/v1", settings.groq_model),
        "openai": ("openai", settings.openai_api_key, None, settings.openai_model),
        "xai": ("xai", settings.xai_api_key, settings.xai_base_url, settings.xai_model),
    }
    if choice in candidates:
        name, key, base, model = candidates[choice]
        return (name, key, base, model) if key is not None else None
    for name in ("groq", "openai", "xai"):
        provider_name, key, base, model = candidates[name]
        if key is not None:
            return provider_name, key, base, model
    return None


def _extract_json(text: str) -> dict[str, Any]:
    cleaned = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    match = re.search(r"\{[\s\S]*\}", cleaned)
    if not match:
        raise DocumentVerifierError("AI did not return JSON.")
    try:
        data = json.loads(match.group())
    except json.JSONDecodeError as error:
        raise DocumentVerifierError(f"AI returned malformed JSON: {error}") from error
    if not isinstance(data, dict):
        raise DocumentVerifierError("AI JSON response was not an object.")
    return data


def _chat_json(system: str, user: str) -> dict[str, Any]:
    provider = _resolve_provider()
    if provider is None:
        raise DocumentVerifierError("No AI provider configured.")
    _, api_key, base_url, model = provider
    openai_module: Any = importlib.import_module("openai")
    client = (
        openai_module.OpenAI(api_key=api_key, base_url=base_url)
        if base_url
        else openai_module.OpenAI(api_key=api_key)
    )
    completion = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.1,
        response_format={"type": "json_object"},
    )
    text = (completion.choices[0].message.content or "").strip()
    try:
        return _extract_json(text)
    except DocumentVerifierError as error:
        repair = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Repair malformed JSON. Return JSON only. Do not add facts."},
                {"role": "user", "content": f"Parse error: {error}\n\nInvalid response:\n{text[:12000]}"},
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )
        return _extract_json((repair.choices[0].message.content or "").strip())


def extract_fields_with_ai_or_parser(text: str, file_type: str) -> DocumentExtractionResult:
    if text.strip() and _resolve_provider() is not None:
        try:
            raw = _chat_json(_AI_SYSTEM, f"DOCUMENT TEXT:\n{text[:16000]}")
            fields = []
            for item in raw.get("fields") or []:
                field_key = _canonical_field_key(str(item.get("field_key") or ""))
                if not field_key:
                    continue
                raw_value = item.get("raw_value")
                normalized = item.get("normalized_value")
                if normalized is None:
                    normalized = _normalize(field_key, str(raw_value) if raw_value is not None else None)
                fields.append(
                    ExtractedFieldValue(
                        field_key=field_key,
                        field_label=str(item.get("field_label") or FIELD_LABELS.get(field_key) or field_key),
                        raw_value=str(raw_value) if raw_value is not None else None,
                        normalized_value=str(normalized) if normalized is not None else None,
                        confidence_score=float(item.get("confidence_score") or 0),
                        page_number=item.get("page_number"),
                        table_reference=item.get("table_reference"),
                        evidence_excerpt=item.get("evidence_excerpt"),
                    )
                )
            return DocumentExtractionResult(
                document_type=str(raw.get("document_type") or "unknown"),
                fields=fields,
                warnings=[str(w) for w in (raw.get("warnings") or [])],
                parser_used="ai_json",
            )
        except Exception:
            # Fall back to deterministic parsing; do not log document content.
            pass
    return _heuristic_extract(text, file_type)


def extract_document(session: Session, document: VerificationDocument) -> int:
    raw = storage.get(document.storage_key)
    text, parser = extract_document_text(raw, document.file_type)
    result = extract_fields_with_ai_or_parser(text, document.file_type)
    document.document_type = result.document_type
    document.parser_used = result.parser_used if result.parser_used != "heuristic" else parser
    document.extraction_status = "extracted"
    document.extraction_error = "; ".join(result.warnings) if result.warnings else None

    session.execute(delete(DocumentExtractedField).where(DocumentExtractedField.document_id == document.id))
    count = 0
    for extracted in result.fields:
        if extracted.raw_value is None and extracted.normalized_value is None:
            continue
        session.add(
            DocumentExtractedField(
                verification_run_id=document.verification_run_id,
                document_id=document.id,
                document_type=result.document_type,
                field_key=extracted.field_key,
                field_label=extracted.field_label,
                raw_value=extracted.raw_value,
                normalized_value=extracted.normalized_value,
                confidence_score=max(0, min(100, extracted.confidence_score)),
                page_number=extracted.page_number,
                table_reference=extracted.table_reference,
                evidence_excerpt=extracted.evidence_excerpt,
            )
        )
        count += 1
    return count


def _numeric(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return None


def _values_match(field_key: str, left: str | None, right: str | None, tolerance_percent: float = 1.0) -> bool:
    if not left or not right:
        return True
    if field_key in NUMERIC_FIELDS:
        left_num = _numeric(left)
        right_num = _numeric(right)
        if left_num is None or right_num is None:
            return left == right
        if left_num == right_num:
            return True
        basis = max(abs(left_num), abs(right_num), 1)
        return abs(left_num - right_num) / basis * 100 <= tolerance_percent
    if field_key in EXACT_FIELDS:
        return left == right
    return left.lower() == right.lower() or left.lower() in right.lower() or right.lower() in left.lower()


def _issue_severity(field_key: str, issue_type: str) -> str:
    if issue_type == "required_document_missing":
        return "high"
    if field_key in {"hsn_code", "incentive_hsn", "shipping_bill_number"}:
        return "high"
    if field_key in {"total_invoice_value", "fob_value", "claim_fob_value", "iec", "gstin"}:
        return "high"
    if field_key in {"invoice_number", "container_number", "seal_number", "bl_awb_number"}:
        return "medium"
    return "medium"


def _field_evidence(field: DocumentExtractedField) -> dict[str, Any]:
    return {
        "document_id": str(field.document_id),
        "document_type": field.document_type,
        "field_key": field.field_key,
        "raw_value": field.raw_value,
        "normalized_value": field.normalized_value,
        "page_number": field.page_number,
        "table_reference": field.table_reference,
        "evidence_excerpt": field.evidence_excerpt,
        "confidence_score": field.confidence_score,
    }


def _create_issue(
    *,
    run_id: UUID,
    issue_type: str,
    severity: str,
    title: str,
    description: str,
    field_key: str | None = None,
    expected_value: str | None = None,
    actual_values: list[dict[str, Any]] | None = None,
    related_document_ids: list[str] | None = None,
    evidence: list[dict[str, Any]] | None = None,
    confidence_score: float = 70,
) -> DocumentVerificationIssue:
    return DocumentVerificationIssue(
        verification_run_id=run_id,
        issue_type=issue_type,
        severity=severity,
        status="open",
        title=title,
        description=description,
        field_key=field_key,
        expected_value=expected_value,
        actual_values_json=actual_values or [],
        related_document_ids_json=related_document_ids or [],
        evidence_json=evidence or [],
        confidence_score=confidence_score,
    )


def _required_document_from_requirement(requirement: ComplianceRequirement) -> str | None:
    text = " ".join(
        str(part or "")
            for part in (
                requirement.requirement_type,
                requirement.requirement_text,
                getattr(requirement, "extracted_requirement", None),
                requirement.notes,
            )
        ).lower()
    if "phytosanitary" in text:
        return "phytosanitary_certificate"
    if "fumigation" in text:
        return "fumigation_certificate"
    if "certificate of origin" in text or "coo" in text:
        return "certificate_of_origin"
    if "inspection certificate" in text:
        return "inspection_certificate"
    if "insurance certificate" in text:
        return "insurance_certificate"
    return None


def _add_required_document_issues(
    session: Session,
    run: DocumentVerificationRun,
    uploaded_types: set[str],
) -> list[DocumentVerificationIssue]:
    if not run.destination_country:
        return []
    query = select(ComplianceRequirement).where(
        ComplianceRequirement.tenant_id == run.tenant_id,
        ComplianceRequirement.status == "active",
        ComplianceRequirement.review_status == "approved",
    )
    requirements = session.scalars(query).all()
    issues = []
    required_types: set[str] = set()
    for requirement in requirements:
        required = _required_document_from_requirement(requirement)
        if required:
            required_types.add(required)
    for required_type in sorted(required_types - uploaded_types):
        label = DOCUMENT_TYPE_LABELS.get(required_type, required_type)
        issues.append(
            _create_issue(
                run_id=run.id,
                issue_type="required_document_missing",
                severity="high",
                title=f"{label} missing",
                description=(
                    f"CCR/source-backed data indicates {label} may be required. "
                    "Upload it or mark this issue ignored only after manual verification."
                ),
                field_key="document_type",
                expected_value=required_type,
                confidence_score=65,
            )
        )
    return issues


def verify_run(session: Session, run: DocumentVerificationRun) -> DocumentVerificationReport:
    documents = session.scalars(
        select(VerificationDocument).where(VerificationDocument.verification_run_id == run.id)
    ).all()
    if not documents:
        raise DocumentVerifierError("Upload at least one document before verification.")
    if any(doc.extraction_status != "extracted" for doc in documents):
        raise DocumentVerifierError("All uploaded documents must be extracted before verification.")

    session.execute(delete(DocumentVerificationIssue).where(DocumentVerificationIssue.verification_run_id == run.id))
    session.execute(delete(DocumentVerificationReport).where(DocumentVerificationReport.verification_run_id == run.id))

    fields = session.scalars(
        select(DocumentExtractedField).where(DocumentExtractedField.verification_run_id == run.id)
    ).all()
    by_key: dict[str, list[DocumentExtractedField]] = {}
    for extracted_field in fields:
        if extracted_field.normalized_value:
            by_key.setdefault(extracted_field.field_key, []).append(extracted_field)

    issues: list[DocumentVerificationIssue] = []
    for field_key in COMPARE_FIELDS:
        candidates = by_key.get(field_key, [])
        if len(candidates) < 2:
            continue
        first = candidates[0]
        mismatches = [
            candidate
            for candidate in candidates[1:]
            if not _values_match(field_key, first.normalized_value, candidate.normalized_value)
        ]
        if mismatches:
            all_fields = [first, *mismatches]
            values = [
                {
                    "document_id": str(field.document_id),
                    "document_type": field.document_type,
                    "raw_value": field.raw_value,
                    "normalized_value": field.normalized_value,
                }
                for field in all_fields
            ]
            label = FIELD_LABELS.get(field_key, field_key.replace("_", " ").title())
            severity = _issue_severity(field_key, "mismatch")
            issues.append(
                _create_issue(
                    run_id=run.id,
                    issue_type="mismatch",
                    severity=severity,
                    title=f"{label} mismatch found",
                    description=(
                        f"{label} differs across uploaded documents. Review before filing or claiming."
                    ),
                    field_key=field_key,
                    actual_values=values,
                    related_document_ids=[str(field.document_id) for field in all_fields],
                    evidence=[_field_evidence(field) for field in all_fields],
                    confidence_score=min(field.confidence_score for field in all_fields),
                )
            )

    uploaded_types = {doc.document_type for doc in documents if doc.document_type}
    issues.extend(_add_required_document_issues(session, run, uploaded_types))

    for issue in issues:
        session.add(issue)

    counts = {
        "critical": sum(1 for issue in issues if issue.severity == "critical"),
        "high": sum(1 for issue in issues if issue.severity == "high"),
        "medium": sum(1 for issue in issues if issue.severity == "medium"),
        "low": sum(1 for issue in issues if issue.severity == "low"),
    }
    summary = {
        "verdict": "Review required" if issues else "Likely consistent",
        "warning": (
            "This audit is based on uploaded documents and source-backed KALYPTO data. "
            "Verify with your CHA/customs broker before filing."
        ),
        "documents_checked": len(documents),
        "fields_checked": len(fields),
        "open_issues": len(issues),
    }
    report = DocumentVerificationReport(
        verification_run_id=run.id,
        summary_json=summary,
        issues_count=len(issues),
        critical_count=counts["critical"],
        high_count=counts["high"],
        medium_count=counts["medium"],
        low_count=counts["low"],
    )
    session.add(report)
    run.status = "completed"
    run.completed_at = datetime.now(UTC)
    session.flush()
    return report


def generate_report_pdf(
    *,
    run: DocumentVerificationRun,
    documents: list[VerificationDocument],
    issues: list[DocumentVerificationIssue],
    report: DocumentVerificationReport,
) -> bytes:
    from reportlab.lib import colors  # type: ignore[import-untyped]
    from reportlab.lib.pagesizes import A4  # type: ignore[import-untyped]
    from reportlab.lib.styles import getSampleStyleSheet  # type: ignore[import-untyped]
    from reportlab.platypus import (  # type: ignore[import-untyped]
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, title="AI Document Verifier Report")
    styles = getSampleStyleSheet()
    story: list[Any] = [
        Paragraph("AI Document Verifier Report", styles["Title"]),
        Paragraph("Review required before filing or claiming.", styles["Normal"]),
        Spacer(1, 12),
        Paragraph(f"Run: {run.title}", styles["Heading2"]),
        Paragraph(f"Reference: {run.reference_number or 'Not provided'}", styles["Normal"]),
        Spacer(1, 12),
        Paragraph("Summary", styles["Heading2"]),
        Paragraph(json.dumps(report.summary_json, indent=2), styles["Code"]),
        Spacer(1, 12),
        Paragraph("Uploaded Documents", styles["Heading2"]),
    ]
    doc_rows = [["File", "Detected Type", "Status"]]
    for item in documents:
        doc_rows.append([item.file_name, item.document_type or "unknown", item.extraction_status])
    story.append(Table(doc_rows, hAlign="LEFT"))
    story.append(Spacer(1, 12))
    story.append(Paragraph("Issues", styles["Heading2"]))
    if issues:
        issue_rows = [["Severity", "Status", "Title"]]
        for issue in issues:
            issue_rows.append([issue.severity, issue.status, issue.title])
        table = Table(issue_rows, colWidths=[70, 70, 320], hAlign="LEFT")
        table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.25, colors.grey)]))
        story.append(table)
    else:
        story.append(Paragraph("No major mismatches found. Manual review is still recommended before filing.", styles["Normal"]))
    doc.build(story)
    return buffer.getvalue()
