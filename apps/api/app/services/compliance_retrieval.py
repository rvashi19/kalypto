# ruff: noqa: E501
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ComplianceCountry, ComplianceRequirement, ProductCategory
from app.schemas.compliance import ComplianceRequirementInput
from app.services.compliance_normalization import (
    normalize_hsn,
    requirement_fingerprint,
    tokenize_keywords,
)


@dataclass(frozen=True, slots=True)
class StoredComplianceRequirement:
    id: str
    tenant_id: str
    country: str
    category: str
    hsn_code: str | None
    product_keywords: list[str]
    requirement_type: str
    requirement_text: str
    source_url: str
    source_name: str
    source_authority_level: str
    last_scraped_at: datetime
    confidence_score: float
    status: str
    content_hash: str


@dataclass(frozen=True, slots=True)
class RequirementMatch:
    requirement: StoredComplianceRequirement
    score: float


def stored_requirement_from_row(
    row: ComplianceRequirement,
    *,
    country: str | None = None,
    category: str | None = None,
) -> StoredComplianceRequirement:
    return StoredComplianceRequirement(
        id=str(row.id),
        tenant_id=str(row.tenant_id),
        country=country or "",
        category=category or "",
        hsn_code=row.hsn_code,
        product_keywords=list(row.product_keywords or []),
        requirement_type=row.requirement_type,
        requirement_text=row.requirement_text,
        source_url=row.source_url,
        source_name=row.source_name,
        source_authority_level=row.source_authority_level,
        last_scraped_at=row.last_scraped_at,
        confidence_score=float(row.confidence_score),
        status=row.status,
        content_hash=row.content_hash,
    )


class ComplianceDataWriter:
    def __init__(self, session: Session, tenant_id: UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    def ingest(self, records: list[ComplianceRequirementInput]) -> tuple[int, int]:
        created = 0
        updated = 0
        for record in records:
            _, was_created = self.upsert_requirement(record)
            if was_created:
                created += 1
            else:
                updated += 1
        return created, updated

    def upsert_requirement(
        self,
        record: ComplianceRequirementInput,
    ) -> tuple[StoredComplianceRequirement, bool]:
        country = self._get_or_create_country(record.country)
        category = self._get_or_create_category(record.category)
        normalized_hsn = normalize_hsn(record.hsn_code)
        content_hash = requirement_fingerprint(
            tenant_id=str(self.tenant_id),
            country=record.country,
            category=record.category,
            hsn_code=normalized_hsn,
            requirement_type=record.requirement_type,
            requirement_text=record.requirement_text,
            source_url=record.source_url,
        )
        existing = self.session.scalars(
            select(ComplianceRequirement).where(
                ComplianceRequirement.tenant_id == self.tenant_id,
                ComplianceRequirement.content_hash == content_hash,
            ),
        ).first()
        keywords = tokenize_keywords(record.product_keywords)
        if existing is not None:
            existing.product_keywords = keywords
            existing.last_scraped_at = datetime.now(UTC)
            existing.confidence_score = record.confidence_score
            existing.status = record.status
            self.session.add(existing)
            return stored_requirement_from_row(existing, country=country.name, category=category.name), False

        requirement = ComplianceRequirement(
            tenant_id=self.tenant_id,
            country_id=country.id,
            category_id=category.id,
            hsn_code=normalized_hsn,
            product_keywords=keywords,
            requirement_type=record.requirement_type,
            requirement_text=record.requirement_text.strip(),
            source_url=record.source_url.strip(),
            source_name=record.source_name.strip(),
            source_authority_level=record.source_authority_level,
            effective_date=None,
            last_scraped_at=datetime.now(UTC),
            confidence_score=record.confidence_score,
            status=record.status,
            content_hash=content_hash,
        )
        self.session.add(requirement)
        self.session.flush()
        return stored_requirement_from_row(requirement, country=country.name, category=category.name), True

    def _get_or_create_country(self, name: str) -> ComplianceCountry:
        country = self.session.scalars(
            select(ComplianceCountry).where(
                ComplianceCountry.tenant_id == self.tenant_id,
                ComplianceCountry.name == name,
            ),
        ).first()
        if country is not None:
            return country
        country = ComplianceCountry(tenant_id=self.tenant_id, name=name, region=None, is_active=True)
        self.session.add(country)
        self.session.flush()
        return country

    def _get_or_create_category(self, name: str) -> ProductCategory:
        category = self.session.scalars(
            select(ProductCategory).where(
                ProductCategory.tenant_id == self.tenant_id,
                ProductCategory.name == name,
            ),
        ).first()
        if category is not None:
            return category
        category = ProductCategory(
            tenant_id=self.tenant_id,
            name=name,
            description=f"Compliance data for {name}.",
            is_active=True,
        )
        self.session.add(category)
        self.session.flush()
        return category


class ComplianceRetriever:
    def __init__(self, session: Session, tenant_id: UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    def retrieve(
        self,
        *,
        product: str,
        hsn_code: str | None,
        destination_country: str,
        category: str,
        limit: int = 30,
    ) -> list[RequirementMatch]:
        country = self.session.scalars(
            select(ComplianceCountry).where(
                ComplianceCountry.tenant_id == self.tenant_id,
                ComplianceCountry.name == destination_country,
                ComplianceCountry.is_active.is_(True),
            ),
        ).first()
        category_row = self.session.scalars(
            select(ProductCategory).where(
                ProductCategory.tenant_id == self.tenant_id,
                ProductCategory.name == category,
                ProductCategory.is_active.is_(True),
            ),
        ).first()
        if country is None or category_row is None:
            return []

        requirements = self.session.scalars(
            select(ComplianceRequirement).where(
                ComplianceRequirement.tenant_id == self.tenant_id,
                ComplianceRequirement.country_id == country.id,
                ComplianceRequirement.category_id == category_row.id,
                ComplianceRequirement.status == "active",
            ),
        ).all()
        request_hsn = normalize_hsn(hsn_code)
        product_tokens = set(tokenize_keywords(product))
        matches: list[RequirementMatch] = []
        for requirement in requirements:
            hsn_score = self._hsn_score(request_hsn, requirement.hsn_code)
            keyword_score = self._keyword_score(product_tokens, requirement.product_keywords)
            if requirement.hsn_code and hsn_score == 0 and keyword_score == 0:
                continue
            score = float(requirement.confidence_score) + hsn_score + keyword_score
            stored = stored_requirement_from_row(
                requirement,
                country=country.name,
                category=category_row.name,
            )
            matches.append(RequirementMatch(requirement=stored, score=min(score, 100)))
        return sorted(matches, key=lambda match: match.score, reverse=True)[:limit]

    @staticmethod
    def _hsn_score(request_hsn: str | None, stored_hsn: str | None) -> float:
        if not stored_hsn:
            return 0
        if not request_hsn:
            return 0
        if request_hsn == stored_hsn:
            return 15
        if request_hsn.startswith(stored_hsn) or stored_hsn.startswith(request_hsn):
            return 8
        return 0

    @staticmethod
    def _keyword_score(product_tokens: set[str], stored_keywords: list[str]) -> float:
        if not stored_keywords:
            return 0
        overlap = product_tokens.intersection(stored_keywords)
        if not overlap:
            return 0
        return min(10, len(overlap) * 3)