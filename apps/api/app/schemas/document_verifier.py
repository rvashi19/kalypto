"""Schemas for the AI Document Verifier module."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class DocumentVerificationRunCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    reference_number: str | None = None
    shipment_id: UUID | None = None
    quote_id: UUID | None = None
    origin_country: str | None = None
    destination_country: str | None = None
    hsn_code: str | None = None
    product_description: str | None = None


class VerificationDocumentResponse(BaseModel):
    id: UUID
    verification_run_id: UUID
    file_name: str
    file_type: str
    mime_type: str | None
    document_type: str | None
    parser_used: str
    extraction_status: str
    extraction_error: str | None
    uploaded_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentExtractedFieldResponse(BaseModel):
    id: UUID
    verification_run_id: UUID
    document_id: UUID
    document_type: str
    field_key: str
    field_label: str
    raw_value: str | None
    normalized_value: str | None
    confidence_score: float
    page_number: int | None
    table_reference: str | None
    evidence_excerpt: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentVerificationIssueResponse(BaseModel):
    id: UUID
    verification_run_id: UUID
    issue_type: str
    severity: str
    status: str
    title: str
    description: str
    field_key: str | None
    expected_value: str | None
    actual_values_json: list[dict[str, Any]] | None
    related_document_ids_json: list[str] | None
    evidence_json: list[dict[str, Any]] | None
    confidence_score: float
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentVerificationReportResponse(BaseModel):
    id: UUID
    verification_run_id: UUID
    summary_json: dict[str, Any]
    issues_count: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    report_storage_key: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentVerificationRunResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    user_id: UUID | None
    shipment_id: UUID | None
    quote_id: UUID | None
    status: str
    title: str
    reference_number: str | None
    origin_country: str | None
    destination_country: str | None
    hsn_code: str | None
    product_description: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    documents: list[VerificationDocumentResponse] = Field(default_factory=list)
    fields: list[DocumentExtractedFieldResponse] = Field(default_factory=list)
    issues: list[DocumentVerificationIssueResponse] = Field(default_factory=list)
    report: DocumentVerificationReportResponse | None = None

    model_config = {"from_attributes": True}


class DocumentUploadResponse(BaseModel):
    documents: list[VerificationDocumentResponse]


class ExtractionRunResponse(BaseModel):
    run_id: UUID
    status: str
    documents_extracted: int
    fields_extracted: int
    failures: int
    message: str


class VerificationRunResponse(BaseModel):
    run_id: UUID
    status: str
    issues_count: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    message: str


class VerifierWarningResponse(BaseModel):
    warning: str = (
        "This audit is based on uploaded documents and source-backed KALYPTO data. "
        "Verify with your CHA/customs broker before filing."
    )
