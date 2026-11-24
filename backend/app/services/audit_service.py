"""Registrador de auditoría. Escribe en la transacción en curso: NO hace commit."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from app.core.logging import request_id_ctx
from app.models.audit_event import AuditEvent
from app.repositories.audit_repository import AuditRepository


def _utcnow() -> datetime:
    return datetime.now(UTC)


class AuditRecorder:
    def __init__(
        self, repository: AuditRepository, clock: Callable[[], datetime] = _utcnow
    ) -> None:
        self._repository = repository
        self._clock = clock

    def record(
        self,
        action: str,
        *,
        actor_id: uuid.UUID | None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        profile_id: uuid.UUID | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        # `request_id` del middleware (Fase 9): permite cruzar un evento de
        # auditoría con la línea de log de la petición. Se guarda en `detail`
        # (jsonb), así que no hace falta migración.
        correlation = request_id_ctx.get()
        if correlation:
            detail = {**(detail or {}), "request_id": correlation}
        self._repository.add(
            AuditEvent(
                id=uuid.uuid4(),
                occurred_at=self._clock(),
                actor_user_id=actor_id,
                action=str(action),
                resource_type=resource_type,
                resource_id=resource_id,
                profile_id=profile_id,
                detail=detail,
            )
        )