from __future__ import annotations

import csv
from datetime import datetime
from io import StringIO

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from pydantic import BaseModel, Field, ValidationError

from app.api.deps import CurrentUser, DbSession
from app.models import MembershipRole, RateTable
from app.repositories.base import TenantRepository
from app.schemas.rates import RateImportError, RateImportResponse, RateRecordResponse
from app.services.rate_limit import rate_limit_upload_requests

router = APIRouter(prefix="/rates", tags=["rates"])


class _RateRow(BaseModel):
    scheme: str = Field(min_length=2, max_length=120)
    hsn: str = Field(min_length=2, max_length=20, pattern=r"^\d+$")
    rate: float = Field(ge=0, le=100)
    source: str = Field(min_length=5, max_length=255)
    effective_date: datetime
    version_stamp: str = Field(min_length=2, max_length=80)
    confidence: str | None = Field(default=None, max_length=40)


def _require_editor(current_user: CurrentUser) -> None:
    if current_user.membership.role == MembershipRole.READ_ONLY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Read-only members cannot import rate tables.",
        )


@router.get("", response_model=list[RateRecordResponse])
def list_rates(
    session: DbSession,
    current_user: CurrentUser,
) -> list[RateRecordResponse]:
    repository = TenantRepository(
        session=session,
        model=RateTable,
        tenant_id=current_user.organization.id,
        actor_user_id=current_user.user.id,
    )
    return [RateRecordResponse.model_validate(row) for row in repository.list()]


@router.post(
    "/import",
    response_model=RateImportResponse,
    dependencies=[Depends(rate_limit_upload_requests)],
)
async def import_rates(
    file: UploadFile,
    session: DbSession,
    current_user: CurrentUser,
) -> RateImportResponse:
    _require_editor(current_user)
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Rate imports must be UTF-8 CSV files.",
        )
    try:
        content = (await file.read()).decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Rate CSV must be UTF-8 encoded.",
        ) from error

    repository = TenantRepository(
        session=session,
        model=RateTable,
        tenant_id=current_user.organization.id,
        actor_user_id=current_user.user.id,
    )
    created = 0
    errors: list[RateImportError] = []
    for row_number, row in enumerate(csv.DictReader(StringIO(content)), start=2):
        try:
            payload = _RateRow.model_validate(row)
        except ValidationError as error:
            errors.append(RateImportError(row=row_number, message=str(error)))
            continue
        repository.add(
            RateTable(
                tenant_id=current_user.organization.id,
                **payload.model_dump(),
            )
        )
        created += 1
    session.commit()
    return RateImportResponse(created=created, failed=len(errors), errors=errors)
