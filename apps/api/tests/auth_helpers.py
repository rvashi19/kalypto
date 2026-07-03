from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.core.security import create_access_token, hash_password
from app.main import app
from app.models import Membership, MembershipRole, Organization, User, UserStatus


def authenticated_client(
    session,
    *,
    email: str,
    organization_name: str = "Test Exports",
    full_name: str = "Test Owner",
    role: MembershipRole = MembershipRole.OWNER,
) -> tuple[TestClient, dict[str, str], str]:
    organization = Organization(
        name=organization_name,
        slug=f"{organization_name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}",
    )
    user = User(
        email=email,
        password_hash=hash_password("StrongPassword123!"),
        full_name=full_name,
        email_verified_at=datetime.now(UTC),
        status=UserStatus.ACTIVE,
    )
    session.add_all([organization, user])
    session.flush()
    session.add(Membership(organization_id=organization.id, user_id=user.id, role=role))
    session.commit()
    token, _, _ = create_access_token(
        user_id=user.id,
        tenant_id=organization.id,
        role=role.value,
    )
    return TestClient(app), {"Authorization": f"Bearer {token}"}, token
