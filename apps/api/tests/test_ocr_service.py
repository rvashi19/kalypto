from pathlib import Path

import pytest
from openpyxl import Workbook

from app.services import ocr_service
from app.services.groq_client import GroqClientError
from app.services.ocr_service import extract_fields


def test_excel_upload_extracts_fields_without_ai(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Simulate "no AI" even when a developer's .env has a provider key.
    def no_ai(**_: object) -> dict[str, object]:
        raise GroqClientError("AI disabled in test")

    monkeypatch.setattr(ocr_service, "call_groq", no_ai)
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Invoice"
    worksheet.append(["Commercial Invoice"])
    worksheet.append(["Invoice No", "INV-2026-001"])
    worksheet.append(["Date", "2026-06-01"])
    worksheet.append(["Buyer", "Atlantic Foods LLC"])
    worksheet.append(["Exporter", "Demo Exports Pvt Ltd"])
    worksheet.append(["HSN Code", "090422"])
    worksheet.append(["FOB Value", "100000"])
    worksheet.append(["Currency", "USD"])
    worksheet.append(["Incoterm", "FOB"])
    worksheet.append(["AD Code", "1234567"])
    file_path = tmp_path / "invoice.xlsx"
    workbook.save(file_path)

    fields = extract_fields(
        str(file_path),
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    assert fields["invoice_number"] == "INV-2026-001"
    assert fields["hsn_code"] == "090422"
    assert fields["currency"] == "USD"
    assert fields["incoterm"] == "FOB"
    assert fields["ad_code"] == "1234567"
    assert fields["_extraction_method"] == "deterministic_text"
