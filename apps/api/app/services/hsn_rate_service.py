"""Tenant-scoped incentive rate lookup.

Rates are operator-seeded evidence, never application constants or model output.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.services.rate_governance import approved_current_rate_rows, latest_rate_by_scheme

DISCLAIMER = (
    "Decision-support only. Verify the HSN classification, eligibility, and current rate "
    "with your CHA/customs broker before filing."
)


def lookup_rates(
    *,
    session: Session,
    tenant_id: UUID,
    hsn_code: str,
    fob_value: float | None,
) -> dict[str, object]:
    cleaned_hsn = "".join(character for character in hsn_code if character.isdigit())
    if len(cleaned_hsn) < 4:
        return {
            "found": False,
            "hsn_code": cleaned_hsn or hsn_code,
            "message": "Enter at least four HSN digits.",
            "disclaimer": DISCLAIMER,
        }

    rows = approved_current_rate_rows(
        session=session,
        tenant_id=tenant_id,
        hsn_code=cleaned_hsn,
    )
    if not rows:
        return {
            "found": False,
            "hsn_code": cleaned_hsn,
            "message": (
                "No operator-verified rate is available for this HSN. "
                "Import and approve the current official rate schedule before showing values."
            ),
            "disclaimer": DISCLAIMER,
        }

    latest_by_scheme = {
        row.scheme.strip().lower(): row for row in latest_rate_by_scheme(rows)
    }

    def rate_for(*names: str) -> float | None:
        for name in names:
            row = latest_by_scheme.get(name)
            if row is not None:
                return float(row.rate)
        return None

    matched_hsn = max((row.hsn for row in latest_by_scheme.values()), key=len)
    evidence = [
        {
            "scheme": row.scheme,
            "rate": float(row.rate),
            "source": row.source,
            "source_url": row.source_url,
            "effective_date": row.effective_date.isoformat(),
            "version_stamp": row.version_stamp,
            "confidence": row.confidence,
            "review_status": row.review_status,
            "reviewed_by": row.reviewed_by,
            "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
            "expires_at": row.expires_at.isoformat() if row.expires_at else None,
            "notes": row.notes,
        }
        for row in latest_by_scheme.values()
    ]

    result: dict[str, object] = {
        "found": True,
        "hsn_code": cleaned_hsn,
        "hsn_prefix_matched": matched_hsn,
        "description": "Operator-verified incentive rate records",
        "duty_drawback_rate": rate_for("duty drawback", "drawback", "drawback air"),
        "rodtep_rate": rate_for("rodtep"),
        "rosctl_rate": rate_for("rosctl"),
        "notes": "Rates shown are sourced from the tenant's versioned rate table.",
        "rate_evidence": evidence,
        "disclaimer": DISCLAIMER,
        "estimated_amounts_inr": None,
    }

    if fob_value is not None and fob_value > 0:
        fob = Decimal(str(fob_value))
        estimates: dict[str, float] = {}
        for scheme, row in latest_by_scheme.items():
            estimates[scheme.replace(" ", "_")] = float(
                (fob * Decimal(str(row.rate)) / Decimal("100")).quantize(Decimal("0.01"))
            )
        result["estimated_amounts_inr"] = estimates or None
        result["fob_inr_basis"] = float(fob)
        result["exchange_rate_note"] = (
            "The entered FOB value is treated as INR. Currency conversion is not guessed."
        )

    return result
