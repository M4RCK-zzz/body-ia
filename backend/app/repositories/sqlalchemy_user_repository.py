from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import func, or_, select
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

    def get_many(self, user_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, User]:
        unique = sorted(set(user_ids))
        if not unique:
            return {}
        rows = self._session.scalars(select(User).where(User.id.in_(unique)))
        return {user.id: user for user in rows}

    def set_roles(self, user: User, role_names: Sequence[str]) -> None:
        user.roles = self._load_roles(role_names)
        self._session.flush()

    def list_page(
        self,
        *,
        limit: int,
        offset: int,
        search: str | None = None,
        role: str | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[User], int]:
        conditions = []
        if search:
            # `ilike` sobre nombre y correo: la búsqueda del panel de administración.
            pattern = f"%{search}%"
            conditions.append(or_(User.full_name.ilike(pattern), User.email.ilike(pattern)))
        if role is not None:
            conditions.append(User.roles.any(Role.name == role))
        if is_active is not None:
            conditions.append(User.is_active.is_(is_active))

        base = select(User).where(*conditions)
        total = self._session.scalar(select(func.count()).select_from(base.subquery())) or 0
        stmt = base.order_by(User.created_at.desc(), User.id).limit(limit).offset(offset)
        return list(self._session.scalars(stmt)), total