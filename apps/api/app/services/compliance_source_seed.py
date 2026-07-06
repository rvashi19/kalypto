# ruff: noqa: E501
"""Curated official-source registry seed for the Country Compliance Checker.

Every source URL here is on an official government/regulatory domain that is
already on the whitelist (see compliance_whitelist.py). Seeding is idempotent:
a source is skipped if the same (tenant, country, base_url) already exists.

These are official landing/hub pages for each authority. They are a vetted
starting set, not a claim of full country coverage.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ComplianceSourceRegistry

_ALL_FOOD = ["food/agri", "beverages", "spices", "dry fruits"]


@dataclass(frozen=True)
class OfficialSourceSeed:
    country: str
    product_categories: list[str]
    source_url: str
    source_type: str
    authority_name: str
    source_name: str
    authority_level: str = "official"
    refresh_frequency_days: int = 30
    is_active: bool = True
    notes: str | None = None


OFFICIAL_SOURCES: list[OfficialSourceSeed] = [
    OfficialSourceSeed(
        country="India",
        product_categories=["food/agri", "spices", "dry fruits"],
        source_url="https://apeda.gov.in/apedawebsite/",
        source_type="html",
        authority_name="APEDA",
        source_name="APEDA export authority portal",
        notes="Official APEDA portal for agricultural and processed food export references.",
    ),
    OfficialSourceSeed(
        country="India",
        product_categories=["textiles", "chemicals", "plastic/packaging", "food/agri"],
        source_url="https://www.dgft.gov.in/CP/",
        source_type="html",
        authority_name="Directorate General of Foreign Trade",
        source_name="DGFT official portal",
        notes="Official DGFT portal for export policy and trade notices.",
    ),
    OfficialSourceSeed(
        country="Canada",
        product_categories=_ALL_FOOD,
        source_url="https://inspection.canada.ca/importing-food-plants-or-animals/food-imports/eng/1376515896184/1376515983781",
        source_type="html",
        authority_name="Canadian Food Inspection Agency",
        source_name="CFIA import food requirements",
    ),
    OfficialSourceSeed(
        country="Canada",
        product_categories=_ALL_FOOD + ["textiles", "chemicals", "plastic/packaging"],
        source_url="https://www.cbsa-asfc.gc.ca/import/menu-eng.html",
        source_type="html",
        authority_name="Canada Border Services Agency",
        source_name="CBSA importing commercial goods",
    ),
    OfficialSourceSeed(
        country="USA",
        product_categories=_ALL_FOOD,
        source_url="https://www.fda.gov/food/importing-food-products-united-states/importing-food-products-overview",
        source_type="html",
        authority_name="US FDA",
        source_name="FDA importing food into the US",
    ),
    OfficialSourceSeed(
        country="USA",
        product_categories=["food/agri", "spices", "dry fruits"],
        source_url="https://www.aphis.usda.gov/plant-imports",
        source_type="html",
        authority_name="USDA APHIS",
        source_name="APHIS plant imports",
    ),
    OfficialSourceSeed(
        country="USA",
        product_categories=["textiles", "chemicals", "plastic/packaging", "food/agri"],
        source_url="https://www.cbp.gov/trade/basic-import-export",
        source_type="html",
        authority_name="US Customs and Border Protection",
        source_name="CBP importing into the US",
    ),
    OfficialSourceSeed(
        country="UK",
        product_categories=_ALL_FOOD + ["textiles", "chemicals", "plastic/packaging"],
        source_url="https://www.gov.uk/import-goods-into-uk",
        source_type="html",
        authority_name="UK Government",
        source_name="GOV.UK import goods into the UK",
    ),
    OfficialSourceSeed(
        country="Netherlands/EU",
        product_categories=_ALL_FOOD + ["textiles", "chemicals", "plastic/packaging"],
        source_url="https://trade.ec.europa.eu/access-to-markets/en/content/import-eu",
        source_type="html",
        authority_name="European Commission",
        source_name="EU Trade import into the EU",
    ),
    OfficialSourceSeed(
        country="Netherlands/EU",
        product_categories=["chemicals", "plastic/packaging", "textiles"],
        source_url="https://taxation-customs.ec.europa.eu/customs-4/customs-procedures-import-and-export/customs-procedures_en",
        source_type="html",
        authority_name="European Commission",
        source_name="EU Taxation and Customs importing goods",
    ),
    OfficialSourceSeed(
        country="United Arab Emirates",
        product_categories=_ALL_FOOD + ["textiles", "chemicals", "plastic/packaging"],
        source_url="https://www.moec.gov.ae/en/importing-and-exporting",
        source_type="html",
        authority_name="UAE Ministry of Economy",
        source_name="MoEC importing to the UAE",
    ),
    OfficialSourceSeed(
        country="United Arab Emirates",
        product_categories=_ALL_FOOD,
        source_url="https://www.adafsa.gov.ae/English/Pages/default.aspx",
        source_type="html",
        authority_name="Abu Dhabi Agriculture and Food Safety Authority",
        source_name="ADAFSA food import",
    ),
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
    updated = 0
    for seed in OFFICIAL_SOURCES:
        if (seed.country, seed.source_url) in existing:
            continue
        session.add(
            ComplianceSourceRegistry(
                tenant_id=tenant_id,
                country=seed.country,
                authority_name=seed.authority_name,
                source_name=seed.source_name,
                base_url=seed.source_url,
                allowed_domains_json=[],
                source_type=seed.source_type,
                authority_level=seed.authority_level,
                product_categories_json=seed.product_categories,
                is_active=seed.is_active,
                refresh_frequency_days=seed.refresh_frequency_days,
                notes=seed.notes,
            )
        )
        created += 1
    session.flush()
    return {
        "created": created,
        "updated": updated,
        "skipped": len(OFFICIAL_SOURCES) - created - updated,
        "total": len(OFFICIAL_SOURCES),
    }
