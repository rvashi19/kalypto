"""Incentive / rate lookup, decoupled from HSN classification.

This is the forward-looking endpoint that the HSN Finder hands a selected HSN to.
It reuses the existing tenant-scoped, governed RateTable lookup. A missing rate
means "no approved incentive data" — never "HSN not found".
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession
from app.schemas.shipment import HsnRateLookupResponse
from app.services.hsn_rate_service import lookup_rates

router = APIRouter(prefix="/incentives", tags=["incentives"])


@router.get("/search", response_model=HsnRateLookupResponse)
def search_incentives(
    session: DbSession,
    current_user: CurrentUser,
    hsn_code: str = Query(min_length=1),
    fob_value: float | None = Query(default=None),
) -> HsnRateLookupResponse:
    result = lookup_rates(
        session=session,
        tenant_id=current_user.organization.id,
        hsn_code=hsn_code,
        fob_value=fob_value,
    )
    if not result.get("found"):
        result["message"] = (
            "HSN exists, but no approved incentive/rate data is available for this code. "
            "Import and approve the current official rate schedule to show values."
        )
    return HsnRateLookupResponse.model_validate(result)
