from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models import DocumentType, DocumentUploadStatus, ShipmentMode, ShipmentStage


class ShipmentCreate(BaseModel):
    exporter_name: str = Field(min_length=2, max_length=255)
    product_name: str = Field(min_length=2, max_length=255)
    hsn_code: str = Field(min_length=4, max_length=20)
    destination_country: str = Field(min_length=2, max_length=120)
    buyer_country: str = Field(min_length=2, max_length=120)
    incoterm: str = Field(min_length=2, max_length=20)
    payment_term: str = Field(min_length=2, max_length=120)
    shipment_mode: ShipmentMode
    container_type: str | None = Field(default=None, max_length=80)
    shipment_stage: ShipmentStage
    fob_value: float | None = Field(default=None, gt=0)
    invoice_currency: str = Field(default="USD", max_length=10)
    shipping_bill_no: str | None = Field(default=None, max_length=120)
    port_of_loading: str | None = Field(default=None, max_length=120)
    shipment_date: datetime | None = None


class ShipmentUpdate(BaseModel):
    exporter_name: str | None = Field(default=None, max_length=255)
    product_name: str | None = Field(default=None, max_length=255)
    hsn_code: str | None = Field(default=None, max_length=20)
    destination_country: str | None = Field(default=None, max_length=120)
    buyer_country: str | None = Field(default=None, max_length=120)
    incoterm: str | None = Field(default=None, max_length=20)
    payment_term: str | None = Field(default=None, max_length=120)
    shipment_mode: ShipmentMode | None = None
    container_type: str | None = None
    shipment_stage: ShipmentStage | None = None
    fob_value: float | None = Field(default=None, gt=0)
    invoice_currency: str | None = Field(default=None, max_length=10)
    shipping_bill_no: str | None = Field(default=None, max_length=120)
    port_of_loading: str | None = Field(default=None, max_length=120)
    shipment_date: datetime | None = None


class ShipmentResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    exporter_name: str
    product_name: str
    hsn_code: str
    destination_country: str
    buyer_country: str
    incoterm: str
    payment_term: str
    shipment_mode: ShipmentMode
    container_type: str | None
    shipment_stage: ShipmentStage
    fob_value: float | None
    invoice_currency: str
    shipping_bill_no: str | None
    port_of_loading: str | None
    shipment_date: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentResponse(BaseModel):
    id: UUID
    shipment_id: UUID
    tenant_id: UUID
    document_type: DocumentType
    file_name: str
    file_size_bytes: int | None
    mime_type: str | None
    upload_status: DocumentUploadStatus
    extracted_fields: dict[str, Any] | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ChecklistItem(BaseModel):
    document_type: str
    label: str
    required: bool
    reason: str


class DocumentChecklist(BaseModel):
    required: list[ChecklistItem]
    optional: list[ChecklistItem]
    country_specific: list[ChecklistItem]
    bank_payment: list[ChecklistItem]
    incentive_refund: list[ChecklistItem]
    disclaimer: str


class DiscrepancyItem(BaseModel):
    field: str
    severity: str
    document_a: str
    document_b: str | None = None
    value_a: str
    value_b: str | None = None
    message: str
    suggested_fix: str


class IncentiveEstimate(BaseModel):
    scheme: str
    eligible: bool
    estimated_amount: float | None = None
    rate_percent: float | None = None
    notes: str = ""
    action_items: list[str] = Field(default_factory=list)

    @field_validator("eligible", mode="before")
    @classmethod
    def coerce_eligible(cls, v: object) -> bool:
        return False if v is None else bool(v)

    @field_validator("notes", mode="before")
    @classmethod
    def coerce_notes(cls, v: object) -> str:
        return "" if v is None else str(v)

    @field_validator("action_items", mode="before")
    @classmethod
    def coerce_action_items(cls, v: object) -> list[str]:
        if v is None:
            return []
        if isinstance(v, list):
            return [str(item) for item in v]
        return [str(v)]


class VerificationReport(BaseModel):
    shipment_id: UUID
    overall_risk: str
    missing_documents: list[str]
    discrepancies: list[DiscrepancyItem]
    incentive_estimates: list[IncentiveEstimate]
    ebrc_gst_reminders: list[str]
    finance_readiness_score: int
    finance_readiness_notes: str
    recommendations: list[str]
    disclaimer: str


class HsnRateLookupResponse(BaseModel):
    found: bool
    hsn_code: str
    hsn_prefix_matched: str | None = None
    description: str | None = None
    duty_drawback_rate: float | None = None
    rodtep_rate: float | None = None
    rosctl_rate: float | None = None
    notes: str | None = None
    estimated_amounts_inr: dict[str, float] | None = None
    fob_inr_basis: float | None = None
    exchange_rate_note: str | None = None
    message: str | None = None
