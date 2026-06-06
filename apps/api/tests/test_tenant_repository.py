from app.models import Buyer, Organization
from app.repositories.base import TenantRepository


def test_tenant_repository_blocks_cross_tenant_reads_and_writes(session) -> None:
    first_org = Organization(name="First Org", slug="first-org")
    second_org = Organization(name="Second Org", slug="second-org")
    session.add_all([first_org, second_org])
    session.flush()

    first_buyer = Buyer(tenant_id=first_org.id, name="Alpha Buyer", country="IN")
    second_buyer = Buyer(tenant_id=second_org.id, name="Beta Buyer", country="US")
    session.add_all([first_buyer, second_buyer])
    session.commit()

    repository = TenantRepository(session=session, model=Buyer, tenant_id=first_org.id)

    assert repository.get(first_buyer.id) is not None
    assert repository.get(second_buyer.id) is None
    assert [buyer.id for buyer in repository.list()] == [first_buyer.id]

    rogue_buyer = Buyer(tenant_id=second_org.id, name="Rogue Buyer", country="AE")

    try:
        repository.add(rogue_buyer)
    except ValueError as error:
        assert "Cross-tenant writes are blocked" in str(error)
    else:
        raise AssertionError("Expected the repository to block a cross-tenant write.")
