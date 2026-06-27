from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class RateRecordResponse(BaseModel):
    id: UUID
    scheme: str
    hsn: str
    rate: float
    source: str
    source_url: str | None
    effective_date: datetime
    version_stamp: str
    confidence: str | None
    review_status: str
    reviewed_by: str | None
    reviewed_at: datetime | None
    expires_at: datetime | None
    notes: str | None

    model_config = {"from_attributes": True}


class RateImportError(BaseModel):
    row: int
    message: str


class RateImportResponse(BaseModel):
    created: int
    failed: int
    errors: list[RateImportError]
