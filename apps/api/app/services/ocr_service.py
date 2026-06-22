"""OCR and field extraction for uploaded shipment documents."""
from __future__ import annotations

import base64
import logging
from pathlib import Path

from app.services.groq_client import GroqClientError, call_groq

logger = logging.getLogger(__name__)

_FIELD_EXTRACT_SYSTEM = """You are an expert Indian export document reader.
Extract key fields from the raw text of a shipment document and return a JSON object.
Only include fields that are clearly present in the text. Return null for missing fields.

Return a JSON object with these fields (use null if absent):
{
  "document_number": null,
  "document_date": null,
  "buyer_name": null,
  "seller_name": null,
  "hsn_code": null,
  "product_description": null,
  "quantity": null,
  "unit_of_measure": null,
  "net_weight_kg": null,
  "gross_weight_kg": null,
  "fob_value": null,
  "cif_value": null,
  "currency": null,
  "incoterm": null,
  "payment_term": null,
  "port_of_loading": null,
  "port_of_discharge": null,
  "vessel_flight_no": null,
  "bl_awb_number": null,
  "shipping_bill_no": null,
  "igst_amount": null,
  "gstin": null,
  "iec_code": null,
  "marks_and_numbers": null
}

Return ONLY the JSON object. No markdown."""


def _extract_text_from_pdf(file_path: str) -> str:
    try:
        import pdfplumber  # noqa: PLC0415
    except ImportError:
        return ""
    text_parts: list[str] = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages[:10]:
            t = page.extract_text()
            if t:
                text_parts.append(t)
    return "\n".join(text_parts)


def _extract_text_from_image(file_path: str) -> str:
    """Use Groq vision to extract text from an image document."""
    from app.core.settings import get_settings  # noqa: PLC0415
    from groq import Groq  # noqa: PLC0415

    settings = get_settings()
    if not settings.groq_api_key:
        return ""

    with open(file_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")

    suffix = Path(file_path).suffix.lower()
    media_type_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
    media_type = media_type_map.get(suffix, "image/jpeg")

    client = Groq(api_key=settings.groq_api_key)
    try:
        completion = client.chat.completions.create(
            model="llama-3.2-11b-vision-preview",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{media_type};base64,{image_data}"},
                        },
                        {
                            "type": "text",
                            "text": "Extract all visible text from this export document. Return just the raw text content, preserving structure.",
                        },
                    ],
                }
            ],
            temperature=0.1,
        )
        return completion.choices[0].message.content or ""
    except Exception as e:
        logger.warning("Groq vision extraction failed: %s", e)
        return ""


def extract_fields(file_path: str, mime_type: str | None) -> dict:
    """Extract structured fields from a document file. Returns a dict of fields."""
    raw_text = ""

    if mime_type == "application/pdf":
        raw_text = _extract_text_from_pdf(file_path)
    elif mime_type in {"image/jpeg", "image/png", "image/webp"}:
        raw_text = _extract_text_from_image(file_path)
    elif mime_type in {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
    }:
        return {"_note": "Excel extraction not yet supported"}

    if not raw_text or len(raw_text.strip()) < 20:
        return {"_note": "Could not extract readable text from this document"}

    truncated = raw_text[:8000]

    try:
        fields = call_groq(
            system_prompt=_FIELD_EXTRACT_SYSTEM,
            user_message=f"Document text:\n{truncated}",
        )
        return {k: v for k, v in fields.items() if v is not None}
    except GroqClientError as e:
        logger.warning("Field extraction Groq call failed: %s", e)
        return {"_note": f"AI extraction failed: {e}"}
