# ruff: noqa: E501
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.services.compliance_normalization import (
    normalize_category,
    normalize_country,
    normalize_hsn,
    normalize_requirement_type,
)

ComplianceStatus = Literal[
    "answered", "insufficient_verified_data", "needs_review", "unsupported_scope"
]
ConfidenceLevel = Literal["High", "Medium", "Low"]
ReviewStatus = Literal["pending", "approved", "rejected"]
SourceChangeStatus = Literal["needs_review", "reviewed", "ignored"]


class ComplianceOptionsResponse(BaseModel):
    countries: list[str]
    categories: list[str]
    recommended_scraping_stack: list[str]
    knowledge_store_backend: str
    refresh_interval_days: int


class ComplianceCheckerRequest(BaseModel):
    product: str = Field(min_length=2, max_length=255)
    hsn_code: str | None = Field(default=None, max_length=20)
    destination_country: str = Field(min_length=2, max_length=120)
    category: str = Field(min_length=2, max_length=120)
    details: dict[str, str | int | float | bool | None] = Field(default_factory=dict)

    @field_validator("destination_country")
    @classmethod
    def normalize_request_country(cls, value: str) -> str:
        return normalize_country(value)

    @field_validator("category")
    @classmethod
    def normalize_request_category(cls, value: str) -> str:
        return normalize_category(value)

    @field_validator("hsn_code")
    @classmethod
    def validate_hsn(cls, value: str | None) -> str | None:
        return normalize_hsn(value)


class ProductSummary(BaseModel):
    product: str
    hsn: str | None
    destination: str
    category: str
    assumptions: list[str]


class ComplianceSourceReference(BaseModel):
    source_name: str
    source_url: str
    last_checked_date: str | None
    expires_at: str | None
    source_authority_level: str


class ComplianceCheckerSections(BaseModel):
    product_summary: ProductSummary
    required_import_documents: list[str]
    certificates_required: list[str]
    labeling_requirements: list[str]
    restriction_alerts: list[str]
    inspection_testing_requirements: list[str]
    buyer_side_questions: list[str]
    source_references: list[ComplianceSourceReference]


class ComplianceCheckerResponse(BaseModel):
    status: ComplianceStatus
    session_id: str | None = None
    answer: str
    follow_up_questions: list[str]
    sections: ComplianceCheckerSections
    confidence_level: ConfidenceLevel
    confidence_explanation: str
    last_checked_date: str | None
    unresolved_questions: list[str]
    disclaimer: str


class ComplianceRequirementInput(BaseModel):
    country: str = Field(min_length=2, max_length=120)
    category: str = Field(min_length=2, max_length=120)
    hsn_code: str | None = Field(default=None, max_length=20)
    product_keywords: list[str] = Field(default_factory=list, max_length=30)
    requirement_type: str = Field(min_length=2, max_length=80)
    requirement_text: str = Field(min_length=10, max_length=4000)
    extracted_requirement: str | None = Field(default=None, max_length=4000)
    source_url: str = Field(min_length=8, max_length=2048)
    source_name: str = Field(min_length=2, max_length=255)
    source_authority_level: Literal["official", "trade_body", "operator_seeded", "unknown"] = (
        "unknown"
    )
    effective_date: str | None = None
    last_checked_at: datetime | None = None
    expires_at: datetime | None = None
    confidence_score: float = Field(default=70, ge=0, le=100)
    status: Literal["draft", "active", "archived"] = "active"
    review_status: ReviewStatus = "approved"
    reviewed_by: str | None = Field(default=None, max_length=255)
    reviewed_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=2000)
    unresolved_questions: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("country")
    @classmethod
    def normalize_input_country(cls, value: str) -> str:
        return normalize_country(value)

    @field_validator("category")
    @classmethod
    def normalize_input_category(cls, value: str) -> str:
        return normalize_category(value)

    @field_validator("hsn_code")
    @classmethod
    def normalize_input_hsn(cls, value: str | None) -> str | None:
        return normalize_hsn(value)

    @field_validator("requirement_type")
    @classmethod
    def normalize_input_requirement_type(cls, value: str) -> str:
        return normalize_requirement_type(value)

    @model_validator(mode="after")
    def populate_extracted_requirement(self) -> ComplianceRequirementInput:
        if self.extracted_requirement is None:
            self.extracted_requirement = self.requirement_text
        return self


