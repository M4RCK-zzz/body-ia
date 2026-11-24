from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_user_admin_service
from app.api.security import AdminUser
from app.domain.identity import RoleName
from app.schemas.admin import (
    AuditActionsResponse,
    AuditEventPage,
    AuditEventRead,
    SetRolesRequest,
    UserPage,
    UserSummary,
)
from app.schemas.auth import UserRead
from app.services.user_admin_service import UserAdminService

router = APIRouter(prefix="/admin", tags=["Administración"])

AdminServiceDep = Annotated[UserAdminService, Depends(get_user_admin_service)]


@router.get("/users", response_model=UserPage)
def list_users(
    _admin: AdminUser,
    service: AdminServiceDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    search: Annotated[str | None, Query(max_length=120)] = None,
    role: RoleName | None = None,
    is_active: bool | None = None,
) -> UserPage:
    users, total = service.list_users(
        limit=limit, offset=offset, search=search, role=role, is_active=is_active
    )
    return UserPage(
        items=[UserRead.from_user(u) for u in users], total=total, limit=limit, offset=offset
    )


@router.put("/users/{user_id}/roles", response_model=UserRead)
def set_roles(
    user_id: uuid.UUID, payload: SetRolesRequest, admin: AdminUser, service: AdminServiceDep
) -> UserRead:
    return UserRead.from_user(service.set_roles(actor=admin, user_id=user_id, roles=payload.roles))


@router.post("/users/{user_id}/activate", response_model=UserRead)
def activate_user(user_id: uuid.UUID, admin: AdminUser, service: AdminServiceDep) -> UserRead:
    return UserRead.from_user(service.set_active(actor=admin, user_id=user_id, active=True))


@router.post("/users/{user_id}/deactivate", response_model=UserRead)
def deactivate_user(user_id: uuid.UUID, admin: AdminUser, service: AdminServiceDep) -> UserRead:
    return UserRead.from_user(service.set_active(actor=admin, user_id=user_id, active=False))


@router.get("/audit-actions", response_model=AuditActionsResponse)
def list_audit_actions(_admin: AdminUser, service: AdminServiceDep) -> AuditActionsResponse:
    """Acciones presentes en `audit_events`, para el filtro del panel."""
    return AuditActionsResponse(actions=service.audit_actions())


@router.get("/audit-events", response_model=AuditEventPage)
def list_audit_events(
    _admin: AdminUser,
    service: AdminServiceDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    action: Annotated[str | None, Query(max_length=60)] = None,
    actor_user_id: uuid.UUID | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
) -> AuditEventPage:
    events, total = service.list_audit_events(
        limit=limit,
        offset=offset,
        action=action,
        actor_user_id=actor_user_id,
        since=since,
        until=until,
    )
    actors = service.resolve_actors([event.actor_user_id for event in events])
    return AuditEventPage(
        items=[AuditEventRead.from_event(e) for e in events],
        total=total,
        limit=limit,
        offset=offset,
        actors=[UserSummary.from_user(u) for u in actors.values()],
    )
