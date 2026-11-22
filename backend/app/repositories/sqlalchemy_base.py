from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.repositories.base import ModelT, Repository


class SQLAlchemyRepository(Repository[ModelT]):
    model: type[ModelT]

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, entity_id: UUID) -> ModelT | None:
        return self._session.get(self.model, entity_id)

    def add(self, entity: ModelT) -> ModelT:
        self._session.add(entity)
        self._session.flush()
        return entity

    def list(self, *, offset: int = 0, limit: int = 50) -> Sequence[ModelT]:
        statement = select(self.model).offset(offset).limit(limit)
        return self._session.scalars(statement).all()