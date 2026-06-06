from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import AuditLog


class AuditLogger:
    def __init__(self, session: Session) -> None:
        self.session = session

    def log(
        self,
        *,
        action: str,
        entity_type: str,
        entity_id: str | None = None,
        tenant_id: UUID | None = None,
        actor_user_id: UUID | None = None,
        route: str | None = None,
        method: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> AuditLog:
        entry = AuditLog(
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            route=route,
            method=method,
            details=details,
        )
        self.session.add(entry)
        return entry
