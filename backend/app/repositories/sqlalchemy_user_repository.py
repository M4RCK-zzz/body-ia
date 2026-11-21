from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import BusinessRuleError, ConflictError
from app.models.identity import Role, User
from app.repositories.user_repository import UserRepository


class SqlAlchemyUserRepository(UserRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def _load_roles(self, names: Sequence[str]) -> list[Role]:
        unique = sorted(set(names))
        roles = list(self._session.scalars(select(Role).where(Role.name.in_(unique))))
        if len(roles) != len(unique):
            raise BusinessRuleError("Se indicó un rol desconocido.")
        return roles

    def create(
        self, *, email: str, password_hash: str, full_name: str, role_names: Sequence[str]
    ) -> User:
        user = User(
            id=uuid.uuid4(),
            email=email,
            password_hash=password_hash,
            full_name=full_name,
            is_active=True,
            failed_login_count=0,
            roles=self._load_roles(role_names),
        )
        self._session.add(user)
        try:
            self._session.flush()
        except IntegrityError as exc:
            raise ConflictError("Ya existe una cuenta con ese correo.") from exc
        return user

    def get(self, user_id: uuid.UUID) -> User | None:
        return self._session.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        return self._session.scalar(select(User).where(User.email == email))

    def set_roles(self, user: User, role_names: Sequence[str]) -> None:
        user.roles = self._load_roles(role_names)
        self._session.flush()

    def list_page(self, *, limit: int, offset: int) -> tuple[list[User], int]:
        total = self._session.scalar(select(func.count()).select_from(User)) or 0
        stmt = select(User).order_by(User.created_at.desc(), User.id).limit(limit).offset(offset)
        return list(self._session.scalars(stmt)), total