class ManualComplianceIngestRequest(BaseModel):
    records: list[ComplianceRequirementInput] = Field(min_length=1, max_length=250)


class ManualComplianceIngestResponse(BaseModel):
    created: int
    updated: int
    total: int


class ComplianceScrapeRunRequest(BaseModel):
    source_url: str = Field(min_length=8, max_length=2048)
    country: str = Field(min_length=2, max_length=120)
    category: str = Field(min_length=2, max_length=120)

    @field_validator("country")
    @classmethod
    def normalize_scrape_country(cls, value: str) -> str:
        return normalize_country(value)

    @field_validator("category")
    @classmethod
    def normalize_scrape_category(cls, value: str) -> str:
        return normalize_category(value)


class ComplianceScrapeRunResponse(BaseModel):
    run_id: str
    status: str
    records_found: int
    message: str


class DueComplianceSourceResponse(BaseModel):
    source_url: str
    country: str
    category: str
    last_checked_at: datetime | None


class ComplianceSourceSnapshotResponse(BaseModel):
    id: str
    source_url: str
    country: str
    category: str
    title: str
    content_hash: str
    previous_content_hash: str | None
    status: str
    scraped_at: datetime


class ComplianceSourceChangeResponse(BaseModel):
    id: str
    source_url: str
    country: str
    category: str
    previous_snapshot_id: str | None
    current_snapshot_id: str
    previous_content_hash: str | None
    current_content_hash: str
    status: str
    reviewed_by: str | None
    reviewed_at: datetime | None
    notes: str | None
    created_at: datetime


class ComplianceSourceChangeDetailResponse(ComplianceSourceChangeResponse):
    current_title: str
    current_scraped_at: datetime
    current_markdown_excerpt: str
    previous_title: str | None
    previous_scraped_at: datetime | None
    previous_markdown_excerpt: str | None
    excerpt_notice: str


class ComplianceCoverageCell(BaseModel):
    country: str
    category: str
    total_records: int
    approved_fresh_records: int
    pending_or_draft_records: int
    stale_records: int
    official_sources: int
    latest_checked_at: datetime | None
    status: Literal["verified", "partial", "needs_review", "empty"]


class ComplianceCoverageResponse(BaseModel):
    refresh_interval_days: int
    supported_countries: list[str]
    supported_categories: list[str]
    cells: list[ComplianceCoverageCell]
    due_sources_count: int
    source_changes_needing_review: int
    disclaimer: str


class SourceChangeReviewRequest(BaseModel):
    status: SourceChangeStatus
    notes: str | None = Field(default=None, max_length=2000)


# ── Country Compliance Checker v1 (check / retrieval jobs / review / sources) ──

class ComplianceCheckRequest(BaseModel):
    origin_country: str = Field(default="India", max_length=120)
    destination_country: str = Field(min_length=2, max_length=120)
    hsn_code: str | None = Field(default=None, max_length=20)
    product_description: str = Field(min_length=2, max_length=1000)
    product_category: str = Field(min_length=2, max_length=120)
    facts: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    start_retrieval: bool = Field(
        default=True,
        description="If no approved local answer exists, queue an official-source retrieval job.",
    )

    @field_validator("destination_country")
    @classmethod
    def _norm_dest(cls, v: str) -> str:
        return normalize_country(v)

    @field_validator("origin_country")
    @classmethod
    def _norm_origin(cls, v: str) -> str:
        return normalize_country(v)

    @field_validator("product_category")
    @classmethod
    def _norm_cat(cls, v: str) -> str:
        return normalize_category(v)

    @field_validator("hsn_code")
    @classmethod
    def _norm_hsn(cls, v: str | None) -> str | None:
        return normalize_hsn(v)


