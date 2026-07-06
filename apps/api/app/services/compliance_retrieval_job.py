# ruff: noqa: E501
"""Official-source retrieval workflow for the Country Compliance Checker.

Flow (never runs on the hot user request path — always via the queue):
  1. Load active source-registry entries for the job's destination country + category.
  2. For each entry, enforce the official-domain whitelist (reject anything else).
  3. Fetch (HTTP-first) up to COMPLIANCE_MAX_PAGES_PER_JOB pages, honoring COMPLIANCE_MAX_PDF_MB.
  4. Record a source snapshot with checksum. If checksum unchanged -> reuse, skip AI.
  5. Store raw + extracted text via the storage abstraction.
  6. Run AI extraction ONLY on new/changed snapshots (unless force=True).
  7. Persist extracted requirement cards as review_status="pending" (pending_review) at
     Low/Medium confidence + evidence rows. They never appear as approved answers until
     an admin approves them.
  8. Update job counters + status (completed / needs_review / failed).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.models import (
    ComplianceRetrievalJob,
    ComplianceSourceRegistry,
    ComplianceSourceSnapshot,
)
from app.models.compliance import ComplianceRequirementEvidence, ComplianceReviewQueue
from app.schemas.compliance import ComplianceRequirementInput
from app.services.compliance_ai_extractor import (
    ComplianceAIError,
    get_compliance_ai_extractor,
)
from app.services.compliance_retrieval import ComplianceDataWriter
from app.services.compliance_scraper import ComplianceScraperError, get_compliance_scraper
from app.services.compliance_source_retriever import (
    _detect_source_type,
    retrieve_source,
)
from app.services.compliance_storage import get_compliance_storage
from app.services.compliance_store import get_compliance_knowledge_store
from app.services.compliance_whitelist import (
    DomainNotWhitelistedError,
    assert_domain_allowed,
)

_REQUIREMENT_TYPE_MAP = {
    "document": "import_document",
    "label": "labeling",
    "certificate": "certificate",
    "inspection": "inspection",
    "license": "restriction",  # licences surface as restriction-style gates
    "restriction": "restriction",
    "buyer_question": "buyer_question",
    "warning": "restriction",
}


def _confidence_score(label: str) -> float:
    return {"low": 40.0, "medium": 60.0}.get(label.lower(), 40.0)


def run_retrieval_job(session: Session, *, job_id: UUID, tenant_id: UUID, force: bool = False) -> ComplianceRetrievalJob:
    """Execute a retrieval job synchronously. Called by the queue worker."""
    job = session.get(ComplianceRetrievalJob, job_id)
    if job is None or job.tenant_id != tenant_id:
        raise ValueError("Retrieval job not found for this tenant.")

    job.status = "running"
    job.started_at = datetime.now(UTC)
    session.flush()

    settings = get_settings()
    max_pages = max(1, settings.compliance_max_pages_per_job)
    store = get_compliance_knowledge_store(session, tenant_id)
    writer = ComplianceDataWriter(session=session, tenant_id=tenant_id)
    storage = get_compliance_storage()
    scraper = get_compliance_scraper()

    sources = _sources_for_job(session, tenant_id, job)
    if not sources:
        job.status = "failed"
        job.error_message = (
            "No active official source registered for this country/category. "
            "An admin must add one under /compliance/sources."
        )
        job.completed_at = datetime.now(UTC)
        session.flush()
        return job

    job.source_registry_ids_json = [str(s.id) for s in sources]
    ai = None
    pages_fetched = snapshots_created = requirements_extracted = 0
    errors: list[str] = []
    extracted_any_pending = False

    for source in sources:
        if pages_fetched >= max_pages:
            break
        url = source.base_url
        extra_domains = list(source.allowed_domains_json or [])
        try:
            assert_domain_allowed(url, extra_domains)
        except DomainNotWhitelistedError as exc:
            errors.append(str(exc))
            continue

        source_type = _detect_source_type(url, source.source_type)
        final_url = url
        http_status = 200
        raw_bytes: bytes | None = None
        try:
            # XLSX/CSV official sources go through the spreadsheet retriever adapter;
            # HTML/PDF stay on the existing whitelist/SSRF-guarded scraper (empty list
            # still enforces the builtin/env official whitelist).
            if source_type in {"xlsx", "csv"}:
                result_meta = retrieve_source(
                    url, declared_source_type=source.source_type, allowed_domains=extra_domains
                )
                doc_source_url = result_meta.final_url
                doc_title = result_meta.source_title
                doc_text = result_meta.extracted_text
                final_url = result_meta.final_url
                http_status = result_meta.http_status
                parser_used = result_meta.parser_used
                raw_bytes = result_meta.raw_bytes
            else:
                document = scraper.scrape(url, allowed_domains=extra_domains)
                doc_source_url = document.source_url
                doc_title = document.title
                doc_text = document.markdown
                final_url = document.source_url
                parser_used = "pdfplumber" if source_type == "pdf" else "html_text"
        except ComplianceScraperError as exc:
            errors.append(f"{url}: {exc}")
            continue

        pages_fetched += 1
        snapshot_result = store.record_source_snapshot(
            source_url=doc_source_url,
            country=job.destination_country,
            category=job.product_category,
            title=doc_title,
            markdown=doc_text,
        )

        snapshot_row = session.scalars(
            select(ComplianceSourceSnapshot)
            .where(
                ComplianceSourceSnapshot.tenant_id == tenant_id,
                ComplianceSourceSnapshot.source_url == doc_source_url,
            )
            .order_by(ComplianceSourceSnapshot.scraped_at.desc())
        ).first()

        if snapshot_result.status in ("new_snapshot", "needs_review"):
            snapshots_created += 1
            # Persist raw + extracted text via storage abstraction (checksum-keyed).
            key_base = f"{tenant_id}/{snapshot_result.content_hash}"
            extracted_key = f"{key_base}/extracted.txt"
            storage.save_file(extracted_key, doc_text.encode("utf-8"))
            raw_key = None
            if raw_bytes is not None:
                raw_key = f"{key_base}/raw.{source_type}"
                storage.save_file(raw_key, raw_bytes)
            # Populate richer snapshot metadata (nullable/backward-compatible fields).
            if snapshot_row is not None:
                snapshot_row.source_registry_id = source.id
                snapshot_row.final_url = final_url
                snapshot_row.source_type = source_type
                snapshot_row.http_status = http_status
                snapshot_row.parser_used = parser_used
                snapshot_row.parser_status = "ok"
                snapshot_row.raw_storage_key = raw_key
                snapshot_row.extracted_text_storage_key = extracted_key

        # Checksum dedup: skip AI for unchanged sources unless explicitly forced.
        if snapshot_result.status == "unchanged" and not force:
            source.last_checked_at = datetime.now(UTC)
            continue

        # AI extraction (assistant only) — new/changed snapshot.
        if ai is None:
            try:
                ai = get_compliance_ai_extractor()
            except ComplianceAIError as exc:
                errors.append(f"AI extractor unavailable: {exc}")
                break
        try:
            result = ai.extract_requirements_from_source_text(
                source_text=doc_text,
                country=job.destination_country,
                product_category=job.product_category,
                hsn_code=job.hsn_code,
                product_description=job.product_description,
            )
        except ComplianceAIError as exc:
            errors.append(f"{url}: AI extraction failed: {exc}")
            continue

        for card in result.requirements:
            req_input = ComplianceRequirementInput(
                country=job.destination_country,
                category=job.product_category,
                hsn_code=job.hsn_code,
                product_keywords=[job.product_description] if job.product_description else [],
                requirement_type=_REQUIREMENT_TYPE_MAP.get(card.requirement_type, "import_document"),
                requirement_text=(card.detail or card.summary or card.title)[:4000],
                extracted_requirement=(card.summary or card.title)[:4000],
                source_url=doc_source_url,
                source_name=source.source_name,
                source_authority_level="official",
                confidence_score=_confidence_score(card.confidence_label),
                status="draft",              # not active -> excluded from answers
                review_status="pending",     # pending_review -> admin must approve
                notes=(
                    f"AI-extracted ({card.mandatory_or_conditional}). "
                    f"Triggers: {', '.join(card.trigger_conditions) or 'n/a'}"
                )[:2000],
                unresolved_questions=result.missing_questions[:20],
            )
            stored, created = writer.upsert_requirement(req_input)
            if created:
                requirements_extracted += 1
                extracted_any_pending = True
                # Attach evidence excerpt to the pending requirement.
                session.add(
                    ComplianceRequirementEvidence(
                        tenant_id=tenant_id,
                        requirement_id=UUID(stored.id),
                        source_snapshot_id=snapshot_row.id if snapshot_row else None,
                        source_url=doc_source_url,
                        authority_name=source.authority_name,
                        evidence_excerpt=card.evidence_excerpt[:8000],
                        retrieved_at=datetime.now(UTC),
                        checksum=snapshot_result.content_hash,
                    )
                )
                # Every AI-extracted requirement enters the admin review queue.
                session.add(
                    ComplianceReviewQueue(
                        tenant_id=tenant_id,
                        requirement_id=UUID(stored.id),
                        status="pending",
                    )
                )
        source.last_checked_at = datetime.now(UTC)

    job.pages_fetched = pages_fetched
    job.snapshots_created = snapshots_created
    job.requirements_extracted = requirements_extracted
    job.error_message = " | ".join(errors)[:4000] if errors else None
    if pages_fetched == 0 and errors:
        job.status = "failed"
    elif extracted_any_pending:
        job.status = "needs_review"
    else:
        job.status = "completed"
    job.completed_at = datetime.now(UTC)
    session.flush()
    return job


def _sources_for_job(
    session: Session, tenant_id: UUID, job: ComplianceRetrievalJob
) -> list[ComplianceSourceRegistry]:
    rows = session.scalars(
        select(ComplianceSourceRegistry).where(
            ComplianceSourceRegistry.tenant_id == tenant_id,
            ComplianceSourceRegistry.country == job.destination_country,
            ComplianceSourceRegistry.is_active.is_(True),
        )
    ).all()
    # Filter by category when the source declares categories.
    filtered = [
        r
        for r in rows
        if not r.product_categories_json or job.product_category in r.product_categories_json
    ]
    return filtered
