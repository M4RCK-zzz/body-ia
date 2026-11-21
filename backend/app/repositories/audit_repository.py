from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from app.models.audit_event import AuditEvent


class AuditRepository(ABC):
    @abstractmethod
    def add(self, event: AuditEvent) -> None: ...

    @abstractmethod
    def list_page(
        self,
        *,
        limit: int,
        offset: int,
        action: str | None = None,
        actor_user_id: uuid.UUID | None = None,
    ) -> tuple[list[AuditEvent], int]: ...