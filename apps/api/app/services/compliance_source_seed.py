# ruff: noqa: E501
"""Curated official-source registry seed for the Country Compliance Checker.

Every base_url here is on an official government/regulatory domain that is already
on the whitelist (see compliance_whitelist.py). Seeding is idempotent: a source is
skipped if the same (tenant, country, base_url) already exists.

These are landing/hub pages for the relevant authority — the retrieval job fetches
them and the AI assistant extracts candidate requirement cards (pending_review).
They are starting points for operators, not an authoritative requirement list.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ComplianceSourceRegistry

_ALL_FOOD = ["food/agri", "beverages", "spices", "dry fruits"]

# (country, authority_name, source_name, base_url, source_type, product_categories)
OFFICIAL_SOURCES: list[tuple[str, str, str, str, str, list[str]]] = [
    # ── Canada ──
    ("Canada", "Canadian Food Inspection Agency", "CFIA — import food requirements",
     "https://inspection.canada.ca/importing-food-plants-or-animals/food-imports/eng/1376515896184/1376515983781",
     "html", _ALL_FOOD),
    ("Canada", "Canada Border Services Agency", "CBSA — importing commercial goods",
     "https://www.cbsa-asfc.gc.ca/import/menu-eng.html", "html", _ALL_FOOD + ["textiles", "chemicals", "plastic/packaging"]),
    # ── USA ──
    ("USA", "US FDA", "FDA — importing food into the US",
     "https://www.fda.gov/food/importing-food-products-united-states/importing-food-products-overview",
     "html", _ALL_FOOD),
    ("USA", "USDA APHIS", "APHIS — plant imports",
     "https://www.aphis.usda.gov/plant-imports", "html", ["food/agri", "spices", "dry fruits"]),
    ("USA", "US Customs and Border Protection", "CBP — importing into the US",
     "https://www.cbp.gov/trade/basic-import-export", "html", ["textiles", "chemicals", "plastic/packaging", "food/agri"]),
    # ── UK ──
    ("UK", "UK Government", "GOV.UK — import goods into the UK",
     "https://www.gov.uk/import-goods-into-uk", "html", _ALL_FOOD + ["textiles", "chemicals", "plastic/packaging"]),
    # ── Netherlands/EU ──
    ("Netherlands/EU", "European Commission", "EU Trade — import into the EU",
     "https://trade.ec.europa.eu/access-to-markets/en/content/import-eu", "html", _ALL_FOOD + ["textiles", "chemicals", "plastic/packaging"]),
    ("Netherlands/EU", "European Commission", "EU Taxation & Customs — importing goods",
     "https://taxation-customs.ec.europa.eu/customs-4/customs-procedures-import-and-export/customs-procedures_en",
     "html", ["chemicals", "plastic/packaging", "textiles"]),
    # ── United Arab Emirates ──
    ("United Arab Emirates", "UAE Ministry of Economy", "MoEC — importing to the UAE",
     "https://www.moec.gov.ae/en/importing-and-exporting", "html", _ALL_FOOD + ["textiles", "chemicals", "plastic/packaging"]),
    ("United Arab Emirates", "Abu Dhabi Agriculture & Food Safety Authority", "ADAFSA — food import",
     "https://www.adafsa.gov.ae/English/Pages/default.aspx", "html", _ALL_FOOD),
]


def seed_official_sources(session: Session, tenant_id: UUID) -> dict[str, int]:
    """Idempotently register the curated official sources for a tenant."""
    existing = {
        (row.country, row.base_url)
        for row in session.scalars(
            select(ComplianceSourceRegistry).where(
                ComplianceSourceRegistry.tenant_id == tenant_id
            )
        ).all()
    }
    created = 0
    for country, authority, name, url, source_type, categories in OFFICIAL_SOURCES:
        if (country, url) in existing:
            continue
        session.add(
            ComplianceSourceRegistry(
                tenant_id=tenant_id,
                country=country,
                authority_name=authority,
                source_name=name,
                base_url=url,
                allowed_domains_json=[],
                source_type=source_type,
                product_categories_json=categories,
                is_active=True,
                refresh_frequency_days=30,
            )
        )
        created += 1
    session.flush()
    return {"created": created, "skipped": len(OFFICIAL_SOURCES) - created, "total": len(OFFICIAL_SOURCES)}
