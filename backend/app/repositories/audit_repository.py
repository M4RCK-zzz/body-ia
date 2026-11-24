from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import datetime

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
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> tuple[list[AuditEvent], int]: ...

    @abstractmethod
    def distinct_actions(self) -> list[str]:
        """Acciones presentes en la tabla, para el desplegable de filtros."""
