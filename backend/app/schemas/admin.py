from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.domain.identity import RoleName
from app.models.audit_event import AuditEvent
from app.schemas.auth import UserRead


class SetRolesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    roles: list[RoleName] = Field(min_length=1, max_length=3)


class UserPage(BaseModel):
    items: list[UserRead]
    total: int
    limit: int
    offset: int


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