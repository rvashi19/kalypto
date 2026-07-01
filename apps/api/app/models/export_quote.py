# ruff: noqa: E501
"""Saved Landed-Cost / Export-Quote calculations (tenant/user scoped)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import JSON, ForeignKey, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.base import TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin

_M = Numeric(16, 2)
_R = Numeric(12, 4)


class ExportQuoteCalculation(Base, UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin):
    __tablename__ = "export_quote_calculations"

    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    quote_number: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="saved")

    buyer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    buyer_country: Mapped[str | None] = mapped_column(String(120), nullable=True)
    seller_country: Mapped[str | None] = mapped_column(String(120), nullable=True)
    origin_city_or_place: Mapped[str | None] = mapped_column(String(160), nullable=True)
    port_of_loading: Mapped[str | None] = mapped_column(String(160), nullable=True)
    port_of_discharge: Mapped[str | None] = mapped_column(String(160), nullable=True)
    final_destination: Mapped[str | None] = mapped_column(String(160), nullable=True)
    incoterm: Mapped[str] = mapped_column(String(8), nullable=False)
    incoterms_version: Mapped[str] = mapped_column(String(12), nullable=False, default="2020")
    quote_currency: Mapped[str] = mapped_column(String(10), nullable=False, default="INR")

    hsn_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    product_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    packaging_description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    quantity: Mapped[float] = mapped_column(Numeric(16, 4), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(30), nullable=True)
    unit_price: Mapped[float] = mapped_column(_R, nullable=False)
    product_value: Mapped[float | None] = mapped_column(_M, nullable=True)
    target_profit_per_unit: Mapped[float | None] = mapped_column(_R, nullable=True)
    target_profit_total: Mapped[float | None] = mapped_column(_M, nullable=True)

    loading_charges: Mapped[float] = mapped_column(_M, nullable=False, default=0)
    local_transportation: Mapped[float] = mapped_column(_M, nullable=False, default=0)
    packaging_cost: Mapped[float] = mapped_column(_M, nullable=False, default=0)
    cfs_charges: Mapped[float] = mapped_column(_M, nullable=False, default=0)
    terminal_handling_charges: Mapped[float] = mapped_column(_M, nullable=False, default=0)
    customs_clearance_charges: Mapped[float] = mapped_column(_M, nullable=False, default=0)
    local_transit_charges: Mapped[float] = mapped_column(_M, nullable=False, default=0)
    seal_charges: Mapped[float] = mapped_column(_M, nullable=False, default=0)
    bill_of_lading_charges: Mapped[float] = mapped_column(_M, nullable=False, default=0)
    cha_charges: Mapped[float] = mapped_column(_M, nullable=False, default=0)
    phytosanitary_certificate_charges: Mapped[float] = mapped_column(_M, nullable=False, default=0)
    fumigation_charges: Mapped[float] = mapped_column(_M, nullable=False, default=0)
    vgm_charges: Mapped[float] = mapped_column(_M, nullable=False, default=0)
    misc_origin_charges: Mapped[float] = mapped_column(_M, nullable=False, default=0)
    ecgc_premium: Mapped[float] = mapped_column(_M, nullable=False, default=0)
    general_insurance: Mapped[float] = mapped_column(_M, nullable=False, default=0)
    bank_transaction_charges: Mapped[float] = mapped_column(_M, nullable=False, default=0)
    onsite_inspection_charges: Mapped[float] = mapped_column(_M, nullable=False, default=0)
    freight_cost: Mapped[float] = mapped_column(_M, nullable=False, default=0)
    destination_handling_charges: Mapped[float] = mapped_column(_M, nullable=False, default=0)

    import_duty_rate: Mapped[float] = mapped_column(_R, nullable=False, default=0)
    import_duty_amount: Mapped[float | None] = mapped_column(_M, nullable=True)
    destination_tax_rate: Mapped[float] = mapped_column(_R, nullable=False, default=0)
    destination_tax_amount: Mapped[float | None] = mapped_column(_M, nullable=True)
    other_destination_charges: Mapped[float] = mapped_column(_M, nullable=False, default=0)
    commission: Mapped[float] = mapped_column(_M, nullable=False, default=0)
    exporter_cost_of_goods: Mapped[float] = mapped_column(_M, nullable=False, default=0)
    exporter_overheads: Mapped[float] = mapped_column(_M, nullable=False, default=0)
    fx_rate_to_inr: Mapped[float | None] = mapped_column(_R, nullable=True)

    incentive_amount: Mapped[float] = mapped_column(_M, nullable=False, default=0)
    incentive_details_json: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)

    fob_value: Mapped[float] = mapped_column(_M, nullable=False, default=0)
    fob_per_unit: Mapped[float] = mapped_column(_R, nullable=False, default=0)
    cfr_value: Mapped[float] = mapped_column(_M, nullable=False, default=0)
    cfr_per_unit: Mapped[float] = mapped_column(_R, nullable=False, default=0)
    cif_value: Mapped[float] = mapped_column(_M, nullable=False, default=0)
    cif_per_unit: Mapped[float] = mapped_column(_R, nullable=False, default=0)
    total_landed_cost: Mapped[float] = mapped_column(_M, nullable=False, default=0)
    landed_cost_per_unit: Mapped[float] = mapped_column(_R, nullable=False, default=0)
    gross_exporter_realization: Mapped[float] = mapped_column(_M, nullable=False, default=0)
    net_exporter_realization: Mapped[float] = mapped_column(_M, nullable=False, default=0)
    net_realization_per_unit: Mapped[float] = mapped_column(_R, nullable=False, default=0)
    exporter_margin_amount: Mapped[float] = mapped_column(_M, nullable=False, default=0)
    exporter_margin_percent: Mapped[float] = mapped_column(_R, nullable=False, default=0)

    assumptions_json: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    warnings_json: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    calculation_version: Mapped[str] = mapped_column(String(40), nullable=False)
