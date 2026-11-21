from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.models.access import Consent, ProfileAccess


class ProfileAccessRepository(ABC):
    @abstractmethod
    def add(self, access: ProfileAccess) -> ProfileAccess: ...

    @abstractmethod
    def save(self, access: ProfileAccess) -> ProfileAccess: ...

    @abstractmethod
    def get_active(self, profile_id: UUID, user_id: UUID) -> ProfileAccess | None: ...

    @abstractmethod
    def list_active(self, profile_id: UUID) -> list[ProfileAccess]: ...


class ConsentRepository(ABC):
    @abstractmethod
    def add(self, consent: Consent) -> Consent: ...

    @abstractmethod
    def save(self, consent: Consent) -> Consent: ...

    @abstractmethod
    def get_active(self, profile_id: UUID, purpose: str) -> Consent | None: ...