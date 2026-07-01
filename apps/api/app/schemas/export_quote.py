# ruff: noqa: E501
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

CALC_DISCLAIMER = (
    "This is a decision-support estimate, not legal/customs filing advice. Verify HSN, duties, "
    "taxes, FX, and incentive eligibility before quoting or filing."
)
_INCOTERMS = ("EXW", "FCA", "FAS", "FOB", "CFR", "CIF", "CPT", "CIP", "DAP", "DPU", "DDP")


class UserIncentiveRate(BaseModel):
    scheme: str
    rate: float


class ExportQuoteRequest(BaseModel):
    # route & incoterm
    buyer_name: str | None = None
    buyer_country: str | None = None
    seller_country: str | None = None
    origin_city_or_place: str | None = None
    port_of_loading: str | None = None
    port_of_discharge: str | None = None
    final_destination: str | None = None
    incoterm: str = Field(default="FOB")
    incoterms_version: str = Field(default="2020")
    quote_currency: str = Field(default="INR", max_length=10)
    # product & hsn
    hsn_code: str | None = None
    product_description: str | None = None
    packaging_description: str | None = None
    quantity: float = Field(gt=0)
    unit: str | None = None
    unit_price: float = Field(ge=0)
    product_value: float | None = None
    target_profit_per_unit: float | None = None
    target_profit_total: float | None = None
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
    ecgc_premium: float = 0.0
    general_insurance: float = 0.0
    bank_transaction_charges: float = 0.0
    onsite_inspection_charges: float = 0.0
    freight_cost: float = 0.0
    destination_handling_charges: float = 0.0
    # destination / landed
    import_duty_rate: float = 0.0
    import_duty_amount: float | None = None
    destination_tax_rate: float = 0.0
    destination_tax_amount: float | None = None
    other_destination_charges: float = 0.0
    # exporter cost & profit
    commission: float = 0.0
    exporter_cost_of_goods: float = 0.0
    exporter_overheads: float = 0.0
    fx_rate_to_inr: float | None = None
    # incentives
    include_incentives: bool = True
    incentive_scheme_rates: list[UserIncentiveRate] | None = None
    export_date: datetime | None = None
    notes: str | None = None

    def normalized_incoterm(self) -> str:
        term = (self.incoterm or "FOB").upper()
        return term if term in _INCOTERMS else "FOB"


class ExportQuoteCalculateResponse(BaseModel):
    input_summary: dict[str, Any]
    incoterm: str
    incoterms_version: str
    named_place_summary: str
    hsn_code: str | None = None
    product_value: float
    origin_cost_breakdown: dict[str, float]
    total_origin_charges: float
    fob_value: float
    fob_per_unit: float
    fob_per_unit_quote_ccy: float | None = None
    cfr_value: float
    cfr_per_unit: float
    cif_value: float
    cif_per_unit: float
    cif_per_unit_quote_ccy: float | None = None
    buyer_landed_cost_breakdown: dict[str, Any]
    import_duty_amount: float
    destination_tax_amount: float
    total_landed_cost: float
    landed_cost_per_unit: float
    invoice_value: float
    exporter_realization_breakdown: dict[str, Any]
    gross_exporter_realization: float
    incentive_breakdown: list[dict[str, Any]]
    incentive_amount: float
    net_exporter_realization: float
    net_realization_per_unit: float
    exporter_margin_amount: float
    exporter_margin_percent: float
    warnings: list[str]
    assumptions: list[str]
    calculation_version: str
    quote_currency: str
    disclaimer: str = CALC_DISCLAIMER


class ExportQuoteSaveRequest(ExportQuoteRequest):
    quote_number: str | None = None
    status: str = "saved"


class ExportQuoteListItem(BaseModel):
    id: str
    quote_number: str | None = None
    buyer_name: str | None = None
    buyer_country: str | None = None
    incoterm: str
    hsn_code: str | None = None
    quote_currency: str
    fob_value: float
    cif_value: float
    net_exporter_realization: float
    exporter_margin_percent: float
    status: str
    created_at: datetime


class ExportQuoteDetailResponse(ExportQuoteListItem):
    calculation: ExportQuoteCalculateResponse
    notes: str | None = None
