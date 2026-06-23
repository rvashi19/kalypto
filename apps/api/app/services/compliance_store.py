# ruff: noqa: E501
from __future__ import annotations

import importlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.models import ComplianceCountry, ComplianceRequirement, ProductCategory
from app.schemas.compliance import ComplianceRequirementInput
from app.services.compliance_freshness import calculate_expires_at, is_stale
from app.services.compliance_normalization import (
    normalize_hsn,
    requirement_fingerprint,
    source_snapshot_fingerprint,
    tokenize_keywords,
)
from app.services.compliance_retrieval import (
    ComplianceDataWriter,
    ComplianceRetriever,
    EvidenceReviewContext,
    RequirementMatch,
    StoredComplianceRequirement,
)


class ComplianceStoreConfigurationError(RuntimeError):
    """Raised when the configured compliance knowledge store is unavailable."""


@dataclass(frozen=True, slots=True)
class SourceSnapshotResult:
    source_url: str
    title: str
    content_hash: str
    previous_content_hash: str | None
    status: str
    message: str


@dataclass(frozen=True, slots=True)
class DueComplianceSource:
    source_url: str
    country: str
    category: str
    last_checked_at: datetime | None


class ComplianceKnowledgeStore(Protocol):
    def ingest(self, records: list[ComplianceRequirementInput]) -> tuple[int, int]: ...

    def retrieve(
        self,
        *,
        product: str,
        hsn_code: str | None,
        destination_country: str,
        category: str,
        limit: int = 30,
    ) -> list[RequirementMatch]: ...

    def review_context(
        self, *, destination_country: str, category: str
    ) -> EvidenceReviewContext: ...

    def record_source_snapshot(
        self,
        *,
        source_url: str,
        country: str,
        category: str,
        title: str,
        markdown: str,
    ) -> SourceSnapshotResult: ...

    def due_sources(self, *, limit: int = 25) -> list[DueComplianceSource]: ...


