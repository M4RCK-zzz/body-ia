from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Generic, TypeVar
from uuid import UUID

ModelT = TypeVar("ModelT")

class Repository(ABC, Generic[ModelT]):
    @abstractmethod
    def get(self, entity_id: UUID) -> ModelT | None: ...

    @abstractmethod
    def add(self, entity: ModelT) -> ModelT: ...

    @abstractmethod
    def list(self, *, offset: int = 0, limit: int = 50) -> Sequence[ModelT]: ...