"""Export quote calculations with tenant-scoped incentive evidence.

The calculator intentionally does not fetch duties or tax rates from models or scraped pages.
Destination duty is accepted only as a user-entered assumption.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import RateTable
from app.schemas.tools import (
    ExportQuoteIncentiveEstimate,
    ExportQuoteLineItem,
    ExportQuoteRequest,
    ExportQuoteResponse,
)

DISCLAIMER = (
    "Decision-support only. Destination duty is a user-entered assumption, and Indian incentive "
    "amounts use operator-seeded rate table records. Verify HSN, duties, incentives, and final "
    "documents with your CHA/customs broker before quoting or filing."
)


def _money(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _rate_rows_for_hsn(
    *, session: Session, tenant_id: UUID, hsn_code: str
) -> list[RateTable]:
    rows = session.scalars(
        select(RateTable)
        .where(RateTable.tenant_id == tenant_id)
        .order_by(RateTable.effective_date.desc())
    ).all()
    matching_rows = [row for row in rows if hsn_code.startswith(row.hsn)]

    latest_by_scheme: dict[str, RateTable] = {}
    for row in sorted(
        matching_rows,
        key=lambda item: (len(item.hsn), item.effective_date),
        reverse=True,
    ):
        latest_by_scheme.setdefault(row.scheme.strip().lower(), row)
    return list(latest_by_scheme.values())


def calculate_export_quote(
    *,
    session: Session,
    tenant_id: UUID,
    payload: ExportQuoteRequest,
) -> ExportQuoteResponse:
    fob = payload.fob_value
    freight = payload.freight_value
    insurance = payload.insurance_value
    destination_charges = payload.destination_charges_value
    cif = fob + freight + insurance
    commercial_total = cif + destination_charges

    estimated_destination_duty: Decimal | None = None
    if payload.destination_duty_percent is not None:
        estimated_destination_duty = (
            cif * payload.destination_duty_percent / Decimal("100")
        )
    buyer_landed_estimate = commercial_total + (estimated_destination_duty or Decimal("0"))

    warnings: list[str] = []
    if payload.destination_duty_percent is None:
        warnings.append(
            "Destination duty is not estimated unless you enter a broker-confirmed duty percent."
        )
    else:
        warnings.append(
            "Destination duty is user-entered and not an authoritative customs duty lookup."
        )

    exchange_rate = payload.exchange_rate_to_inr
    quote_currency = payload.quote_currency.upper()
    if quote_currency == "INR" and exchange_rate is None:
        exchange_rate = Decimal("1")
    if exchange_rate is None:
        warnings.append(
            "Add an exchange rate to estimate INR realization and incentive amounts."
        )

    fob_inr = fob * exchange_rate if exchange_rate is not None else None
    cif_inr = cif * exchange_rate if exchange_rate is not None else None

    rate_rows = _rate_rows_for_hsn(
        session=session,
        tenant_id=tenant_id,
        hsn_code=payload.hsn_code,
    )
    incentive_estimates: list[ExportQuoteIncentiveEstimate] = []
    if not rate_rows:
        warnings.append(
            "No tenant-verified incentive rate was found for this HSN. "
            "Import the current rate table before relying on incentives."
        )
    elif fob_inr is None:
        warnings.append(
            "Verified incentive rates exist, but INR incentive values need an exchange rate."
        )
    else:
        for row in rate_rows:
            incentive_estimates.append(
                ExportQuoteIncentiveEstimate(
                    scheme=row.scheme,
                    rate_percent=float(row.rate),
                    estimated_amount_inr=_money(fob_inr * Decimal(str(row.rate)) / Decimal("100")),
                    source=row.source,
                    version_stamp=row.version_stamp,
                    confidence=row.confidence,
                )
            )

    incentive_total = Decimal(
        str(sum(item.estimated_amount_inr for item in incentive_estimates))
    )
    exporter_net_realization = (
        fob_inr + incentive_total - payload.domestic_charges_inr
        if fob_inr is not None
        else None
    )

    line_items = [
        ExportQuoteLineItem(label="FOB value", amount=_money(fob), currency=quote_currency),
        ExportQuoteLineItem(label="Freight", amount=_money(freight), currency=quote_currency),
        ExportQuoteLineItem(label="Insurance", amount=_money(insurance), currency=quote_currency),
        ExportQuoteLineItem(
            label="Destination charges",
            amount=_money(destination_charges),
            currency=quote_currency,
            note="Buyer-side estimate if included in your quote.",
        ),
    ]
    if estimated_destination_duty is not None:
        line_items.append(
            ExportQuoteLineItem(
                label="Estimated destination duty",
                amount=_money(estimated_destination_duty),
                currency=quote_currency,
                note="User-entered duty percent, not auto-classified.",
            )
        )
    if payload.domestic_charges_inr:
        line_items.append(
            ExportQuoteLineItem(
                label="Domestic charges",
                amount=_money(payload.domestic_charges_inr),
                currency="INR",
                note="Deducted from exporter net realization.",
            )
        )

    return ExportQuoteResponse(
        product_name=payload.product_name,
        hsn_code=payload.hsn_code,
        destination_country=payload.destination_country,
        incoterm=payload.incoterm,
        quote_currency=quote_currency,
        fob_value=_money(fob),
        cif_value=_money(cif),
        commercial_quote_total=_money(commercial_total),
        estimated_destination_duty=(
            _money(estimated_destination_duty)
            if estimated_destination_duty is not None
            else None
        ),
        buyer_landed_estimate=_money(buyer_landed_estimate),
        exchange_rate_to_inr=float(exchange_rate) if exchange_rate is not None else None,
        fob_value_inr=_money(fob_inr) if fob_inr is not None else None,
        cif_value_inr=_money(cif_inr) if cif_inr is not None else None,
        exporter_net_realization_inr=(
            _money(exporter_net_realization)
            if exporter_net_realization is not None
            else None
        ),
        incentive_total_inr=_money(incentive_total),
        incentive_estimates=incentive_estimates,
        line_items=line_items,
        warnings=warnings,
        disclaimer=DISCLAIMER,
    )
