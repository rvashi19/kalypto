from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

INCENTIVE_DISCLAIMER = (
    "Incentive/rate information is source-backed but should be verified before filing "
    "export documents or claiming benefits."
)


class IncentiveEvidenceItem(BaseModel):
    source_name: str
    source_url: str | None = None
    document_title: str | None = None
    document_date: datetime | None = None
    raw_text_excerpt: str | None = None
    retrieved_at: datetime | None = None
    evidence_type: str
    confidence_weight: float | None = None


class IncentiveRateItem(BaseModel):
    id: str
    scheme: str
    hsn_code: str
    normalized_hsn_code: str
    digit_level: int
    product_description: str | None = None
    rate_type: str
    rate_value: float
    cap_value: float | None = None
    cap_unit: str | None = None
    unit_of_quantity: str | None = None
    condition_text: str | None = None
    effective_from: datetime
    effective_to: datetime | None = None
    source_name: str
    source_url: str | None = None
    source_document_title: str | None = None
    source_document_date: datetime | None = None
    source_version: str | None = None
    approval_status: str
    verified_by: str | None = None
    verified_at: datetime | None = None
    is_active: bool
    review_note: str | None = None
    match_level: str  # exact / prefix
    source_evidence_count: int = 0


class IncentiveSearchResponse(BaseModel):
    hsn_code: str
    normalized_hsn_code: str
    digit_level: int | None = None
    hsn_exists: bool = False
    count: int
    schemes_present: list[str] = Field(default_factory=list)
    results: list[IncentiveRateItem] = Field(default_factory=list)
    message: str | None = None
    disclaimer: str = INCENTIVE_DISCLAIMER


class IncentiveDetailResponse(IncentiveRateItem):
    source_evidence: list[IncentiveEvidenceItem] = Field(default_factory=list)
    disclaimer: str = INCENTIVE_DISCLAIMER


class IncentiveSourceCreate(BaseModel):
    source_name: str = Field(min_length=2, max_length=255)
    scheme: str | None = Field(default=None, max_length=40)
    source_url: str | None = Field(default=None, max_length=2048)
    source_document_title: str | None = Field(default=None, max_length=512)
    source_type: str = Field(default="csv", pattern=r"^(csv|xlsx|pdf|json)$")
    refresh_interval_days: int | None = Field(default=None, ge=1, le=365)


class IncentiveSourceResponse(BaseModel):
    id: str
    scheme: str | None = None
    source_name: str
    source_url: str | None = None
    source_document_title: str | None = None
    source_type: str
    refresh_interval_days: int | None = None
    last_fetched_at: datetime | None = None
    last_source_version: str | None = None
    last_status: str
    last_records: int
    is_active: bool
    due_for_refresh: bool = False
    created_at: datetime


class IncentiveRefreshResponse(BaseModel):
    source_id: str
    status: str
    message: str
    records_seen: int = 0
    records_created: int = 0
    records_updated: int = 0


class IncentiveAnomalyResponse(BaseModel):
    checked: int
    flagged: int
    model: str | None = None


class IncentiveBulkApproveRequest(BaseModel):
    source_id: str | None = None


class IncentiveBulkApproveResponse(BaseModel):
    approved: int


class IncentiveImportError(BaseModel):
    row: int
    message: str


class IncentiveImportResponse(BaseModel):
    job_id: str
    status: str
    scheme: str | None = None
    source_name: str
    import_type: str
    checksum: str | None = None
    records_seen: int
    records_created: int
    records_updated: int
    records_deactivated: int
    error_message: str | None = None
    errors: list[IncentiveImportError] = Field(default_factory=list)


class IncentiveImportJobResponse(BaseModel):
    id: str
    scheme: str | None = None
    source_name: str
    source_url: str | None = None
    import_type: str
    status: str
    records_seen: int
    records_created: int
    records_updated: int
    records_deactivated: int
    error_message: str | None = None
    checksum: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_by: str | None = None
    created_at: datetime
