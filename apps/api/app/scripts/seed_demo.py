from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import Buyer, Membership, MembershipRole, Organization, Product, User
from app.schemas.compliance import ComplianceRequirementInput
from app.services.compliance_store import get_compliance_knowledge_store


def compliance_seed_records() -> list[ComplianceRequirementInput]:
    return [
        ComplianceRequirementInput(
            country="Canada",
            category="beverages",
            hsn_code="2009",
            product_keywords=["juice", "beverage", "mango", "fruit"],
            requirement_type="import_document",
            requirement_text=(
                "Importer-side Canadian customs entry is normally supported by a commercial invoice, "
                "packing list, bill of lading/air waybill, and product composition details for the food item."
            ),
            source_url="https://www.cbsa-asfc.gc.ca/import/guide-eng.html",
            source_name="Canada Border Services Agency importing commercial goods guide",
            source_authority_level="official",
            confidence_score=82,
            review_status="approved",
            reviewed_by="demo-seed",
            reviewed_at=datetime.now(UTC),
            notes="Seed/demo evidence for V0 workflow testing; verify official source before production reliance.",
        ),
        ComplianceRequirementInput(
            country="Canada",
            category="beverages",
            hsn_code="2009",
            product_keywords=["juice", "beverage", "fruit"],
            requirement_type="labeling",
            requirement_text=(
                "Retail prepackaged foods in Canada commonly require bilingual English/French labeling, "
                "including product identity, net quantity, dealer name/address, ingredient and allergen information "
                "where applicable; verify product-specific label rules before shipment."
            ),
            source_url="https://inspection.canada.ca/en/food-labels/labelling",
            source_name="Canadian Food Inspection Agency food labelling",
            source_authority_level="official",
            confidence_score=82,
            review_status="approved",
            reviewed_by="demo-seed",
            reviewed_at=datetime.now(UTC),
            notes="Seed/demo evidence for V0 workflow testing; verify official source before production reliance.",
        ),
        ComplianceRequirementInput(
            country="Canada",
            category="beverages",
            product_keywords=["food", "plant", "processed", "beverage"],
            requirement_type="inspection",
            requirement_text=(
                "Food and plant-origin consignments may be subject to CFIA import controls or inspection. "
                "Use AIRS/importer confirmation to verify whether phytosanitary, food safety, or other permits apply."
            ),
            source_url="https://inspection.canada.ca/en/importing-food-plants-animals",
            source_name="Canadian Food Inspection Agency import requirements",
            source_authority_level="official",
            confidence_score=76,
            review_status="approved",
            reviewed_by="demo-seed",
            reviewed_at=datetime.now(UTC),
            notes="Seed/demo evidence for V0 workflow testing; verify official source before production reliance.",
        ),
        ComplianceRequirementInput(
            country="Canada",
            category="dry fruits",
            product_keywords=["dry", "dried", "fruit", "nuts", "almond", "cashew", "raisin"],
            requirement_type="certificate",
            requirement_text=(
                "Dry fruits and nuts may require food safety evidence, origin/processing details, and possibly "
                "phytosanitary or fumigation support depending on product state and importer instructions."
            ),
            source_url="https://inspection.canada.ca/en/importing-food-plants-animals",
            source_name="Canadian Food Inspection Agency import requirements",
            source_authority_level="official",
            confidence_score=70,
            review_status="approved",
            reviewed_by="demo-seed",
            reviewed_at=datetime.now(UTC),
            notes="Seed/demo evidence for V0 workflow testing; verify official source before production reliance.",
        ),
        ComplianceRequirementInput(
            country="United Arab Emirates",
            category="dry fruits",
            product_keywords=["dry", "dried", "fruit", "dates", "nuts", "almond", "cashew"],
            requirement_type="import_document",
            requirement_text=(
                "UAE food imports commonly require importer-side food registration/clearance support plus "
                "commercial invoice, packing list, certificate of origin, transport document, and product label details."
            ),
            source_url="https://www.moccae.gov.ae/en/services/export-import-services.aspx",
            source_name="UAE Ministry of Climate Change and Environment import/export services",
            source_authority_level="official",
            confidence_score=72,
            review_status="approved",
            reviewed_by="demo-seed",
            reviewed_at=datetime.now(UTC),
            notes="Seed/demo evidence for V0 workflow testing; verify official source before production reliance.",
        ),
        ComplianceRequirementInput(
            country="United Arab Emirates",
            category="dry fruits",
            product_keywords=["dry", "dried", "fruit", "nuts"],
            requirement_type="labeling",
            requirement_text=(
                "Food labels for UAE retail sale should be checked for Arabic/English requirements, ingredients, "
                "country of origin, production/expiry dates, lot details, and any allergen or claim-specific wording."
            ),
            source_url="https://www.dm.gov.ae/municipality-business/food-safety/",
            source_name="Dubai Municipality food safety",
            source_authority_level="official",
            confidence_score=68,
            review_status="approved",
            reviewed_by="demo-seed",
            reviewed_at=datetime.now(UTC),
            notes="Seed/demo evidence for V0 workflow testing; verify official source before production reliance.",
        ),
        ComplianceRequirementInput(
            country="UK",
            category="textiles",
            product_keywords=["cotton", "shirt", "garment", "textile", "clothing"],
            requirement_type="labeling",
            requirement_text=(
                "Textile products placed on the UK market generally need accurate fibre composition information. "
                "Children/baby textiles and chemically treated goods may trigger additional safety checks."
            ),
            source_url="https://www.gov.uk/guidance/textile-products-labelling-and-fibre-composition",
            source_name="GOV.UK textile products labelling and fibre composition",
            source_authority_level="official",
            confidence_score=80,
            review_status="approved",
            reviewed_by="demo-seed",
            reviewed_at=datetime.now(UTC),
            notes="Seed/demo evidence for V0 workflow testing; verify official source before production reliance.",
        ),
        ComplianceRequirementInput(
            country="UK",
            category="textiles",
            product_keywords=["garment", "textile", "clothing"],
            requirement_type="restriction",
            requirement_text=(
                "Verify UK product safety, fibre composition, and any restricted chemical treatment obligations before "
                "retail shipment, especially for children or baby textiles."
            ),
            source_url="https://www.gov.uk/product-safety-for-businesses",
            source_name="GOV.UK product safety for businesses",
            source_authority_level="official",
            confidence_score=74,
            review_status="approved",
            reviewed_by="demo-seed",
            reviewed_at=datetime.now(UTC),
            notes="Seed/demo evidence for V0 workflow testing; verify official source before production reliance.",
        ),
    ]


