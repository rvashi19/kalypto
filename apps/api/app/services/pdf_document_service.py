from __future__ import annotations

from io import BytesIO

from reportlab.lib import colors  # type: ignore[import-untyped]
from reportlab.lib.pagesizes import A4  # type: ignore[import-untyped]
from reportlab.lib.styles import getSampleStyleSheet  # type: ignore[import-untyped]
from reportlab.lib.units import mm  # type: ignore[import-untyped]
from reportlab.platypus import (  # type: ignore[import-untyped]
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.models import DocumentType, ExportShipment

SUPPORTED_GENERATED_DOCUMENTS = {
    DocumentType.PROFORMA_INVOICE,
    DocumentType.COMMERCIAL_INVOICE,
    DocumentType.PACKING_LIST,
}


def generate_shipment_pdf(shipment: ExportShipment, document_type: DocumentType) -> bytes:
    if document_type not in SUPPORTED_GENERATED_DOCUMENTS:
        raise ValueError(
            "Only proforma invoices, commercial invoices, and packing lists can be generated."
        )

    labels = {
        DocumentType.PROFORMA_INVOICE: "PROFORMA INVOICE",
        DocumentType.COMMERCIAL_INVOICE: "COMMERCIAL INVOICE",
        DocumentType.PACKING_LIST: "PACKING LIST",
    }
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=labels[document_type],
        author=shipment.exporter_name,
    )
    styles = getSampleStyleSheet()
    story = [
        Paragraph(labels[document_type], styles["Title"]),
        Spacer(1, 8 * mm),
        Paragraph(shipment.exporter_name, styles["Heading2"]),
        Spacer(1, 3 * mm),
    ]
    rows = [
        ["Product", shipment.product_name],
        ["HSN", shipment.hsn_code],
        ["Destination", shipment.destination_country],
        ["Buyer country", shipment.buyer_country],
        ["Incoterm", shipment.incoterm],
        ["Payment term", shipment.payment_term],
        ["Shipment mode", str(shipment.shipment_mode)],
        ["FOB value", f"{shipment.fob_value or 'Not provided'} {shipment.invoice_currency}"],
        ["Shipping bill", shipment.shipping_bill_no or "Not yet assigned"],
        ["Port of loading", shipment.port_of_loading or "Not provided"],
        [
            "Shipment date",
            shipment.shipment_date.date().isoformat() if shipment.shipment_date else "Not provided",
        ],
    ]
    table = Table(rows, colWidths=[45 * mm, 115 * mm], repeatRows=0)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#E2E8F0")),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#0F172A")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.extend(
        [
            table,
            Spacer(1, 10 * mm),
            Paragraph(
                "Draft generated from shipment data. Review all values and obtain authorized "
                "signatures before commercial or customs use.",
                styles["BodyText"],
            ),
        ]
    )
    document.build(story)
    return buffer.getvalue()
