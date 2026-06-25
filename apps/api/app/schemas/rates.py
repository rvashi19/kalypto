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
    effective_date: datetime
    version_stamp: str
    confidence: str | None

    model_config = {"from_attributes": True}


class RateImportError(BaseModel):
    row: int
    message: str


class RateImportResponse(BaseModel):
    created: int
    failed: int
    errors: list[RateImportError]
