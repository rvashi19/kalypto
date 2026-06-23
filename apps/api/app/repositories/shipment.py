from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models import ExportShipment, ShipmentDocument
from app.repositories.base import TenantRepository
from app.services.audit import AuditLogger


class ShipmentRepository(TenantRepository[ExportShipment]):
    def __init__(
        self, *, session: Session, tenant_id: UUID, actor_user_id: UUID | None = None
    ) -> None:
        super().__init__(
            session=session, model=ExportShipment, tenant_id=tenant_id, actor_user_id=actor_user_id
        )

    def delete(self, shipment: ExportShipment) -> None:
        self.audit.log(
            action="repository.delete",
            entity_type="ExportShipment",
            entity_id=str(shipment.id),
            tenant_id=self.tenant_id,
            actor_user_id=self.actor_user_id,
        )
        self.session.delete(shipment)


class DocumentRepository(TenantRepository[ShipmentDocument]):
    def __init__(
        self, *, session: Session, tenant_id: UUID, actor_user_id: UUID | None = None
    ) -> None:
        super().__init__(
            session=session,
            model=ShipmentDocument,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
        )

    def list_for_shipment(self, shipment_id: UUID) -> list[ShipmentDocument]:
        rows = self.session.scalars(
            self.scoped_query().where(ShipmentDocument.shipment_id == shipment_id)
        ).all()
        AuditLogger(self.session).log(
            action="repository.list_for_shipment",
            entity_type="ShipmentDocument",
            entity_id=str(shipment_id),
            tenant_id=self.tenant_id,
            actor_user_id=self.actor_user_id,
            details={"count": len(rows)},
        )
        return list(rows)

    def delete(self, doc: ShipmentDocument) -> None:
        self.audit.log(
            action="repository.delete",
            entity_type="ShipmentDocument",
            entity_id=str(doc.id),
            tenant_id=self.tenant_id,
            actor_user_id=self.actor_user_id,
        )
        self.session.delete(doc)
