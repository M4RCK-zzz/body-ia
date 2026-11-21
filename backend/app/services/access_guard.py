from __future__ import annotations

from uuid import UUID

from app.core.errors import NotFoundError
from app.core.security_errors import PermissionDeniedError
from app.domain.access import ACCESS_LABELS, AccessLevel, level_allows
from app.domain.identity import AuditAction
from app.models.access import ProfileAccess
from app.models.identity import User
from app.models.profile import Profile
from app.repositories.access_repository import ProfileAccessRepository
from app.repositories.profile_repository import ProfileRepository
from app.services.audit_service import AuditRecorder
from app.services.ports import Transaction

_NOT_FOUND = "Expediente no encontrado."


class AccessGuard:
    """Sin acceso vigente => 404 (no revela existencia). Nivel insuficiente => 403.
    `admin` no tiene acceso implícito. Los rechazos se auditan (si el expediente existe)."""

    def __init__(
        self,
        profiles: ProfileRepository,
        access: ProfileAccessRepository,
        audit: AuditRecorder,
        tx: Transaction,
    ) -> None:
        self._profiles = profiles
        self._access = access
        self._audit = audit
        self._tx = tx

    def require(
        self, profile_id: UUID, actor: User, minimum: AccessLevel = AccessLevel.VIEWER
    ) -> tuple[Profile, ProfileAccess]:
        profile = self._profiles.get(profile_id)
        if profile is None:
            raise NotFoundError(_NOT_FOUND)
        grant = self._access.get_active(profile_id, actor.id)
        if grant is None:
            self._deny(actor, profile_id, "no_access", minimum, None)
            raise NotFoundError(_NOT_FOUND)
        if not level_allows(grant.level, minimum):
            self._deny(actor, profile_id, "insufficient_level", minimum, grant.level)
            label = ACCESS_LABELS[AccessLevel(grant.level)]
            raise PermissionDeniedError(
                f"Tu nivel de acceso ({label}) no permite esta acción.",
                code="insufficient_access",
            )
        return profile, grant

    def _deny(
        self, actor: User, profile_id: UUID, reason: str, required: AccessLevel, actual: str | None
    ) -> None:
        self._audit.record(
            AuditAction.ACCESS_DENIED,
            actor_id=actor.id,
            resource_type="profile",
            resource_id=str(profile_id),
            profile_id=profile_id,
            detail={"reason": reason, "required": required.value, "actual": actual},
        )
        self._tx.commit()