from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.profiles import ProfileStatus
from app.models.profile import Profile


class ProfileRepository(ABC):
    @abstractmethod
    def get(self, profile_id: UUID) -> Profile | None: ...

    @abstractmethod
    def get_by_display_code(self, display_code: str) -> Profile | None: ...

    @abstractmethod
    def add(self, profile: Profile) -> Profile: ...

    @abstractmethod
    def save(self, profile: Profile) -> Profile: ...

    @abstractmethod
    def list_accessible(
        self, *, user_id: UUID, status: ProfileStatus | None, limit: int, offset: int
    ) -> tuple[list[tuple[Profile, str]], int]:
        """Solo expedientes con acceso vigente del usuario, junto con su nivel."""