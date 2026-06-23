from __future__ import annotations

from typing import Any, Generic, Protocol, TypeVar, cast
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.services.audit import AuditLogger


class TenantRecord(Protocol):
    id: UUID
    tenant_id: UUID


TenantModelT = TypeVar("TenantModelT", bound=TenantRecord)


class TenantRepository(Generic[TenantModelT]):
    def __init__(
        self,
        *,
        session: Session,
        model: type[TenantModelT],
        tenant_id: UUID,
        actor_user_id: UUID | None = None,
    ) -> None:
        self.session = session
        self.model = model
        self.tenant_id = tenant_id
        self.actor_user_id = actor_user_id
        self.audit = AuditLogger(session)

    def scoped_query(self) -> Select[tuple[TenantModelT]]:
        model = cast(Any, self.model)
        return select(self.model).where(model.tenant_id == self.tenant_id)

    def list(self) -> list[TenantModelT]:
        rows = self.session.scalars(self.scoped_query()).all()
        self.audit.log(
            action="repository.list",
            entity_type=self.model.__name__,
            tenant_id=self.tenant_id,
            actor_user_id=self.actor_user_id,
            details={"count": len(rows)},
        )
        return list(rows)

    def get(self, entity_id: UUID) -> TenantModelT | None:
        row = self.session.scalars(
            self.scoped_query().where(cast(Any, self.model).id == entity_id),
        ).first()
        self.audit.log(
            action="repository.get",
            entity_type=self.model.__name__,
            entity_id=str(entity_id),
            tenant_id=self.tenant_id,
            actor_user_id=self.actor_user_id,
            details={"found": row is not None},
        )
        return row

    def add(self, instance: TenantModelT) -> TenantModelT:
        if instance.tenant_id != self.tenant_id:
            raise ValueError("Cross-tenant writes are blocked at the repository layer.")
        self.session.add(instance)
        self.audit.log(
            action="repository.add",
            entity_type=self.model.__name__,
            entity_id=str(instance.id),
            tenant_id=self.tenant_id,
            actor_user_id=self.actor_user_id,
        )
        return instance