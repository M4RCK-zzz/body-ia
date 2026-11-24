from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.domain.identity import RoleName
from app.models.audit_event import AuditEvent
from app.models.identity import User
from app.schemas.auth import UserRead


class SetRolesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    roles: list[RoleName] = Field(min_length=1, max_length=3)


class UserPage(BaseModel):
    items: list[UserRead]
    total: int
    limit: int
    offset: int
    # `admin` se incluye porque el panel gestiona cuentas y roles, no expedientes:
    # el backend sigue negando el acceso implícito a datos corporales.
    can_manage: bool = True


class UserSummary(BaseModel):
    """Identidad mínima de un actor de auditoría (sin datos de acceso).

    La tabla `audit_events` guarda solo `actor_user_id`; el panel resuelve los
    nombres de la página visible para no mostrar UUIDs ilegibles.
    """

    id: uuid.UUID
    email: EmailStr
    full_name: str

    @classmethod
    def from_user(cls, user: User) -> UserSummary:
        return cls(id=user.id, email=user.email, full_name=user.full_name)


class AuditEventRead(BaseModel):
    id: uuid.UUID
    occurred_at: datetime
    actor_user_id: uuid.UUID | None
    action: str
    resource_type: str | None
    resource_id: str | None
    profile_id: uuid.UUID | None
    detail: dict[str, Any] | None

    @classmethod
    def from_event(cls, event: AuditEvent) -> AuditEventRead:
        return cls(
            id=event.id,
            occurred_at=event.occurred_at,
            actor_user_id=event.actor_user_id,
            action=event.action,
            resource_type=event.resource_type,
            resource_id=event.resource_id,
            profile_id=event.profile_id,
            detail=event.detail,
        )


class AuditEventPage(BaseModel):
    items: list[AuditEventRead]
    total: int
    limit: int
    offset: int
    actors: list[UserSummary] = Field(
        default_factory=list, description="Actores distintos presentes en esta página"
    )


class AuditActionsResponse(BaseModel):
    actions: list[str] = Field(default_factory=list)