def seed_compliance_data(organization: Organization) -> None:
    session = SessionLocal()
    try:
        store = get_compliance_knowledge_store(session=session, tenant_id=organization.id)
        store.ingest(compliance_seed_records())
        session.commit()
    finally:
        session.close()


def main() -> None:
    session = SessionLocal()
    try:
        existing = session.scalars(
            select(Organization).where(Organization.slug == "demo-exports")
        ).first()
        if existing is not None:
            seed_compliance_data(existing)
            print("Demo tenant already exists. Compliance seed data refreshed.")
            return

        organization = Organization(name="Demo Exports Pvt Ltd", slug="demo-exports")
        user = User(
            email="demo@example.com",
            password_hash=hash_password("DemoPassword123!"),
            full_name="Demo Owner",
        )
        session.add_all([organization, user])
        session.flush()

        membership = Membership(
            organization_id=organization.id,
            user_id=user.id,
            role=MembershipRole.OWNER,
        )
        buyers = [
            Buyer(
                tenant_id=organization.id,
                name="Nordic Retail AB",
                country="Sweden",
                contact_email="imports@nordicretail.example",
            ),
            Buyer(
                tenant_id=organization.id,
                name="Gulf Trade LLC",
                country="UAE",
                contact_email="trade@gulf.example",
            ),
        ]
        products = [
            Product(
                tenant_id=organization.id,
                sku="COT-001",
                name="Cotton Knit T-Shirt",
                hsn_code="610910",
                unit_of_measure="pcs",
            ),
            Product(
                tenant_id=organization.id,
                sku="AGR-002",
                name="Groundnut Kernel",
                hsn_code="120242",
                unit_of_measure="kg",
            ),
        ]
        session.add(membership)
        session.add_all([*buyers, *products])
        session.commit()
        seed_compliance_data(organization)
        print(f"Seeded demo tenant at {datetime.now(UTC).isoformat()}")
        print("Email: demo@example.com")
        print("Password: DemoPassword123!")
    finally:
        session.close()


if __name__ == "__main__":
    main()
