from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.audit_event import AuditEvent
from app.repositories.audit_repository import AuditRepository


class SqlAlchemyAuditRepository(AuditRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, event: AuditEvent) -> None:
        self._session.add(event)

    def list_page(
        self,
        *,
        limit: int,
        offset: int,
        action: str | None = None,
        actor_user_id: uuid.UUID | None = None,
    ) -> tuple[list[AuditEvent], int]:
        conditions = []
        if action:
            conditions.append(AuditEvent.action == action)
        if actor_user_id:
            conditions.append(AuditEvent.actor_user_id == actor_user_id)
        total = (
            self._session.scalar(select(func.count()).select_from(AuditEvent).where(*conditions))
            or 0
        )
        stmt = (
            select(AuditEvent)
            .where(*conditions)
            .order_by(AuditEvent.occurred_at.desc(), AuditEvent.id)
            .limit(limit)
            .offset(offset)
        )
        return list(self._session.scalars(stmt)), total