class ComplianceRequirementCard(BaseModel):
    requirement_type: str
    title: str
    detail: str
    mandatory_or_conditional: str | None = None
    source_name: str | None = None
    source_url: str | None = None
    last_checked_date: str | None = None
    confidence_label: ConfidenceLevel | None = None


class ComplianceCheckResponse(BaseModel):
    session_id: str
    # answered / needs_more_info / no_verified_source / retrieval_queued / pending_review
    status: str
    answer_summary: str
    requirements: dict[str, list[ComplianceRequirementCard]]
    missing_questions: list[str]
    buyer_questions: list[str]
    cha_questions: list[str]
    confidence_label: ConfidenceLevel
    confidence_score: float
    sources: list[ComplianceSourceReference]
    warnings: list[str]
    retrieval_job_id: str | None = None
    disclaimer: str


class ComplianceCheckSessionResponse(ComplianceCheckResponse):
    origin_country: str | None = None
    destination_country: str
    product_category: str
    hsn_code: str | None = None
    created_at: datetime


class RetrievalJobCreateRequest(BaseModel):
    origin_country: str = Field(default="India", max_length=120)
    destination_country: str = Field(min_length=2, max_length=120)
    product_category: str = Field(min_length=2, max_length=120)
    hsn_code: str | None = Field(default=None, max_length=20)
    product_description: str | None = Field(default=None, max_length=1000)

    @field_validator("destination_country")
    @classmethod
    def _norm_dest(cls, v: str) -> str:
        return normalize_country(v)

    @field_validator("product_category")
    @classmethod
    def _norm_cat(cls, v: str) -> str:
        return normalize_category(v)


class RetrievalJobResponse(BaseModel):
    id: str
    status: str
    destination_country: str
    product_category: str
    hsn_code: str | None
    pages_fetched: int
    snapshots_created: int
    requirements_extracted: int
    retry_count: int
    max_retries: int
    source_registry_ids: list[str]
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    message: str
    checksum_status: str | None = None
    parser_used: str | None = None
    pending_review_count: int = 0


class ReviewQueueItem(BaseModel):
    requirement_id: str
    country: str
    category: str
    hsn_code: str | None
    requirement_type: str
    title: str
    detail: str
    confidence_score: float
    review_status: str
    source_name: str
    source_url: str
    evidence_excerpts: list[str]
    created_at: datetime


class RequirementReviewRequest(BaseModel):
    notes: str | None = Field(default=None, max_length=2000)


class RequirementReviewResponse(BaseModel):
    requirement_id: str
    review_status: str
    status: str
    reviewed_by: str | None


class SourceRegistryCreateRequest(BaseModel):
    country: str = Field(min_length=2, max_length=120)
    authority_name: str = Field(min_length=2, max_length=255)
    source_name: str = Field(min_length=2, max_length=255)
    base_url: str = Field(min_length=8, max_length=2048)
    allowed_domains: list[str] = Field(default_factory=list, max_length=50)
    source_type: Literal["html", "pdf", "xlsx", "csv"] = "html"
    authority_level: Literal["official"] = "official"
    product_categories: list[str] = Field(default_factory=list, max_length=20)
    refresh_frequency_days: int = Field(default=30, ge=1, le=365)
    is_active: bool = True
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("country")
    @classmethod
    def _norm_country(cls, v: str) -> str:
        return normalize_country(v)


class SourceRegistryResponse(BaseModel):
    id: str
    country: str
    authority_name: str
    source_name: str
    base_url: str
    allowed_domains: list[str]
    source_type: str
    authority_level: str
    product_categories: list[str]
    is_active: bool
    refresh_frequency_days: int
    last_checked_at: datetime | None
    created_at: datetime
    notes: str | None
