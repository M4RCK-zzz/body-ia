from __future__ import annotations

import uuid
from collections.abc import Sequence

from app.core.errors import BusinessRuleError, NotFoundError
from app.domain.identity import AuditAction, RoleName
from app.models.audit_event import AuditEvent
from app.models.identity import User
from app.repositories.audit_repository import AuditRepository
from app.repositories.user_repository import UserRepository
from app.services.audit_service import AuditRecorder
from app.services.ports import Transaction


class UserAdminService:
    def __init__(
        self,
        *,
        users: UserRepository,
        audit_repository: AuditRepository,
        audit: AuditRecorder,
        tx: Transaction,
    ) -> None:
        self._users = users
        self._audit_repository = audit_repository
        self._audit = audit
        self._tx = tx

    def list_users(self, *, limit: int, offset: int) -> tuple[list[User], int]:
        return self._users.list_page(limit=limit, offset=offset)

    def list_audit_events(
        self, *, limit: int, offset: int, action: str | None = None
    ) -> tuple[list[AuditEvent], int]:
        return self._audit_repository.list_page(limit=limit, offset=offset, action=action)

    def _get(self, user_id: uuid.UUID) -> User:
        user = self._users.get(user_id)
        if user is None:
            raise NotFoundError("Usuario no encontrado.")
        return user

    def set_roles(self, *, actor: User, user_id: uuid.UUID, roles: Sequence[RoleName]) -> User:
        target = self._get(user_id)
        wanted = sorted({str(r) for r in roles})
        if not wanted:
            raise BusinessRuleError("Un usuario debe tener al menos un rol.")
        if target.id == actor.id and RoleName.ADMIN.value not in wanted:
            raise BusinessRuleError("No puedes quitarte a ti mismo el rol de administrador.")
        before = target.role_names
        self._users.set_roles(target, wanted)
        self._audit.record(
            AuditAction.ROLES_CHANGED,
            actor_id=actor.id,
            resource_type="user",
            resource_id=str(target.id),
            detail={"before": before, "after": wanted},
        )
        self._tx.commit()
        return target

    def set_active(self, *, actor: User, user_id: uuid.UUID, active: bool) -> User:
        target = self._get(user_id)
        if target.id == actor.id and not active:
            raise BusinessRuleError("No puedes desactivar tu propia cuenta.")
        if target.is_active != active:
            target.is_active = active
            self._audit.record(
                AuditAction.USER_ACTIVATED if active else AuditAction.USER_DEACTIVATED,
                actor_id=actor.id,
                resource_type="user",
                resource_id=str(target.id),
            )
            self._tx.commit()
        return target