from datetime import UTC, datetime

from app.models import (
    DocumentType,
    ExportShipment,
    Organization,
    RateTable,
    ShipmentMode,
    ShipmentStage,
)
from app.services.hsn_rate_service import lookup_rates
from app.services.pdf_document_service import generate_shipment_pdf


def _shipment(tenant_id):
    return ExportShipment(
        tenant_id=tenant_id,
        exporter_name="Demo Exports",
        product_name="Cotton shirts",
        hsn_code="620520",
        destination_country="United Kingdom",
        buyer_country="United Kingdom",
        incoterm="FOB",
        payment_term="TT advance",
        shipment_mode=ShipmentMode.SEA,
        shipment_stage=ShipmentStage.PRE_SHIPMENT,
        fob_value=100000,
        invoice_currency="INR",
    )


def test_generated_commercial_invoice_is_a_pdf(session) -> None:
    organization = Organization(name="PDF Tenant", slug="pdf-tenant")
    session.add(organization)
    session.flush()

    pdf = generate_shipment_pdf(_shipment(organization.id), DocumentType.COMMERCIAL_INVOICE)

    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1000


def test_rate_lookup_is_tenant_scoped_and_source_backed(session) -> None:
    first = Organization(name="First", slug="rate-first")
    second = Organization(name="Second", slug="rate-second")
    session.add_all([first, second])
    session.flush()
    session.add(
        RateTable(
            tenant_id=first.id,
            scheme="RoDTEP",
            hsn="6205",
            rate=1.25,
            source="Operator uploaded notification",
            effective_date=datetime(2026, 1, 1, tzinfo=UTC),
            version_stamp="notification-v1",
            confidence="verified",
        )
    )
    session.commit()

    visible = lookup_rates(
        session=session,
        tenant_id=first.id,
        hsn_code="620520",
        fob_value=100000,
    )
    hidden = lookup_rates(
        session=session,
        tenant_id=second.id,
        hsn_code="620520",
        fob_value=100000,
    )

    assert visible["found"] is True
    assert visible["rodtep_rate"] == 1.25
    assert visible["rate_evidence"][0]["source"] == "Operator uploaded notification"
    assert hidden["found"] is False
