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
