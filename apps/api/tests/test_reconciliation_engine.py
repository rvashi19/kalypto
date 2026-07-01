from decimal import Decimal

from engine.reconciliation import ReconciliationInput, StructuredDocument, reconcile_shipment


def test_reconciliation_flags_missing_and_cross_document_mismatches() -> None:
    result = reconcile_shipment(
        ReconciliationInput(
            hsn_code="0902",
            buyer_country="Canada",
            incoterm="FOB",
            fob_value=Decimal("100000"),
            shipment_stage="post_shipment",
            shipping_bill_no=None,
            shipment_date=None,
            documents=[
                StructuredDocument(
                    document_type="commercial_invoice",
                    file_name="invoice.pdf",
                    fields={
                        "invoice_number": "INV-1",
                        "hsn_code": "0902",
                        "buyer_name": "Maple Buyer",
                        "fob_value": "100000",
                    },
                ),
                StructuredDocument(
                    document_type="packing_list",
                    file_name="packing.pdf",
                    fields={
                        "invoice_number": "INV-2",
                        "hsn_code": "0901",
                        "buyer_name": "Maple Buyer",
                        "fob_value": "100000",
                    },
                ),
            ],
        )
    )

    issue_types = {issue.type for issue in result.issues}
    assert "missing_document" in issue_types
    assert "invoice_number_mismatch" in issue_types
    assert "hsn_code_mismatch" in issue_types
    assert "shipment_hsn_mismatch" in issue_types
    assert "ad_code_missing" in issue_types


def test_reconciliation_uses_only_supplied_verified_rates() -> None:
    without_rates = reconcile_shipment(
        ReconciliationInput(
            hsn_code="0902",
            buyer_country="Canada",
            incoterm="FOB",
            fob_value=Decimal("100000"),
            shipment_stage="pre_shipment",
            shipping_bill_no=None,
            shipment_date=None,
            documents=[],
        )
    )
    with_rates = reconcile_shipment(
        ReconciliationInput(
            hsn_code="0902",
            buyer_country="Canada",
            incoterm="FOB",
            fob_value=Decimal("100000"),
            shipment_stage="pre_shipment",
            shipping_bill_no=None,
            shipment_date=None,
            documents=[],
            verified_rates={"RoDTEP": Decimal("1.25")},
        )
    )

    assert without_rates.potential_amount == 0
    assert with_rates.potential_amount == Decimal("1250.00")
    assert any(issue.type == "claim_status_unconfirmed" for issue in with_rates.issues)
