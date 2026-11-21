from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.core.clock import utcnow
from app.core.errors import BusinessRuleError, ConflictError
from app.domain.access import AccessLevel
from app.domain.identity import AuditAction
from app.domain.profiles import ProfileStatus
from app.models.access import ProfileAccess
from app.models.identity import User
from app.models.profile import Profile
from app.repositories.access_repository import ProfileAccessRepository
from app.repositories.profile_repository import ProfileRepository
from app.services.access_guard import AccessGuard
from app.services.audit_service import AuditRecorder
from app.services.ports import Transaction

_DUPLICATE = "Ya existe un expediente con ese código."


@dataclass(frozen=True, slots=True)
class ProfileView:
    profile: Profile
    my_access: str


class ProfileService:
    def __init__(
        self,
        profiles: ProfileRepository,
        access: ProfileAccessRepository,
        guard: AccessGuard,
        audit: AuditRecorder,
        tx: Transaction,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        self._profiles = profiles
        self._access = access
        self._guard = guard
        self._audit = audit
        self._tx = tx
        self._clock = clock

    def _record(self, action: AuditAction, actor: User, profile: Profile, detail=None) -> None:
        self._audit.record(
            action,
            actor_id=actor.id,
            resource_type="profile",
            resource_id=str(profile.id),
            profile_id=profile.id,
            detail=detail,
        )

    def create(self, actor: User, display_code: str) -> ProfileView:
        if self._profiles.get_by_display_code(display_code) is not None:
            raise ConflictError(_DUPLICATE)
        profile = Profile(
            display_code=display_code, status=ProfileStatus.ACTIVE.value, owner_id=actor.id
        )
        self._profiles.add(profile)
        self._access.add(
            ProfileAccess(
                profile_id=profile.id,
                user_id=actor.id,
                level=AccessLevel.OWNER.value,
                granted_by=actor.id,
                granted_at=self._clock(),
            )
        )
        self._record(AuditAction.PROFILE_CREATED, actor, profile)
        self._tx.commit()
        return ProfileView(profile, AccessLevel.OWNER.value)

    def get(self, actor: User, profile_id: UUID) -> ProfileView:
        profile, grant = self._guard.require(profile_id, actor, AccessLevel.VIEWER)
        return ProfileView(profile, grant.level)

    def list_page(
        self, actor: User, *, status: ProfileStatus | None, limit: int, offset: int
    ) -> tuple[list[ProfileView], int]:
        rows, total = self._profiles.list_accessible(
            user_id=actor.id, status=status, limit=limit, offset=offset
        )
        return [ProfileView(p, level) for p, level in rows], total

    def rename(self, actor: User, profile_id: UUID, display_code: str) -> ProfileView:
        profile, grant = self._guard.require(profile_id, actor, AccessLevel.OWNER)
        if profile.status != ProfileStatus.ACTIVE.value:
            raise BusinessRuleError("Sólo se puede editar un expediente activo.")
        if display_code == profile.display_code:
            return ProfileView(profile, grant.level)
        existing = self._profiles.get_by_display_code(display_code)
        if existing is not None and existing.id != profile.id:
            raise ConflictError(_DUPLICATE)
        before = profile.display_code
        profile.display_code = display_code
        self._profiles.save(profile)
        self._record(
            AuditAction.PROFILE_RENAMED, actor, profile, {"before": before, "after": display_code}
        )
        self._tx.commit()
        return ProfileView(profile, grant.level)

    def archive(self, actor: User, profile_id: UUID) -> ProfileView:
        profile, grant = self._guard.require(profile_id, actor, AccessLevel.OWNER)
        if profile.status == ProfileStatus.ARCHIVED.value:
            return ProfileView(profile, grant.level)
        if profile.status == ProfileStatus.RESTRICTED.value:
            raise BusinessRuleError("Un expediente restringido no puede archivarse.")
        profile.status = ProfileStatus.ARCHIVED.value
        profile.archived_at = self._clock()
        self._profiles.save(profile)
        self._record(AuditAction.PROFILE_ARCHIVED, actor, profile)
        self._tx.commit()
        return ProfileView(profile, grant.level)

    def restore(self, actor: User, profile_id: UUID) -> ProfileView:
        profile, grant = self._guard.require(profile_id, actor, AccessLevel.OWNER)
        if profile.status == ProfileStatus.ACTIVE.value:
            return ProfileView(profile, grant.level)
        if profile.status != ProfileStatus.ARCHIVED.value:
            raise BusinessRuleError("Sólo se puede restaurar un expediente archivado.")
        profile.status = ProfileStatus.ACTIVE.value
        profile.archived_at = None
        self._profiles.save(profile)
        self._record(AuditAction.PROFILE_RESTORED, actor, profile)
        self._tx.commit()
        return ProfileView(profile, grant.level)