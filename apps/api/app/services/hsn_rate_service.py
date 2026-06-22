"""HSN code incentive rate lookup — Duty Drawback and RoDTEP static tables."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HsnRateEntry:
    hsn_prefix: str
    description: str
    duty_drawback_rate: float | None
    rodtep_rate: float | None
    rosctl_rate: float | None
    notes: str = ""


_RATE_TABLE: list[HsnRateEntry] = [
    # Chapter 09 — Spices
    HsnRateEntry("0904", "Peppers; capsicum / pimento", 1.2, 0.5, None, "Includes dried chillies"),
    HsnRateEntry("0901", "Coffee", 0.5, 0.3, None),
    HsnRateEntry("0902", "Tea", 0.5, 0.5, None),
    HsnRateEntry("09", "Spices & coffee", 1.0, 0.5, None),
    # Chapter 08 — Edible fruits
    HsnRateEntry("0803", "Bananas & plantains", 0.5, 0.3, None),
    HsnRateEntry("0806", "Grapes (fresh/dried)", 0.5, 0.3, None),
    HsnRateEntry("0808", "Apples & pears", 0.5, 0.3, None),
    HsnRateEntry("08", "Edible fruits and nuts", 0.5, 0.3, None),
    # Chapter 03 — Fish and seafood
    HsnRateEntry("0302", "Fish, fresh or chilled", 1.0, 0.5, None),
    HsnRateEntry("0303", "Fish, frozen", 1.5, 0.75, None),
    HsnRateEntry("0306", "Crustaceans (shrimp/prawn)", 2.0, 1.0, None),
    HsnRateEntry("03", "Fish and seafood", 1.5, 0.75, None),
    # Chapter 26 — Ores
    HsnRateEntry("26", "Ores, slag and ash", 0.0, 0.0, None, "Generally not eligible for drawback"),
    # Chapter 27 — Mineral fuels
    HsnRateEntry("27", "Mineral fuels, oils", 0.0, 0.0, None, "Export of petroleum products — check DFIA"),
    # Chapter 28-29 — Chemicals
    HsnRateEntry("2801", "Fluorine, chlorine, bromine", 1.5, 0.5, None),
    HsnRateEntry("2901", "Acyclic hydrocarbons", 1.0, 0.5, None),
    HsnRateEntry("2941", "Antibiotics", 2.0, 1.0, None),
    HsnRateEntry("28", "Inorganic chemicals", 1.5, 0.5, None),
    HsnRateEntry("29", "Organic chemicals", 1.5, 0.5, None),
    # Chapter 30 — Pharma
    HsnRateEntry("3004", "Medicaments (formulations)", 2.5, 1.0, None, "CDSCO NOC required for most destinations"),
    HsnRateEntry("30", "Pharmaceutical products", 2.0, 0.75, None),
    # Chapter 33 — Cosmetics
    HsnRateEntry("3304", "Beauty / make-up preparations", 1.5, 0.7, None),
    HsnRateEntry("33", "Essential oils & cosmetics", 1.5, 0.7, None),
    # Chapter 39 — Plastics
    HsnRateEntry("3920", "Plates / sheets of plastics", 1.0, 0.5, None),
    HsnRateEntry("39", "Plastics and articles thereof", 1.0, 0.5, None),
    # Chapter 40 — Rubber
    HsnRateEntry("4011", "Pneumatic tyres (new)", 1.5, 0.7, None),
    HsnRateEntry("40", "Rubber and articles thereof", 1.0, 0.5, None),
    # Chapters 50-63 — Textiles (RoSCTL eligible)
    HsnRateEntry("5208", "Woven cotton fabrics", 1.5, 0.7, 3.0, "RoSCTL eligible"),
    HsnRateEntry("6101", "Men's overcoats (knitted)", 1.5, 0.7, 3.5, "RoSCTL eligible"),
    HsnRateEntry("6201", "Men's overcoats (woven)", 1.5, 0.7, 3.5, "RoSCTL eligible"),
    HsnRateEntry("6301", "Blankets and travelling rugs", 1.5, 0.7, 3.0, "RoSCTL eligible"),
    HsnRateEntry("50", "Silk", 1.5, 0.5, 3.0, "RoSCTL eligible"),
    HsnRateEntry("51", "Wool", 1.5, 0.5, 3.0, "RoSCTL eligible"),
    HsnRateEntry("52", "Cotton", 1.5, 0.7, 3.5, "RoSCTL eligible"),
    HsnRateEntry("53", "Vegetable textile fibres", 1.5, 0.5, 3.0, "RoSCTL eligible"),
    HsnRateEntry("54", "Man-made filaments", 1.5, 0.7, 3.5, "RoSCTL eligible"),
    HsnRateEntry("55", "Man-made staple fibres", 1.5, 0.7, 3.5, "RoSCTL eligible"),
    HsnRateEntry("56", "Wadding, felt, nonwovens", 1.0, 0.5, 2.5, "RoSCTL eligible"),
    HsnRateEntry("57", "Carpets and floor coverings", 1.5, 0.5, 3.0, "RoSCTL eligible"),
    HsnRateEntry("58", "Special woven fabrics", 1.5, 0.5, 3.0, "RoSCTL eligible"),
    HsnRateEntry("59", "Impregnated textile fabrics", 1.0, 0.5, 2.5, "RoSCTL eligible"),
    HsnRateEntry("60", "Knitted / crocheted fabrics", 1.5, 0.7, 3.5, "RoSCTL eligible"),
    HsnRateEntry("61", "Knitted / crocheted apparel", 1.5, 0.7, 4.0, "RoSCTL eligible"),
    HsnRateEntry("62", "Woven apparel", 1.5, 0.7, 4.0, "RoSCTL eligible"),
    HsnRateEntry("63", "Other made-up textile articles", 1.5, 0.7, 3.5, "RoSCTL eligible"),
    # Chapter 64 — Footwear
    HsnRateEntry("6401", "Waterproof footwear", 1.0, 0.5, None),
    HsnRateEntry("64", "Footwear, gaiters", 1.0, 0.5, None),
    # Chapter 72-73 — Iron and steel
    HsnRateEntry("7208", "Flat-rolled iron/non-alloy steel", 0.5, 0.3, None),
    HsnRateEntry("7304", "Tubes and pipes of iron/steel", 1.0, 0.5, None),
    HsnRateEntry("72", "Iron and steel", 0.5, 0.3, None),
    HsnRateEntry("73", "Articles of iron or steel", 1.0, 0.5, None),
    # Chapter 76 — Aluminium
    HsnRateEntry("76", "Aluminium and articles", 1.0, 0.5, None),
    # Chapter 84 — Machinery
    HsnRateEntry("8413", "Pumps for liquids", 1.5, 0.75, None),
    HsnRateEntry("8471", "Computers", 0.0, 0.3, None, "EPCG commonly used"),
    HsnRateEntry("8479", "Machines / mechanical appliances", 1.5, 0.75, None),
    HsnRateEntry("84", "Nuclear reactors, boilers, machinery", 1.5, 0.75, None),
    # Chapter 85 — Electrical
    HsnRateEntry("8517", "Telephones / smartphones", 0.0, 0.5, None),
    HsnRateEntry("8541", "Semiconductor devices", 0.5, 0.3, None),
    HsnRateEntry("85", "Electrical machinery and equipment", 1.0, 0.5, None),
    # Chapter 87 — Vehicles
    HsnRateEntry("8703", "Motor cars / passenger vehicles", 0.5, 0.3, None),
    HsnRateEntry("8714", "Parts for motorcycles", 1.5, 0.75, None),
    HsnRateEntry("87", "Vehicles other than railway", 0.5, 0.3, None),
    # Chapter 90 — Optical / medical
    HsnRateEntry("90", "Optical, photographic, medical instruments", 1.5, 0.75, None),
    # Chapter 71 — Gems and jewellery
    HsnRateEntry("7113", "Articles of jewellery", 2.0, 1.0, None, "Gems & Jewellery export promotion — verify with GJEPC"),
    HsnRateEntry("71", "Pearls, precious stones, metals", 2.0, 1.0, None),
    # Chapter 10 — Cereals
    HsnRateEntry("1006", "Rice", 0.0, 0.0, None, "Rice export may be restricted — check current MEP"),
    HsnRateEntry("1001", "Wheat", 0.0, 0.0, None, "Wheat export currently prohibited — verify"),
    HsnRateEntry("10", "Cereals", 0.5, 0.3, None),
    # Chapter 17 — Sugar
    HsnRateEntry("1701", "Cane or beet sugar", 0.0, 0.0, None, "Sugar export subject to MEP and quota"),
    HsnRateEntry("17", "Sugars and sugar confectionery", 0.5, 0.3, None),
    # Chapter 41 — Leather
    HsnRateEntry("41", "Raw hides, skins and leather", 1.5, 0.75, None),
    # Chapter 42 — Leather goods
    HsnRateEntry("4202", "Trunks, handbags, wallets", 1.5, 0.75, None),
    HsnRateEntry("42", "Articles of leather", 1.5, 0.75, None),
    # Chapter 94 — Furniture
    HsnRateEntry("9401", "Seats and parts thereof", 1.5, 0.75, None),
    HsnRateEntry("9403", "Other furniture", 1.5, 0.75, None),
    HsnRateEntry("94", "Furniture, bedding, lamps", 1.5, 0.75, None),
]


def lookup(hsn_code: str) -> HsnRateEntry | None:
    """Return the best-matching rate entry for an HSN code (most-specific first)."""
    cleaned = hsn_code.strip().replace(" ", "").replace(".", "")
    for length in (8, 6, 4, 2):
        prefix = cleaned[:length]
        for entry in _RATE_TABLE:
            if entry.hsn_prefix == prefix:
                return entry
    return None


def estimate_incentives(hsn_code: str, fob_value_usd: float | None) -> dict:
    """Return incentive rate data and estimated INR amounts for a given HSN and FOB value."""
    entry = lookup(hsn_code)
    if entry is None:
        return {
            "found": False,
            "hsn_code": hsn_code,
            "message": "No rate data found for this HSN code. Rates may still apply — consult your CHA.",
        }

    result: dict = {
        "found": True,
        "hsn_code": hsn_code,
        "hsn_prefix_matched": entry.hsn_prefix,
        "description": entry.description,
        "duty_drawback_rate": entry.duty_drawback_rate,
        "rodtep_rate": entry.rodtep_rate,
        "rosctl_rate": entry.rosctl_rate,
        "notes": entry.notes,
        "estimated_amounts_inr": None,
    }

    if fob_value_usd and fob_value_usd > 0:
        fob_inr = fob_value_usd * 84
        amounts: dict[str, float] = {}
        if entry.duty_drawback_rate:
            amounts["duty_drawback"] = round(fob_inr * entry.duty_drawback_rate / 100, 2)
        if entry.rodtep_rate:
            amounts["rodtep"] = round(fob_inr * entry.rodtep_rate / 100, 2)
        if entry.rosctl_rate:
            amounts["rosctl"] = round(fob_inr * entry.rosctl_rate / 100, 2)
        if amounts:
            result["estimated_amounts_inr"] = amounts
            result["fob_inr_basis"] = round(fob_inr, 0)
            result["exchange_rate_note"] = "Exchange rate ≈ ₹84/USD (indicative). Use actual rate on shipment date."

    return result