class PostgresComplianceKnowledgeStore:
    def __init__(self, session: Session, tenant_id: UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.writer = ComplianceDataWriter(session=session, tenant_id=tenant_id)
        self.retriever = ComplianceRetriever(session=session, tenant_id=tenant_id)

    def ingest(self, records: list[ComplianceRequirementInput]) -> tuple[int, int]:
        return self.writer.ingest(records)

    def retrieve(
        self,
        *,
        product: str,
        hsn_code: str | None,
        destination_country: str,
        category: str,
        limit: int = 30,
    ) -> list[RequirementMatch]:
        return self.retriever.retrieve(
            product=product,
            hsn_code=hsn_code,
            destination_country=destination_country,
            category=category,
            limit=limit,
        )

    def review_context(self, *, destination_country: str, category: str) -> EvidenceReviewContext:
        return self.retriever.review_context(
            destination_country=destination_country, category=category
        )

    def record_source_snapshot(
        self,
        *,
        source_url: str,
        country: str,
        category: str,
        title: str,
        markdown: str,
    ) -> SourceSnapshotResult:
        content_hash = source_snapshot_fingerprint(
            source_url=source_url, title=title, markdown=markdown
        )
        return SourceSnapshotResult(
            source_url=source_url,
            title=title,
            content_hash=content_hash,
            previous_content_hash=None,
            status="needs_review",
            message=(
                f"source={source_url} content_hash={content_hash} changed=unknown "
                "pending_review_created=true. Persistent snapshot diffing requires MongoDB."
            ),
        )

    def due_sources(self, *, limit: int = 25) -> list[DueComplianceSource]:
        rows = self.session.execute(
            select(ComplianceRequirement, ComplianceCountry, ProductCategory)
            .join(ComplianceCountry, ComplianceRequirement.country_id == ComplianceCountry.id)
            .join(ProductCategory, ComplianceRequirement.category_id == ProductCategory.id)
            .where(
                ComplianceRequirement.tenant_id == self.tenant_id,
                ComplianceRequirement.status == "active",
                ComplianceRequirement.review_status == "approved",
            ),
        ).all()
        seen: set[str] = set()
        due: list[DueComplianceSource] = []
        for requirement, country, category in rows:
            if requirement.source_url in seen:
                continue
            seen.add(requirement.source_url)
            due.append(
                DueComplianceSource(
                    source_url=requirement.source_url,
                    country=country.name,
                    category=category.name,
                    last_checked_at=requirement.last_checked_at,
                ),
            )
            if len(due) >= limit:
                break
        return due


class MongoComplianceKnowledgeStore:
    def __init__(self, tenant_id: UUID, database: Any | None = None) -> None:
        self.settings = get_settings()
        self.tenant_id = tenant_id
        if database is None:
            if not self.settings.mongodb_url:
                raise ComplianceStoreConfigurationError(
                    "MONGODB_URL is required when COMPLIANCE_STORE_BACKEND=mongo.",
                )
            pymongo_module: Any = importlib.import_module("pymongo")
            client = pymongo_module.MongoClient(
                self.settings.mongodb_url,
                serverSelectionTimeoutMS=5000,
            )
            database = client[self.settings.mongodb_database]
        self.database = database
        self.requirements = database[self.settings.mongodb_requirements_collection]
        self.source_snapshots = database[self.settings.mongodb_source_snapshots_collection]
        self.source_changes = database[self.settings.mongodb_source_changes_collection]
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        self.requirements.create_index(
            [("tenant_id", 1), ("content_hash", 1)],
            unique=True,
            name="uq_tenant_requirement_hash",
        )
        self.requirements.create_index(
            [
                ("tenant_id", 1),
                ("country", 1),
                ("category", 1),
                ("status", 1),
                ("review_status", 1),
            ],
            name="ix_tenant_country_category_status_review",
        )
        self.requirements.create_index(
            [("tenant_id", 1), ("hsn_code", 1)],
            name="ix_tenant_hsn",
        )
        self.source_snapshots.create_index(
            [("tenant_id", 1), ("source_url", 1), ("scraped_at", -1)],
            name="ix_tenant_source_scraped_at",
        )
        self.source_changes.create_index(
            [("tenant_id", 1), ("source_url", 1), ("status", 1)],
            name="ix_tenant_source_change_status",
        )

    def ingest(self, records: list[ComplianceRequirementInput]) -> tuple[int, int]:
        created = 0
        updated = 0
        now = datetime.now(UTC)
        for record in records:
            document = self._record_to_document(record, now=now)
            filter_query = {
                "tenant_id": str(self.tenant_id),
                "content_hash": document["content_hash"],
            }
            existing = self.requirements.find_one(filter_query)
            if existing:
                document["_id"] = existing["_id"]
                document["created_at"] = existing.get("created_at", now)
                updated += 1
            else:
                document["_id"] = str(uuid4())
                document["created_at"] = now
                created += 1
            document["updated_at"] = now
            self.requirements.replace_one(filter_query, document, upsert=True)
        return created, updated

    def retrieve(
        self,
        *,
        product: str,
        hsn_code: str | None,
        destination_country: str,
        category: str,
        limit: int = 30,
    ) -> list[RequirementMatch]:
        request_hsn = normalize_hsn(hsn_code)
        product_tokens = set(tokenize_keywords(product))
        documents = self.requirements.find(
            {
                "tenant_id": str(self.tenant_id),
                "country": destination_country,
                "category": category,
                "status": "active",
                "review_status": "approved",
            },
        )
        matches: list[RequirementMatch] = []
        for document in documents:
            if is_stale(expires_at=document.get("expires_at")):
                continue
            stored_hsn = document.get("hsn_code")
            stored_keywords = list(document.get("product_keywords") or [])
            hsn_score = ComplianceRetriever._hsn_score(request_hsn, stored_hsn)
            keyword_score = ComplianceRetriever._keyword_score(product_tokens, stored_keywords)
            if stored_hsn and hsn_score == 0 and keyword_score == 0:
                continue
            score = float(document.get("confidence_score", 0)) + hsn_score + keyword_score
            matches.append(
                RequirementMatch(
                    requirement=self._document_to_requirement(document),
                    score=min(score, 100),
                ),
            )
        return sorted(matches, key=lambda match: match.score, reverse=True)[:limit]

    def review_context(self, *, destination_country: str, category: str) -> EvidenceReviewContext:
        documents = self.requirements.find(
            {
                "tenant_id": str(self.tenant_id),
                "country": destination_country,
                "category": category,
            },
        )
        total = 0
        pending = 0
        stale = 0
        for document in documents:
            total += 1
            if document.get("status") != "active" or document.get("review_status") != "approved":
                pending += 1
                continue
            if is_stale(expires_at=document.get("expires_at")):
                stale += 1
        return EvidenceReviewContext(
            total_records=total, pending_records=pending, stale_records=stale
        )

    def record_source_snapshot(
        self,
        *,
        source_url: str,
        country: str,
        category: str,
        title: str,
        markdown: str,
    ) -> SourceSnapshotResult:
        now = datetime.now(UTC)
        content_hash = source_snapshot_fingerprint(
            source_url=source_url, title=title, markdown=markdown
        )
        filter_query = {"tenant_id": str(self.tenant_id), "source_url": source_url}
        latest = self.source_snapshots.find_one(filter_query, sort=[("scraped_at", -1)])
        previous_hash = latest.get("content_hash") if latest else None
        if previous_hash is None:
            status = "new_snapshot"
            pending_review_created = False
            message = (
                f"source={source_url} content_hash={content_hash} changed=new "
                "pending_review_created=false"
            )
        elif previous_hash == content_hash:
            status = "unchanged"
            pending_review_created = False
            message = (
                f"source={source_url} content_hash={content_hash} changed=false "
                "pending_review_created=false"
            )
        else:
            status = "needs_review"
            pending_review_created = True
            message = (
                f"source={source_url} content_hash={content_hash} changed=true "
                "pending_review_created=true"
            )

        snapshot_id = str(uuid4())
        self.source_snapshots.insert_one(
            {
                "_id": snapshot_id,
                "tenant_id": str(self.tenant_id),
                "source_url": source_url,
                "country": country,
                "category": category,
                "title": title,
                "markdown": markdown,
                "content_hash": content_hash,
                "previous_content_hash": previous_hash,
                "status": status,
                "scraped_at": now,
            },
        )
        if pending_review_created:
            self.source_changes.insert_one(
                {
                    "_id": str(uuid4()),
                    "tenant_id": str(self.tenant_id),
                    "source_url": source_url,
                    "country": country,
                    "category": category,
                    "previous_snapshot_id": latest.get("_id") if latest else None,
                    "current_snapshot_id": snapshot_id,
                    "previous_content_hash": previous_hash,
                    "current_content_hash": content_hash,
                    "status": "needs_review",
                    "created_at": now,
                },
            )

        return SourceSnapshotResult(
            source_url=source_url,
            title=title,
            content_hash=content_hash,
            previous_content_hash=previous_hash,
            status=status,
            message=message,
        )

    def due_sources(self, *, limit: int = 25) -> list[DueComplianceSource]:
        cutoff = datetime.now(UTC) - timedelta(days=self.settings.compliance_refresh_interval_days)
        documents = self.requirements.find(
            {"tenant_id": str(self.tenant_id), "status": "active", "review_status": "approved"},
            {"source_url": 1, "country": 1, "category": 1},
        )
        due: list[DueComplianceSource] = []
        seen: set[str] = set()
        for document in documents:
            source_url = document.get("source_url")
            if not source_url or source_url in seen:
                continue
            seen.add(source_url)
            latest = self.source_snapshots.find_one(
                {"tenant_id": str(self.tenant_id), "source_url": source_url},
                sort=[("scraped_at", -1)],
            )
            last_checked_at = latest.get("scraped_at") if latest else None
            if last_checked_at is None or last_checked_at <= cutoff:
                due.append(
                    DueComplianceSource(
                        source_url=source_url,
                        country=document.get("country", ""),
                        category=document.get("category", ""),
                        last_checked_at=last_checked_at,
                    ),
                )
            if len(due) >= limit:
                break
        return due

    def _record_to_document(
        self, record: ComplianceRequirementInput, *, now: datetime
    ) -> dict[str, Any]:
        normalized_hsn = normalize_hsn(record.hsn_code)
        requirement_text = record.extracted_requirement or record.requirement_text
        last_checked_at = record.last_checked_at or now
        expires_at = record.expires_at or calculate_expires_at(
            category=record.category,
            requirement_type=record.requirement_type,
            last_checked_at=last_checked_at,
        )
        content_hash = requirement_fingerprint(
            tenant_id=str(self.tenant_id),
            country=record.country,
            category=record.category,
            hsn_code=normalized_hsn,
            requirement_type=record.requirement_type,
            requirement_text=requirement_text,
            source_url=record.source_url,
        )
        return {
            "tenant_id": str(self.tenant_id),
            "country": record.country,
            "category": record.category,
            "hsn_code": normalized_hsn,
            "product_keywords": tokenize_keywords(record.product_keywords),
            "requirement_type": record.requirement_type,
            "extracted_requirement": requirement_text.strip(),
            "requirement_text": requirement_text.strip(),
            "source_url": record.source_url.strip(),
            "source_name": record.source_name.strip(),
            "source_authority_level": record.source_authority_level,
            "effective_date": record.effective_date,
            "last_scraped_at": now,
            "last_checked_at": last_checked_at,
            "expires_at": expires_at,
            "confidence_score": record.confidence_score,
            "status": record.status,
            "review_status": record.review_status,
            "reviewed_by": record.reviewed_by,
            "reviewed_at": record.reviewed_at,
            "notes": record.notes,
            "unresolved_questions": record.unresolved_questions,
            "content_hash": content_hash,
        }

    def _document_to_requirement(self, document: dict[str, Any]) -> StoredComplianceRequirement:
        last_checked_at = document.get("last_checked_at") or document.get("last_scraped_at")
        expires_at = document.get("expires_at")
        return StoredComplianceRequirement(
            id=str(document.get("_id", "")),
            tenant_id=str(document.get("tenant_id", "")),
            country=str(document.get("country", "")),
            category=str(document.get("category", "")),
            hsn_code=document.get("hsn_code"),
            product_keywords=list(document.get("product_keywords") or []),
            requirement_type=str(document.get("requirement_type", "")),
            extracted_requirement=str(
                document.get("extracted_requirement") or document.get("requirement_text", "")
            ),
            source_url=str(document.get("source_url", "")),
            source_name=str(document.get("source_name", "")),
            source_authority_level=str(document.get("source_authority_level", "unknown")),
            last_checked_at=last_checked_at if isinstance(last_checked_at, datetime) else None,
            expires_at=expires_at if isinstance(expires_at, datetime) else None,
            confidence_score=float(document.get("confidence_score", 0)),
            status=str(document.get("status", "")),
            review_status=str(document.get("review_status", "")),
            reviewed_by=document.get("reviewed_by"),
            reviewed_at=document.get("reviewed_at")
            if isinstance(document.get("reviewed_at"), datetime)
            else None,
            notes=document.get("notes"),
            unresolved_questions=list(document.get("unresolved_questions") or []),
            content_hash=str(document.get("content_hash", "")),
        )


def get_compliance_knowledge_store(session: Session, tenant_id: UUID) -> ComplianceKnowledgeStore:
    settings = get_settings()
    backend = settings.compliance_store_backend.lower()
    if backend == "mongo":
        return MongoComplianceKnowledgeStore(tenant_id=tenant_id)
    if backend == "postgres":
        return PostgresComplianceKnowledgeStore(session=session, tenant_id=tenant_id)
    raise ComplianceStoreConfigurationError(
        "COMPLIANCE_STORE_BACKEND must be either 'postgres' or 'mongo'.",
    )
