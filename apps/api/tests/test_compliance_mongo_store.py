# ruff: noqa: E501
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from app.schemas.compliance import ComplianceRequirementInput
from app.services.compliance_store import MongoComplianceKnowledgeStore


class FakeCollection:
    def __init__(self) -> None:
        self.documents: list[dict[str, Any]] = []

    def create_index(self, *args: Any, **kwargs: Any) -> None:
        return None

    def find_one(
        self,
        filter_query: dict[str, Any],
        sort: list[tuple[str, int]] | None = None,
    ) -> dict[str, Any] | None:
        results = list(self.find(filter_query))
        if sort:
            key, direction = sort[0]
            results.sort(key=lambda document: document.get(key) or datetime.min.replace(tzinfo=UTC), reverse=direction < 0)
        return results[0] if results else None

    def find(
        self,
        filter_query: dict[str, Any],
        projection: dict[str, int] | None = None,
    ) -> list[dict[str, Any]]:
        return [document for document in self.documents if self._matches(document, filter_query)]

    def insert_one(self, document: dict[str, Any]) -> None:
        self.documents.append(document.copy())

    def replace_one(
        self,
        filter_query: dict[str, Any],
        replacement: dict[str, Any],
        upsert: bool = False,
    ) -> None:
        for index, document in enumerate(self.documents):
            if self._matches(document, filter_query):
                self.documents[index] = replacement.copy()
                return
        if upsert:
            self.documents.append(replacement.copy())

    @staticmethod
    def _matches(document: dict[str, Any], filter_query: dict[str, Any]) -> bool:
        return all(document.get(key) == value for key, value in filter_query.items())


class FakeDatabase:
    def __init__(self) -> None:
        self.collections: dict[str, FakeCollection] = {}

    def __getitem__(self, name: str) -> FakeCollection:
        if name not in self.collections:
            self.collections[name] = FakeCollection()
        return self.collections[name]


def test_mongo_store_retrieves_active_requirement_documents() -> None:
    tenant_id = uuid4()
    store = MongoComplianceKnowledgeStore(tenant_id=tenant_id, database=FakeDatabase())

    created, updated = store.ingest(
        [
            ComplianceRequirementInput(
                country="Canada",
                category="beverages",
                hsn_code="2009",
                product_keywords=["mango", "juice"],
                requirement_type="labeling",
                requirement_text="Bilingual retail label requirements must be verified before shipment.",
                source_url="https://inspection.canada.ca/en/food-labels/labelling",
                source_name="CFIA food labelling",
                source_authority_level="official",
                confidence_score=82,
            ),
        ],
    )

    matches = store.retrieve(
        product="Mango juice beverage",
        hsn_code="200989",
        destination_country="Canada",
        category="beverages",
    )

    assert (created, updated) == (1, 0)
    assert len(matches) == 1
    assert matches[0].requirement.source_name == "CFIA food labelling"
    assert matches[0].score > 80


def test_mongo_store_detects_source_snapshot_changes() -> None:
    tenant_id = uuid4()
    database = FakeDatabase()
    store = MongoComplianceKnowledgeStore(tenant_id=tenant_id, database=database)

    first = store.record_source_snapshot(
        source_url="https://example.gov/rules",
        country="Canada",
        category="beverages",
        title="Rules",
        markdown="Current label rules",
    )
    unchanged = store.record_source_snapshot(
        source_url="https://example.gov/rules",
        country="Canada",
        category="beverages",
        title="Rules",
        markdown="Current label rules",
    )
    changed = store.record_source_snapshot(
        source_url="https://example.gov/rules",
        country="Canada",
        category="beverages",
        title="Rules",
        markdown="Updated label rules",
    )

    assert first.status == "new_snapshot"
    assert unchanged.status == "unchanged"
    assert changed.status == "needs_review"
    assert len(database["compliance_source_changes"].documents) == 1


def test_mongo_store_lists_sources_due_for_refresh() -> None:
    tenant_id = uuid4()
    database = FakeDatabase()
    store = MongoComplianceKnowledgeStore(tenant_id=tenant_id, database=database)
    store.ingest(
        [
            ComplianceRequirementInput(
                country="Canada",
                category="beverages",
                hsn_code="2009",
                product_keywords=["mango", "juice"],
                requirement_type="labeling",
                requirement_text="Bilingual retail label requirements must be verified before shipment.",
                source_url="https://inspection.canada.ca/en/food-labels/labelling",
                source_name="CFIA food labelling",
                source_authority_level="official",
                confidence_score=82,
            ),
        ],
    )
    store.record_source_snapshot(
        source_url="https://inspection.canada.ca/en/food-labels/labelling",
        country="Canada",
        category="beverages",
        title="CFIA",
        markdown="Old label rules",
    )
    database["compliance_source_snapshots"].documents[0]["scraped_at"] = datetime.now(UTC) - timedelta(days=5)

    due = store.due_sources(limit=5)

    assert len(due) == 1
    assert due[0].source_url == "https://inspection.canada.ca/en/food-labels/labelling"