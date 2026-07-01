# ruff: noqa: E501
"""Export-quote / landed-cost calculation engine (pure, deterministic).

Decision-support only: duty/tax/FX are user-entered; incentive rates come from the
Incentive Finder's approved records (never invented here). All monetary inputs are
treated as INR (the exporter's cost currency); the quote currency is used only to
express per-unit invoice values via the user's FX rate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

CALCULATION_VERSION = "export-quote-1.0"

# Charges that build up the FOB value (spec origin_charges formula).
_ORIGIN_FIELDS = (
    "loading_charges",
    "local_transportation",
    "packaging_cost",
    "cfs_charges",
    "terminal_handling_charges",
    "customs_clearance_charges",
    "local_transit_charges",
    "seal_charges",
    "bill_of_lading_charges",
    "cha_charges",
    "phytosanitary_certificate_charges",
    "fumigation_charges",
    "vgm_charges",
    "misc_origin_charges",
    "bank_transaction_charges",
    "onsite_inspection_charges",
)

_INVOICE_BASIS = {
    "EXW": "product_value",
    "FCA": "fob_value",
    "FAS": "fob_value",
    "FOB": "fob_value",
    "CFR": "cfr_value",
    "CPT": "cfr_value",
    "CIF": "cif_value",
    "CIP": "cif_value",
    "DAP": "delivered_value",
    "DPU": "delivered_value",
    "DDP": "ddp_value",
}


@dataclass
class ResolvedIncentive:
    scheme: str
    rate: float
    source: str  # approved_source_backed / user_provided
    cap_value: float | None = None
    cap_unit: str | None = None


@dataclass
class QuoteInputs:
    incoterm: str
    quote_currency: str
    quantity: float
    unit_price: float
    product_value: float | None = None
    fx_rate_to_inr: float | None = None
    include_incentives: bool = True
    hsn_code: str = ""
    # origin charges
    loading_charges: float = 0.0
    local_transportation: float = 0.0
    packaging_cost: float = 0.0
    cfs_charges: float = 0.0
    terminal_handling_charges: float = 0.0
    customs_clearance_charges: float = 0.0
    local_transit_charges: float = 0.0
    seal_charges: float = 0.0
    bill_of_lading_charges: float = 0.0
    cha_charges: float = 0.0
    phytosanitary_certificate_charges: float = 0.0
    fumigation_charges: float = 0.0
    vgm_charges: float = 0.0
    misc_origin_charges: float = 0.0
    bank_transaction_charges: float = 0.0
    onsite_inspection_charges: float = 0.0
    # freight / insurance
    freight_cost: float = 0.0
    general_insurance: float = 0.0
    ecgc_premium: float = 0.0
    # destination / landed
    destination_handling_charges: float = 0.0
    import_duty_rate: float = 0.0
    import_duty_amount: float | None = None
    destination_tax_rate: float = 0.0
    destination_tax_amount: float | None = None
    other_destination_charges: float = 0.0
    # exporter cost & profit
    commission: float = 0.0
    exporter_cost_of_goods: float = 0.0
    exporter_overheads: float = 0.0
    target_profit_per_unit: float | None = None
    target_profit_total: float | None = None
    incentives: list[ResolvedIncentive] = field(default_factory=list)


def _d(value: float | int | None) -> Decimal:
    return Decimal(str(value or 0))


def _money(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def calculate_quote(inputs: QuoteInputs) -> dict:
    warnings: list[str] = []
    assumptions: list[str] = [
        "All monetary inputs are treated as INR; per-unit invoice values are converted to the quote currency using the user FX rate.",
        "Incentives are applied as a percentage of FOB value (RoDTEP/Drawback/RoSCTL convention).",
    ]

    quantity = _d(inputs.quantity)
    if quantity <= 0:
        raise ValueError("Quantity must be greater than zero.")

    product_value = _d(inputs.product_value) if inputs.product_value else _d(inputs.unit_price) * quantity

    origin_breakdown = {name: _money(_d(getattr(inputs, name))) for name in _ORIGIN_FIELDS}
    origin_charges = sum((_d(getattr(inputs, name)) for name in _ORIGIN_FIELDS), Decimal("0"))

    fob_value = product_value + origin_charges
    cfr_value = fob_value + _d(inputs.freight_cost)
    cif_value = cfr_value + _d(inputs.general_insurance)

    # Buyer landed cost.
    duty_user_provided = inputs.import_duty_amount is not None
    import_duty = _d(inputs.import_duty_amount) if duty_user_provided else cif_value * _d(inputs.import_duty_rate) / _d(100)
    tax_base = cif_value + import_duty
    tax_user_provided = inputs.destination_tax_amount is not None
    destination_tax = _d(inputs.destination_tax_amount) if tax_user_provided else tax_base * _d(inputs.destination_tax_rate) / _d(100)
    total_landed_cost = (
        cif_value + import_duty + destination_tax + _d(inputs.destination_handling_charges) + _d(inputs.other_destination_charges)
    )

    # Invoice basis by incoterm.
    delivered_value = cif_value + _d(inputs.destination_handling_charges) + _d(inputs.other_destination_charges)
    ddp_value = delivered_value + import_duty + destination_tax
    basis_map = {
        "product_value": product_value,
        "fob_value": fob_value,
        "cfr_value": cfr_value,
        "cif_value": cif_value,
        "delivered_value": delivered_value,
        "ddp_value": ddp_value,
    }
    incoterm = (inputs.incoterm or "FOB").upper()
    invoice_value = basis_map[_INVOICE_BASIS.get(incoterm, "fob_value")]

    # Incentives (percentage of FOB, capped per unit if a cap is set).
    incentive_breakdown: list[dict] = []
    incentive_total = Decimal("0")
    if inputs.include_incentives:
        for inc in inputs.incentives:
            amount = fob_value * _d(inc.rate) / _d(100)
            cap_applied = False
            if inc.cap_value:
                cap_total = _d(inc.cap_value) * quantity
                if cap_total < amount:
                    amount = cap_total
                    cap_applied = True
            incentive_total += amount
            incentive_breakdown.append(
                {
                    "scheme": inc.scheme,
                    "rate_percent": inc.rate,
                    "source": inc.source,
                    "amount_inr": _money(amount),
                    "cap_applied": cap_applied,
                }
            )
        if not inputs.incentives:
            warnings.append("No approved incentive/rate data available for this HSN. Quote calculated without incentives.")
    if any(i.source == "user_provided" for i in inputs.incentives):
        warnings.append("Some incentive rates are user-provided and are not approved source-backed records.")

    # Exporter realization (INR).
    gross_realization = invoice_value
    net_realization = (
        gross_realization
        + incentive_total
        - _d(inputs.exporter_cost_of_goods)
        - _d(inputs.exporter_overheads)
        - _d(inputs.commission)
        - _d(inputs.ecgc_premium)
    )
    margin_amount = net_realization
    margin_percent = (net_realization / gross_realization * _d(100)) if gross_realization else Decimal("0")

    # Standing warnings.
    if duty_user_provided or inputs.import_duty_rate:
        warnings.append("Import duty/tax rates are user-provided and must be verified with the destination customs authority.")
    if incoterm == "DDP":
        warnings.append("DDP requires destination-country duty/tax confirmation.")
    if inputs.quote_currency.upper() != "INR" and not inputs.fx_rate_to_inr:
        warnings.append("Enter an FX rate to express invoice values in the quote currency.")
    warnings.append("Incoterms affect cost/risk responsibility but do not replace the sales contract.")
    warnings.append("This is an estimate, not legal/customs filing advice.")

    fx = _d(inputs.fx_rate_to_inr)

    def per_unit(value: Decimal) -> float:
        return _money(value / quantity)

    def in_quote_ccy(value: Decimal) -> float | None:
        if inputs.quote_currency.upper() == "INR":
            return _money(value)
        if fx and fx > 0:
            return _money(value / fx)
        return None

    return {
        "incoterm": incoterm,
        "quote_currency": inputs.quote_currency.upper(),
        "hsn_code": inputs.hsn_code,
        "product_value": _money(product_value),
        "origin_cost_breakdown": origin_breakdown,
        "total_origin_charges": _money(origin_charges),
        "fob_value": _money(fob_value),
        "fob_per_unit": per_unit(fob_value),
        "fob_per_unit_quote_ccy": in_quote_ccy(fob_value / quantity),
        "cfr_value": _money(cfr_value),
        "cfr_per_unit": per_unit(cfr_value),
        "cif_value": _money(cif_value),
        "cif_per_unit": per_unit(cif_value),
        "cif_per_unit_quote_ccy": in_quote_ccy(cif_value / quantity),
        "buyer_landed_cost_breakdown": {
            "cif_value": _money(cif_value),
            "import_duty_amount": _money(import_duty),
            "import_duty_user_provided": duty_user_provided,
            "destination_tax_amount": _money(destination_tax),
            "destination_tax_user_provided": tax_user_provided,
            "destination_handling_charges": _money(_d(inputs.destination_handling_charges)),
            "other_destination_charges": _money(_d(inputs.other_destination_charges)),
        },
        "import_duty_amount": _money(import_duty),
        "destination_tax_amount": _money(destination_tax),
        "total_landed_cost": _money(total_landed_cost),
        "landed_cost_per_unit": per_unit(total_landed_cost),
        "invoice_value": _money(invoice_value),
        "exporter_realization_breakdown": {
            "invoice_value": _money(invoice_value),
            "incentive_total": _money(incentive_total),
            "exporter_cost_of_goods": _money(_d(inputs.exporter_cost_of_goods)),
            "exporter_overheads": _money(_d(inputs.exporter_overheads)),
            "commission": _money(_d(inputs.commission)),
            "ecgc_premium": _money(_d(inputs.ecgc_premium)),
        },
        "gross_exporter_realization": _money(gross_realization),
        "incentive_breakdown": incentive_breakdown,
        "incentive_amount": _money(incentive_total),
        "net_exporter_realization": _money(net_realization),
        "net_realization_per_unit": per_unit(net_realization),
        "exporter_margin_amount": _money(margin_amount),
        "exporter_margin_percent": _money(margin_percent),
        "warnings": warnings,
        "assumptions": assumptions,
        "calculation_version": CALCULATION_VERSION,
    }
