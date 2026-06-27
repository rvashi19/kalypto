from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.tools import ExportQuoteRequest, ExportQuoteResponse
from app.services.export_quote_service import calculate_export_quote

router = APIRouter(prefix="/tools", tags=["tools"])


@router.post("/export-quote", response_model=ExportQuoteResponse)
def calculate_quote(
    payload: ExportQuoteRequest,
    session: DbSession,
    current_user: CurrentUser,
) -> ExportQuoteResponse:
    return calculate_export_quote(
        session=session,
        tenant_id=current_user.organization.id,
        payload=payload,
    )
