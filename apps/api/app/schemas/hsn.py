from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

HSN_DISCLAIMER = (
    "HSN classification suggestions are source-backed but should be verified with a "
    "CHA/customs broker before filing customs/GST/export documents."
)


class HsnHierarchy(BaseModel):
    chapter_code: str | None = None
    heading_code: str | None = None
    subheading_code: str | None = None
    parent_code: str | None = None


class HsnEvidenceItem(BaseModel):
    source_name: str
    source_url: str | None = None
    evidence_type: str
    document_title: str | None = None
    document_date: datetime | None = None
    retrieved_at: datetime | None = None
    raw_text_excerpt: str | None = None
    confidence_weight: float | None = None


class HsnSearchItem(BaseModel):
    code: str
    normalized_code: str
    description: str
    digit_level: int
    hierarchy: HsnHierarchy
    confidence_score: float
    confidence_label: str
    match_reason: str
    source_evidence: list[HsnEvidenceItem] = Field(default_factory=list)
    warning_flags: list[str] = Field(default_factory=list)
    verification_recommended: bool = True


class HsnSearchResponse(BaseModel):
    query: str
    count: int
    results: list[HsnSearchItem]
    disclaimer: str = HSN_DISCLAIMER


class HsnDetailResponse(BaseModel):
    code: str
    normalized_code: str
    description: str
    digit_level: int
    hierarchy: HsnHierarchy
    unit_of_quantity: str | None = None
    section_name: str | None = None
    chapter_name: str | None = None
    import_policy: str | None = None
    export_policy: str | None = None
    policy_condition: str | None = None
    source_name: str
    source_url: str | None = None
    source_document_title: str | None = None
    source_document_date: datetime | None = None
    source_version: str | None = None
    is_active: bool
    source_evidence: list[HsnEvidenceItem] = Field(default_factory=list)
    incentive_rate_available: bool = False
    disclaimer: str = HSN_DISCLAIMER


class HsnImportError(BaseModel):
    row: int
    message: str


class HsnImportResponse(BaseModel):
    job_id: str
    status: str
    import_type: str
    source_name: str
    source_version: str | None = None
    checksum: str | None = None
    records_seen: int
    records_created: int
    records_updated: int
    records_deactivated: int
    error_message: str | None = None
    errors: list[HsnImportError] = Field(default_factory=list)


class HsnImportJobResponse(BaseModel):
    id: str
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


class HsnVerificationCreate(BaseModel):
    product_description: str = Field(min_length=2, max_length=4000)
    selected_hsn_code: str | None = Field(default=None, max_length=20)
    alternative_hsn_codes: list[str] = Field(default_factory=list)
    user_notes: str | None = Field(default=None, max_length=4000)


class HsnVerificationResponse(BaseModel):
    id: str
    product_description: str
    selected_hsn_code: str | None = None
    alternative_hsn_codes: list[str] = Field(default_factory=list)
    user_notes: str | None = None
    status: str
    reviewer_notes: str | None = None
    created_at: datetime
    disclaimer: str = HSN_DISCLAIMER


class HsnCodeAnnotateRequest(BaseModel):
    is_active: bool | None = None
    notes: str | None = Field(default=None, max_length=2000)


class HsnScrapeRequest(BaseModel):
    # "ogd" = data.gov.in REST API; "file" = direct official snapshot file URL.
    source: str = Field(pattern=r"^(ogd|file)$")
    source_version: str = Field(min_length=2, max_length=80)
    source_name: str | None = Field(default=None, max_length=255)
    # OGD connector
    resource_id: str | None = Field(default=None, max_length=120)
    api_key: str | None = Field(default=None, max_length=200)
    max_records: int | None = Field(default=None, ge=1, le=200000)
    # File connector
    url: str | None = Field(default=None, max_length=2048)
    import_type: str | None = Field(default=None, pattern=r"^(csv|xlsx|json)$")
    # Shared provenance
    source_document_title: str | None = Field(default=None, max_length=512)
    source_document_date: str | None = Field(default=None, max_length=40)
