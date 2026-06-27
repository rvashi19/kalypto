from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class ExportQuoteRequest(BaseModel):
    product_name: str = Field(min_length=2, max_length=255)
    hsn_code: str = Field(min_length=4, max_length=20)
    destination_country: str = Field(min_length=2, max_length=120)
    incoterm: str = Field(default="FOB", min_length=2, max_length=20)
    quote_currency: str = Field(default="USD", min_length=3, max_length=10)
    fob_value: Decimal = Field(gt=0, decimal_places=2)
    freight_value: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2)
    insurance_value: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2)
    destination_charges_value: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2)
    domestic_charges_inr: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2)
    destination_duty_percent: Decimal | None = Field(default=None, ge=0, le=200)
    exchange_rate_to_inr: Decimal | None = Field(default=None, gt=0, decimal_places=4)

    @field_validator("quote_currency", "incoterm", mode="before")
    @classmethod
    def normalize_uppercase(cls, value: object) -> str:
        return str(value).strip().upper()

    @field_validator("hsn_code", mode="before")
    @classmethod
    def normalize_hsn(cls, value: object) -> str:
        return "".join(character for character in str(value) if character.isdigit())


class ExportQuoteLineItem(BaseModel):
    label: str
    amount: float
    currency: str
    note: str | None = None


class ExportQuoteIncentiveEstimate(BaseModel):
    scheme: str
    rate_percent: float
    estimated_amount_inr: float
    source: str
    version_stamp: str
    confidence: str | None = None


class ExportQuoteResponse(BaseModel):
    product_name: str
    hsn_code: str
    destination_country: str
    incoterm: str
    quote_currency: str
    fob_value: float
    cif_value: float
    commercial_quote_total: float
    estimated_destination_duty: float | None
    buyer_landed_estimate: float
    exchange_rate_to_inr: float | None
    fob_value_inr: float | None
    cif_value_inr: float | None
    exporter_net_realization_inr: float | None
    incentive_total_inr: float
    incentive_estimates: list[ExportQuoteIncentiveEstimate]
    line_items: list[ExportQuoteLineItem]
    warnings: list[str]
    disclaimer: str
