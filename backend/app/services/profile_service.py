from collections.abc import Callable
from datetime import datetime
from uuid import UUID
from app.core.clock import utcnow
from app.core.errors import BusinessRuleError, ConflictError, NotFoundError
from app.domain.profiles import ProfileStatus
from app.models.profile import Profile
from app.repositories.profile_repository import ProfileRepository
from app.services.ports import Transaction

class ProfileService:
    def __init__(
        self,
        profiles: ProfileRepository,
        tx: Transaction,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        self._profiles = profiles
        self._tx = tx
        self._clock = clock

    def create(self, display_code: str) -> Profile:
        if self._profiles.get_by_display_code(display_code) is not None:
            raise ConflictError("Ya existe un expediente con ese código.")
        profile = Profile(display_code=display_code, status=ProfileStatus.ACTIVE.value)
        self._profiles.add(profile)
        self._tx.commit()
        return profile

    def get(self, profile_id: UUID) -> Profile:
        profile = self._profiles.get(profile_id)
        if profile is None:
            raise NotFoundError("Expediente no encontrado.")
        return profile

    def list_page(
        self, *, status: ProfileStatus | None, limit: int, offset: int
    ) -> tuple[list[Profile], int]:
        return self._profiles.list_page(status=status, limit=limit, offset=offset)

    def rename(self, profile_id: UUID, display_code: str) -> Profile:
        profile = self.get(profile_id)
        if profile.status != ProfileStatus.ACTIVE.value:
            raise BusinessRuleError("Sólo se puede editar un expediente activo.")
        if display_code == profile.display_code:
            return profile
        existing = self._profiles.get_by_display_code(display_code)
        if existing is not None and existing.id != profile.id:
            raise ConflictError("Ya existe un expediente con ese código.")
        profile.display_code = display_code
        self._profiles.save(profile)
        self._tx.commit()
        return profile

    def archive(self, profile_id: UUID) -> Profile:
        profile = self.get(profile_id)
        if profile.status == ProfileStatus.ARCHIVED.value:
            return profile
        if profile.status == ProfileStatus.RESTRICTED.value:
            raise BusinessRuleError("Un expediente restringido no puede archivarse.")
        profile.status = ProfileStatus.ARCHIVED.value
        profile.archived_at = self._clock()
        self._profiles.save(profile)
        self._tx.commit()
        return profile

    def restore(self, profile_id: UUID) -> Profile:
        profile = self.get(profile_id)
        if profile.status == ProfileStatus.ACTIVE.value:
            return profile
        if profile.status != ProfileStatus.ARCHIVED.value:
            raise BusinessRuleError("Sólo se puede restaurar un expediente archivado.")
        profile.status = ProfileStatus.ACTIVE.value
        profile.archived_at = None
        self._profiles.save(profile)
        self._tx.commit()
        return profile