from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import Buyer, Membership, MembershipRole, Organization, Product, User


def main() -> None:
    session = SessionLocal()
    try:
        existing = session.scalars(select(Organization).where(Organization.slug == "demo-exports")).first()
        if existing is not None:
            print("Demo tenant already exists.")
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
        print(f"Seeded demo tenant at {datetime.now(UTC).isoformat()}")
        print("Email: demo@example.com")
        print("Password: DemoPassword123!")
    finally:
        session.close()


if __name__ == "__main__":
    main()
