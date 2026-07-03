# ruff: noqa: E501
"""Queue/job abstraction for compliance retrieval.

Current backend: FastAPI BackgroundTasks (in-process). A retrieval job row is created
synchronously (status="queued"); the actual crawl runs in the background so the user
request is never blocked by a long crawl.

FUTURE AWS MAPPING:
  BackgroundTasks (in-process)  -> SQS queue + ECS/Fargate worker (or Redis + rq)
  enqueue_retrieval_job         -> sqs.send_message with the job id
  get_job_status                -> read the ComplianceRetrievalJob row (unchanged)
  retry_job                     -> re-enqueue the same job id
The interface stays stable; only the enqueue mechanism changes.
"""

from __future__ import annotations

from uuid import UUID

from app.core.settings import get_settings
from app.db.session import session_scope
from app.models import ComplianceRetrievalJob
from app.services.compliance_retrieval_job import run_retrieval_job

# Auto-retry: transient failures (network/timeout) are retried; permanent ones
# (e.g. no official source registered, non-whitelisted domain) are not.
_PERMANENT_MARKERS = (
    "No active official source",
    "non-whitelisted domain",
    "Refused to fetch",
)


def _is_permanent_failure(message: str | None) -> bool:
    if not message:
        return False
    return any(marker in message for marker in _PERMANENT_MARKERS)


def _run_job_in_new_session(job_id: UUID, tenant_id: UUID, force: bool) -> None:
    """Background entrypoint. Uses its own DB session (request session is closed).

    Retries transient failures up to the job's persisted max_retries; skips retry
    for permanent failures (no registered source, non-whitelisted domain).
    """
    fallback_max_retries = max(0, get_settings().compliance_max_retries)
    attempt = 0
    while True:
        attempt += 1
        with session_scope() as session:
            job = session.get(ComplianceRetrievalJob, job_id)
            if job is None or job.tenant_id != tenant_id:
                return
            if job.max_retries < 0:
                job.max_retries = fallback_max_retries
            max_retries = job.max_retries
            job.retry_count = max(0, attempt - 1)
            session.flush()
            try:
                job = run_retrieval_job(
                    session, job_id=job_id, tenant_id=tenant_id, force=force
                )
                status, message = job.status, job.error_message
            except Exception as exc:  # pragma: no cover - defensive; mark job failed
                job = session.get(ComplianceRetrievalJob, job_id)
                if job is not None:
                    job.status = "failed"
                    job.error_message = str(exc)[:4000]
                    status, message, max_retries = "failed", str(exc), job.max_retries
                else:
                    status, message, max_retries = "failed", str(exc), fallback_max_retries
        if status != "failed" or _is_permanent_failure(message) or attempt > max_retries:
            return


def enqueue_retrieval_job(background_tasks, *, job_id: UUID, tenant_id: UUID, force: bool = False) -> None:
    """Schedule a retrieval job to run after the response is returned."""
    background_tasks.add_task(_run_job_in_new_session, job_id, tenant_id, force)


def get_job_status(session, *, job_id: UUID, tenant_id: UUID) -> ComplianceRetrievalJob | None:
    job = session.get(ComplianceRetrievalJob, job_id)
    if job is None or job.tenant_id != tenant_id:
        return None
    return job


def retry_job(background_tasks, session, *, job_id: UUID, tenant_id: UUID) -> ComplianceRetrievalJob | None:
    job = get_job_status(session, job_id=job_id, tenant_id=tenant_id)
    if job is None:
        return None
    job.status = "queued"
    job.error_message = None
    job.retry_count = 0
    job.max_retries = max(0, get_settings().compliance_max_retries)
    session.flush()
    enqueue_retrieval_job(background_tasks, job_id=job_id, tenant_id=tenant_id, force=True)
    return job
