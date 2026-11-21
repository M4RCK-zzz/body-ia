from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from collections.abc import Sequence

from app.models.identity import User


class UserRepository(ABC):
    @abstractmethod
    def create(
        self, *, email: str, password_hash: str, full_name: str, role_names: Sequence[str]
    ) -> User: ...

    @abstractmethod
    def get(self, user_id: uuid.UUID) -> User | None: ...

    @abstractmethod
    def get_by_email(self, email: str) -> User | None: ...

    @abstractmethod
    def set_roles(self, user: User, role_names: Sequence[str]) -> None: ...

    @abstractmethod
    def list_page(self, *, limit: int, offset: int) -> tuple[list[User], int]: ...