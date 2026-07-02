"""Pydantic schemas for the Document Builder module."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


# ── Sub-object schemas ────────────────────────────────────────────────────────

class ExporterData(BaseModel):
    company_name: str
    address: str
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str = "India"
    iec: str | None = None
    gstin: str | None = None
    email: str | None = None
    phone: str | None = None
    bank_name: str | None = None
    bank_account: str | None = None
    ifsc_swift: str | None = None
    ad_code: str | None = None


class BuyerData(BaseModel):
    buyer_name: str
    buyer_address: str | None = None
    buyer_country: str
    consignee_name: str | None = None
    consignee_address: str | None = None
    notify_party: str | None = None


class ShipmentData(BaseModel):
    invoice_number: str | None = None
    invoice_date: str | None = None
    proforma_invoice_number: str | None = None
    proforma_invoice_date: str | None = None
    shipment_reference: str | None = None
    buyer_order_number: str | None = None
    purchase_order_number: str | None = None
    country_of_origin: str = "India"
    country_of_final_destination: str | None = None
    final_destination: str | None = None
    port_of_loading: str | None = None
    port_of_discharge: str | None = None
    incoterm: str | None = None
    incoterms_version: str = "Incoterms 2020"
    mode_of_transport: str = "Sea"
    currency: str | None = None
    payment_terms: str | None = None
    marks_and_numbers: str | None = None
    container_number: str | None = None
    seal_number: str | None = None
    vessel_flight_number: str | None = None
    expected_shipment_date: str | None = None
    validity: str | None = None


class ItemData(BaseModel):
    item_number: int | None = None
    product_description: str | None = None
    hsn_code: str | None = None
    quantity: float | None = None
    unit: str | None = None
    unit_price: float | None = None
    total_value: float | None = None
    net_weight: float | None = None
    gross_weight: float | None = None
    package_count: int | None = None
    package_type: str | None = None
    dimensions: str | None = None
    batch_lot_number: str | None = None
    country_of_origin: str | None = None
    row_index: int | None = None


class PackingData(BaseModel):
    total_packages: int | None = None
    package_type: str | None = None
    total_net_weight: float | None = None
    total_gross_weight: float | None = None
    total_volume: float | None = None
    freight: float | None = None
    insurance: float | None = None
    special_handling: str | None = None
    total_invoice_value: float | None = None


class DeclarationsData(BaseModel):
    authorized_signatory_name: str | None = None
    authorized_signatory_designation: str | None = None
    place_of_issue: str | None = None
    date_of_issue: str | None = None
    declaration_of_origin: str | None = None


class ShipmentPayload(BaseModel):
    exporter: ExporterData
    buyer: BuyerData
    shipment: ShipmentData
    items: list[ItemData] = Field(default_factory=list)
    packing: PackingData | None = None
    declarations: DeclarationsData | None = None


# ── Import session ────────────────────────────────────────────────────────────

class ImportSessionUploadResponse(BaseModel):
    session_id: UUID
    original_filename: str
    file_type: str
    sheet_names: list[str]
    detected_columns: list[str]
    suggested_mapping: dict[str, str]
    parsed_preview: list[dict[str, Any]]
    warnings: list[dict[str, str]]
    status: str


class MappingConfirmRequest(BaseModel):
    mapping: dict[str, str] = Field(..., description="raw_header -> canonical_field")
    sheet_name: str | None = None


class MappingConfirmResponse(BaseModel):
    session_id: UUID
    status: str
    parsed_items: list[dict[str, Any]]
    missing_fields: list[str]
    warnings: list[dict[str, str]]


# ── Validation ────────────────────────────────────────────────────────────────

class ValidationIssue(BaseModel):
    code: str
    message: str
    severity: str  # error | warning


class ValidateRequest(BaseModel):
    data: ShipmentPayload


class ValidateResponse(BaseModel):
    valid: bool
    errors: list[ValidationIssue]
    warnings: list[ValidationIssue]


# ── Document generation ───────────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    data: ShipmentPayload
    document_types: list[str] = Field(
        default_factory=lambda: list([
            "proforma_invoice",
            "commercial_invoice",
            "packing_list",
            "commercial_invoice_cum_packing_list",
            "shipping_instruction",
            "coo_application_data_sheet",
            "export_document_checklist",
        ])
    )
    save_pack: bool = True


class GeneratedDocumentMeta(BaseModel):
    document_type: str
    file_name: str
    file_size: int
    checksum: str


class GenerateResponse(BaseModel):
    pack_id: UUID | None = None
    documents: list[GeneratedDocumentMeta]
    validation_warnings: list[ValidationIssue]
    download_url: str | None = None


# ── Smart extraction ─────────────────────────────────────────────────────────

class ExtractResponse(BaseModel):
    """Returned by POST /documents/import/extract."""
    extracted: dict[str, Any]
    confidence: int = Field(ge=0, le=100)
    missing_fields: list[str]
    notes: str | None = None
    file_type: str
    used_llm: bool
    sheet_names: list[str] = Field(default_factory=list)


# ── Pack list & detail ────────────────────────────────────────────────────────

class PackSummary(BaseModel):
    id: UUID
    pack_number: str | None
    invoice_number: str | None
    buyer_name: str | None
    destination_country: str | None
    incoterm: str | None
    currency: str | None
    total_invoice_value: float | None
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PackDetail(PackSummary):
    shipment_data: dict[str, Any] | None = None
    validation_warnings: list[dict[str, Any]] | None = None
    generated_documents: list[dict[str, Any]] | None = None

    class Config:
        from_attributes = True
