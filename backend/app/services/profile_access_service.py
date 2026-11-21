from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from app.core.clock import utcnow
from app.core.errors import BusinessRuleError, NotFoundError
from app.domain.access import AccessLevel
from app.domain.identity import AuditAction
from app.models.access import ProfileAccess
from app.models.identity import User
from app.repositories.access_repository import ProfileAccessRepository
from app.repositories.user_repository import UserRepository
from app.services.access_guard import AccessGuard
from app.services.audit_service import AuditRecorder
from app.services.auth_service import normalize_email
from app.services.ports import Transaction


class ProfileAccessService:
    def __init__(
        self,
        guard: AccessGuard,
        access: ProfileAccessRepository,
        users: UserRepository,
        audit: AuditRecorder,
        tx: Transaction,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        self._guard = guard
        self._access = access
        self._users = users
        self._audit = audit
        self._tx = tx
        self._clock = clock

    def list_access(self, actor: User, profile_id: UUID) -> list[ProfileAccess]:
        self._guard.require(profile_id, actor, AccessLevel.OWNER)
        return self._access.list_active(profile_id)

    def grant(self, actor: User, profile_id: UUID, email: str, level: AccessLevel) -> ProfileAccess:
        self._guard.require(profile_id, actor, AccessLevel.OWNER)
        if level == AccessLevel.OWNER:
            raise BusinessRuleError("La propiedad no se puede conceder ni transferir en esta fase.")
        target = self._users.get_by_email(normalize_email(email))
        if target is None or not target.is_active:
            raise NotFoundError("No existe una cuenta activa con ese correo.")
        if target.id == actor.id:
            raise BusinessRuleError("Ya eres el propietario de este expediente.")

        now = self._clock()
        current = self._access.get_active(profile_id, target.id)
        if current is not None:
            if current.level == level.value:
                return current
            current.revoked_at, current.revoked_by = now, actor.id
            self._access.save(current)
        grant = ProfileAccess(
            profile_id=profile_id,
            user_id=target.id,
            level=level.value,
            granted_by=actor.id,
            granted_at=now,
        )
        grant.user = target
        self._access.add(grant)
        self._audit.record(
            AuditAction.ACCESS_GRANTED,
            actor_id=actor.id,
            resource_type="profile_access",
            resource_id=str(grant.id),
            profile_id=profile_id,
            detail={
                "user_id": str(target.id),
                "level": level.value,
                "previous_level": current.level if current else None,
            },
        )
        self._tx.commit()
        return grant

    def revoke(self, actor: User, profile_id: UUID, user_id: UUID) -> None:
        self._guard.require(profile_id, actor, AccessLevel.OWNER)
        current = self._access.get_active(profile_id, user_id)
        if current is None:
            raise NotFoundError("Ese usuario no tiene acceso vigente a este expediente.")
        if current.level == AccessLevel.OWNER.value:
            raise BusinessRuleError("No se puede revocar el acceso del propietario.")
        current.revoked_at, current.revoked_by = self._clock(), actor.id
        self._access.save(current)
        self._audit.record(
            AuditAction.ACCESS_REVOKED,
            actor_id=actor.id,
            resource_type="profile_access",
            resource_id=str(current.id),
            profile_id=profile_id,
            detail={"user_id": str(user_id), "level": current.level},
        )
        self._tx.commit()