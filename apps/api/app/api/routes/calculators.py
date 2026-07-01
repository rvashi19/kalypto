# ruff: noqa: E501
"""Landed-Cost / Export-Quote calculator (/api/v1/calculators/export-quote).

Consumes an already-selected HSN and the Incentive Finder's approved rates — it does
not classify HSN or invent incentive/duty/tax/FX values.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models import ExportQuoteCalculation
from app.schemas.export_quote import (
    ExportQuoteCalculateResponse,
    ExportQuoteDetailResponse,
    ExportQuoteListItem,
    ExportQuoteRequest,
    ExportQuoteSaveRequest,
)
from app.services.export_quote_calc import QuoteInputs, ResolvedIncentive, calculate_quote
from app.services.hsn_normalization import normalize_code
from app.services.incentive_search import search_incentives

router = APIRouter(prefix="/calculators/export-quote", tags=["calculators"])

# Input fields shared by request, model, and QuoteInputs.
_INPUT_FIELDS = (
    "quantity", "unit_price", "product_value", "fx_rate_to_inr", "include_incentives",
    "loading_charges", "local_transportation", "packaging_cost", "cfs_charges",
    "terminal_handling_charges", "customs_clearance_charges", "local_transit_charges",
    "seal_charges", "bill_of_lading_charges", "cha_charges", "phytosanitary_certificate_charges",
    "fumigation_charges", "vgm_charges", "misc_origin_charges", "bank_transaction_charges",
    "onsite_inspection_charges", "ecgc_premium", "general_insurance", "freight_cost",
    "destination_handling_charges", "import_duty_rate", "import_duty_amount",
    "destination_tax_rate", "destination_tax_amount", "other_destination_charges",
    "commission", "exporter_cost_of_goods", "exporter_overheads",
    "target_profit_per_unit", "target_profit_total",
)
_PERSIST_TEXT = (
    "buyer_name", "buyer_country", "seller_country", "origin_city_or_place", "port_of_loading",
    "port_of_discharge", "final_destination", "incoterms_version", "quote_currency",
    "product_description", "packaging_description", "unit", "notes",
)


def _resolve_incentives(
    session: DbSession, tenant_id: UUID, request: ExportQuoteRequest, normalized_hsn: str
) -> list[ResolvedIncentive]:
    if request.incentive_scheme_rates:
        return [
            ResolvedIncentive(scheme=item.scheme.lower(), rate=float(item.rate), source="user_provided")
            for item in request.incentive_scheme_rates
        ]
    if not request.include_incentives or len(normalized_hsn) < 2:
        return []
    matches = search_incentives(session=session, tenant_id=tenant_id, hsn_code=normalized_hsn)
    resolved: list[ResolvedIncentive] = []
    seen: set[str] = set()
    for match in matches:
        scheme = match.row.scheme.lower()
        if scheme in seen:
            continue
        seen.add(scheme)
        resolved.append(
            ResolvedIncentive(
                scheme=scheme,
                rate=float(match.row.rate_value),
                source="approved_source_backed",
                cap_value=float(match.row.cap_value) if match.row.cap_value is not None else None,
                cap_unit=match.row.cap_unit,
            )
        )
    return resolved


def _inputs_from_request(request: ExportQuoteRequest, incentives: list[ResolvedIncentive]) -> QuoteInputs:
    kwargs = {name: getattr(request, name) for name in _INPUT_FIELDS}
    return QuoteInputs(
        incoterm=request.normalized_incoterm(),
        quote_currency=request.quote_currency,
        hsn_code=normalize_code(request.hsn_code or ""),
        incentives=incentives,
        **kwargs,
    )


def _named_place(request: ExportQuoteRequest) -> str:
    term = request.normalized_incoterm()
    place = request.port_of_loading if term in ("FOB", "FAS", "FCA", "EXW") else (
        request.port_of_discharge or request.final_destination
    )
    place = place or request.final_destination or request.port_of_discharge or "named place"
    country = request.buyer_country if term not in ("FOB", "FAS", "FCA", "EXW") else request.seller_country
    tail = f", {country}" if country else ""
    return f"{term} {place}{tail} Incoterms {request.incoterms_version}"


def _build_response(session: DbSession, tenant_id: UUID, request: ExportQuoteRequest) -> ExportQuoteCalculateResponse:
    normalized_hsn = normalize_code(request.hsn_code or "")
    incentives = _resolve_incentives(session, tenant_id, request, normalized_hsn)
    result = calculate_quote(_inputs_from_request(request, incentives))
    warnings = list(result["warnings"])
    if not normalized_hsn:
        warnings.insert(0, "Select/classify HSN first for better incentive accuracy.")
    warnings.append("HSN classification should be verified before filing.")
    result["warnings"] = warnings
    return ExportQuoteCalculateResponse(
        input_summary={
            "product_description": request.product_description,
            "hsn_code": normalized_hsn or None,
            "quantity": request.quantity,
            "unit": request.unit,
            "unit_price": request.unit_price,
            "incoterm": request.normalized_incoterm(),
            "quote_currency": request.quote_currency.upper(),
            "buyer_country": request.buyer_country,
        },
        incoterms_version=request.incoterms_version,
        named_place_summary=_named_place(request),
        **result,
    )


@router.post("/calculate", response_model=ExportQuoteCalculateResponse)
def calculate(request: ExportQuoteRequest, session: DbSession, current_user: CurrentUser) -> ExportQuoteCalculateResponse:
    try:
        return _build_response(session, current_user.organization.id, request)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error


@router.post("/save", response_model=ExportQuoteDetailResponse, status_code=status.HTTP_201_CREATED)
def save(request: ExportQuoteSaveRequest, session: DbSession, current_user: CurrentUser) -> ExportQuoteDetailResponse:
    try:
        response = _build_response(session, current_user.organization.id, request)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error

    row = ExportQuoteCalculation(
        tenant_id=current_user.organization.id,
        user_id=current_user.user.id,
        quote_number=request.quote_number or f"EQ-{uuid4().hex[:8].upper()}",
        status=request.status or "saved",
        incoterm=request.normalized_incoterm(),
        hsn_code=normalize_code(request.hsn_code or "") or None,
        quantity=request.quantity,
        unit_price=request.unit_price,
        incentive_amount=response.incentive_amount,
        incentive_details_json=response.incentive_breakdown,
        assumptions_json=response.assumptions,
        warnings_json=response.warnings,
        calculation_version=response.calculation_version,
        fob_value=response.fob_value,
        fob_per_unit=response.fob_per_unit,
        cfr_value=response.cfr_value,
        cfr_per_unit=response.cfr_per_unit,
        cif_value=response.cif_value,
        cif_per_unit=response.cif_per_unit,
        total_landed_cost=response.total_landed_cost,
        landed_cost_per_unit=response.landed_cost_per_unit,
        gross_exporter_realization=response.gross_exporter_realization,
        net_exporter_realization=response.net_exporter_realization,
        net_realization_per_unit=response.net_realization_per_unit,
        exporter_margin_amount=response.exporter_margin_amount,
        exporter_margin_percent=response.exporter_margin_percent,
        product_value=response.product_value,
    )
    for name in _PERSIST_TEXT:
        setattr(row, name, getattr(request, name))
    for name in _INPUT_FIELDS:
        if hasattr(row, name):
            setattr(row, name, getattr(request, name))
    session.add(row)
    session.commit()
    session.refresh(row)
    return _detail_response(session, current_user, row)


@router.get("", response_model=list[ExportQuoteListItem])
def list_quotes(session: DbSession, current_user: CurrentUser) -> list[ExportQuoteListItem]:
    rows = session.scalars(
        select(ExportQuoteCalculation)
        .where(ExportQuoteCalculation.tenant_id == current_user.organization.id)
        .order_by(ExportQuoteCalculation.created_at.desc())
        .limit(100)
    ).all()
    return [_list_item(row) for row in rows]


@router.get("/{quote_id}", response_model=ExportQuoteDetailResponse)
def get_quote(quote_id: UUID, session: DbSession, current_user: CurrentUser) -> ExportQuoteDetailResponse:
    row = _load(session, current_user, quote_id)
    return _detail_response(session, current_user, row)


@router.post("/{quote_id}/duplicate", response_model=ExportQuoteDetailResponse, status_code=status.HTTP_201_CREATED)
def duplicate(quote_id: UUID, session: DbSession, current_user: CurrentUser) -> ExportQuoteDetailResponse:
    source = _load(session, current_user, quote_id)
    clone = ExportQuoteCalculation(
        tenant_id=source.tenant_id,
        user_id=current_user.user.id,
        quote_number=f"EQ-{uuid4().hex[:8].upper()}",
        status="draft",
        calculation_version=source.calculation_version,
    )
    for column in ExportQuoteCalculation.__table__.columns.keys():
        if column in ("id", "user_id", "quote_number", "status", "created_at", "updated_at", "tenant_id"):
            continue
        setattr(clone, column, getattr(source, column))
    session.add(clone)
    session.commit()
    session.refresh(clone)
    return _detail_response(session, current_user, clone)


def _load(session: DbSession, current_user: CurrentUser, quote_id: UUID) -> ExportQuoteCalculation:
    row = session.get(ExportQuoteCalculation, quote_id)
    if row is None or row.tenant_id != current_user.organization.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quote not found.")
    return row


def _list_item(row: ExportQuoteCalculation) -> ExportQuoteListItem:
    return ExportQuoteListItem(
        id=str(row.id),
        quote_number=row.quote_number,
        buyer_name=row.buyer_name,
        buyer_country=row.buyer_country,
        incoterm=row.incoterm,
        hsn_code=row.hsn_code,
        quote_currency=row.quote_currency,
        fob_value=float(row.fob_value),
        cif_value=float(row.cif_value),
        net_exporter_realization=float(row.net_exporter_realization),
        exporter_margin_percent=float(row.exporter_margin_percent),
        status=row.status,
        created_at=row.created_at,
    )


def _model_to_request(row: ExportQuoteCalculation) -> ExportQuoteRequest:
    request = ExportQuoteRequest(
        incoterm=row.incoterm,
        incoterms_version=row.incoterms_version,
        quote_currency=row.quote_currency,
        quantity=float(row.quantity),
        unit_price=float(row.unit_price),
    )
    request.hsn_code = row.hsn_code
    request.include_incentives = bool(row.incentive_details_json)
    for name in _PERSIST_TEXT:
        setattr(request, name, getattr(row, name))
    for name in _INPUT_FIELDS:
        if name == "include_incentives":
            continue
        value = getattr(row, name, None)
        if value is not None:
            setattr(request, name, float(value))
    return request


def _detail_response(session: DbSession, current_user: CurrentUser, row: ExportQuoteCalculation) -> ExportQuoteDetailResponse:
    # Rebuild the full calculation deterministically from stored inputs + saved incentives.
    request = _model_to_request(row)
    incentives = [
        ResolvedIncentive(
            scheme=i["scheme"], rate=float(i["rate_percent"]), source=i.get("source", "approved_source_backed")
        )
        for i in (row.incentive_details_json or [])
    ]
    result = calculate_quote(_inputs_from_request(request, incentives))
    calc = ExportQuoteCalculateResponse(
        input_summary={"hsn_code": row.hsn_code, "quantity": float(row.quantity), "incoterm": row.incoterm},
        incoterms_version=row.incoterms_version,
        named_place_summary=_named_place(request),
        **result,
    )
    return ExportQuoteDetailResponse(**_list_item(row).model_dump(), calculation=calc, notes=row.notes)
