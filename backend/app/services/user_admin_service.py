from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime

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

    def list_users(
        self,
        *,
        limit: int,
        offset: int,
        search: str | None = None,
        role: str | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[User], int]:
        cleaned = (search or "").strip() or None
        return self._users.list_page(
            limit=limit, offset=offset, search=cleaned, role=role, is_active=is_active
        )

    def list_audit_events(
        self,
        *,
        limit: int,
        offset: int,
        action: str | None = None,
        actor_user_id: uuid.UUID | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> tuple[list[AuditEvent], int]:
        return self._audit_repository.list_page(
            limit=limit,
            offset=offset,
            action=action or None,
            actor_user_id=actor_user_id,
            since=since,
            until=until,
        )

    def audit_actions(self) -> list[str]:
        return self._audit_repository.distinct_actions()

    def resolve_actors(self, user_ids: Sequence[uuid.UUID | None]) -> dict[uuid.UUID, User]:
        """Etiquetas legibles de los actores de una página de auditoría.

        La tabla solo guarda `actor_user_id`; sin esto la UI mostraría UUIDs. Se
        resuelven en una sola consulta y solo para los ids presentes en la página.
        """
        wanted = [user_id for user_id in user_ids if user_id is not None]
        return self._users.get_many(wanted)

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