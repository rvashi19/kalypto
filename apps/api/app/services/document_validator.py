# ruff: noqa: E501
"""Validate shipment data before document generation."""

from __future__ import annotations

import re
from typing import Any

TOLERANCE = 0.02  # 2% tolerance on computed totals


def _err(code: str, msg: str, severity: str = "error") -> dict[str, str]:
    return {"code": code, "message": msg, "severity": severity}


def validate_shipment_data(data: dict[str, Any]) -> list[dict[str, str]]:
    """Return list of {code, message, severity} dicts. Empty = valid."""
    issues: list[dict[str, str]] = []

    exporter = data.get("exporter", {}) or {}
    buyer = data.get("buyer", {}) or {}
    shipment = data.get("shipment", {}) or {}
    items: list[dict[str, Any]] = data.get("items", []) or []
    packing = data.get("packing", {}) or {}
    declarations = data.get("declarations", {}) or {}

    # --- Exporter ---
    if not exporter.get("company_name"):
        issues.append(_err("EXP001", "Exporter company name is required."))
    if not exporter.get("address"):
        issues.append(_err("EXP002", "Exporter address is required."))
    if not exporter.get("country"):
        issues.append(_err("EXP003", "Exporter country is required."))
    if not exporter.get("iec"):
        issues.append(_err("EXP004", "Exporter IEC is required for Indian export documents.", "warning"))
    if not exporter.get("gstin"):
        issues.append(_err("EXP005", "Exporter GSTIN is required for Indian GST export documentation.", "warning"))

    # --- Buyer ---
    if not buyer.get("buyer_name"):
        issues.append(_err("BUY001", "Buyer name is required."))
    if not buyer.get("buyer_country"):
        issues.append(_err("BUY002", "Buyer country is required."))
    if not buyer.get("buyer_address"):
        issues.append(_err("BUY003", "Buyer address is required.", "warning"))

    # --- Shipment ---
    if not shipment.get("invoice_number"):
        issues.append(_err("SHP001", "Invoice number is required."))
    if not shipment.get("invoice_date"):
        issues.append(_err("SHP002", "Invoice date is required."))
    if not shipment.get("incoterm"):
        issues.append(_err("SHP003", "Incoterm is required."))
    if not shipment.get("currency"):
        issues.append(_err("SHP004", "Currency is required."))
    if not shipment.get("country_of_origin"):
        issues.append(_err("SHP005", "Country of origin is required."))
    if not shipment.get("country_of_final_destination"):
        issues.append(_err("SHP006", "Country of final destination is required."))
    if not shipment.get("port_of_loading"):
        issues.append(_err("SHP007", "Port of loading is required.", "warning"))
    if not shipment.get("port_of_discharge"):
        issues.append(_err("SHP008", "Port of discharge is required.", "warning"))
    if not shipment.get("payment_terms"):
        issues.append(_err("SHP009", "Payment terms are required.", "warning"))

    mode = (shipment.get("mode_of_transport") or "sea").lower()
    if mode == "sea" and not shipment.get("port_of_loading"):
        issues.append(_err("SHP010", "Port of loading is required for sea shipments."))

    # --- Items ---
    if not items:
        issues.append(_err("ITM000", "At least one line item is required."))

    item_total = 0.0
    for idx, item in enumerate(items):
        label = f"Item {item.get('item_number', idx + 1)}"
        if not item.get("product_description"):
            issues.append(_err(f"ITM{idx:03d}A", f"{label}: product description is required."))
        hsn = str(item.get("hsn_code") or "").strip()
        if not hsn:
            issues.append(_err(f"ITM{idx:03d}B", f"{label}: HSN code is required.", "warning"))
        elif not re.fullmatch(r"\d{2,8}", hsn):
            issues.append(_err(f"ITM{idx:03d}C", f"{label}: HSN code must be 2–8 digits (got '{hsn}').", "warning"))

        qty = item.get("quantity")
        price = item.get("unit_price")
        total = item.get("total_value")

        if qty is None or qty <= 0:
            issues.append(_err(f"ITM{idx:03d}D", f"{label}: quantity must be positive."))
        if price is None or price < 0:
            issues.append(_err(f"ITM{idx:03d}E", f"{label}: unit price must be non-negative."))
        if total is None:
            issues.append(_err(f"ITM{idx:03d}F", f"{label}: total value is required.", "warning"))

        if qty and price and total:
            computed = qty * price
            if abs(computed - total) / max(total, 0.01) > TOLERANCE:
                issues.append(_err(f"ITM{idx:03d}G", f"{label}: total value {total} does not match qty×price={computed:.2f} (>{TOLERANCE*100:.0f}% diff).", "warning"))
            item_total += total

        net = item.get("net_weight")
        gross = item.get("gross_weight")
        if net is not None and gross is not None and gross < net:
            issues.append(_err(f"ITM{idx:03d}H", f"{label}: gross weight ({gross}) must be ≥ net weight ({net})."))

    # --- Packing totals vs items ---
    if items and packing:
        declared_total = packing.get("total_invoice_value") or packing.get("grand_total")
        if declared_total and item_total:
            if abs(declared_total - item_total) / max(item_total, 0.01) > TOLERANCE:
                issues.append(_err("PKG001", f"Invoice total declared ({declared_total}) differs from sum of item totals ({item_total:.2f}).", "warning"))

        total_pkgs_declared = packing.get("total_packages")
        total_pkgs_items = sum(item.get("package_count") or 0 for item in items)
        if total_pkgs_declared and total_pkgs_items and total_pkgs_declared != total_pkgs_items:
            issues.append(_err("PKG002", f"Packing total packages ({total_pkgs_declared}) differs from sum of item package counts ({total_pkgs_items}).", "warning"))

    # --- Declarations ---
    if not declarations.get("authorized_signatory_name"):
        issues.append(_err("DCL001", "Authorized signatory name is required.", "warning"))

    return issues
