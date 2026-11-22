"""Regresión: los repositorios SQLAlchemy reales deben instanciarse y exponer
todos sus métodos abstractos.

Bug real que causó el 500/CORS en GET /api/profiles: `list_accessible` quedó
definido a nivel de módulo (fuera de la clase), así que
`SqlAlchemyProfileRepository` no era instanciable en el entorno real.
"""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.access import ProfileAccess
from app.models.identity import Role, User, user_roles
from app.models.profile import Profile
from app.repositories.sqlalchemy_profile_repository import SqlAlchemyProfileRepository

_TABLES = [Role.__table__, user_roles, User.__table__, Profile.__table__, ProfileAccess.__table__]


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=_TABLES)
    with Session(engine) as db:
        yield db
    engine.dispose()


def _seed_user_with_profiles(session: Session, count: int) -> tuple[User, list[Profile]]:
    user = User(email="regresion@example.com", password_hash="x", full_name="Regresion")
    session.add(user)
    session.flush()
    profiles: list[Profile] = []
    for i in range(count):
        p = Profile(display_code=f"REG-{i:03d}", status="active", owner_id=user.id)
        session.add(p)
        session.flush()
        session.add(
            ProfileAccess(
                profile_id=p.id,
                user_id=user.id,
                level="owner",
                granted_by=user.id,
            )
        )
        profiles.append(p)
    session.commit()
    return user, profiles


def test_repository_roundtrip_and_limit_offset(session: Session) -> None:
    user, _ = _seed_user_with_profiles(session, 3)
    repo = SqlAlchemyProfileRepository(session)

    rows, total = repo.list_accessible(user_id=user.id, status=None, limit=200, offset=0)
    assert total == 3
    assert len(rows) == 3
    assert {lv for _, lv in rows} == {"owner"}

    page, total = repo.list_accessible(user_id=user.id, status=None, limit=1, offset=1)
    assert total == 3
    assert len(page) == 1

    page, total = repo.list_accessible(user_id=user.id, status=None, limit=1, offset=2)
    assert total == 3
    assert len(page) == 1


def test_list_accessible_filters_by_status(session: Session) -> None:
    user, profiles = _seed_user_with_profiles(session, 2)
    repo = SqlAlchemyProfileRepository(session)

    from app.domain.profiles import ProfileStatus

    rows, total = repo.list_accessible(
        user_id=user.id, status=ProfileStatus.ARCHIVED, limit=50, offset=0
    )
    assert total == 0
    assert rows == []

    rows, total = repo.list_accessible(
        user_id=user.id, status=ProfileStatus.ACTIVE, limit=50, offset=0
    )
    assert total == 2
    assert len(rows) == 2


def test_repository_get_and_list_for_other_user_returns_nothing(session: Session) -> None:
    user, profiles = _seed_user_with_profiles(session, 2)
    repo = SqlAlchemyProfileRepository(session)

    stranger = User(email="stranger@example.com", password_hash="x", full_name="Stranger")
    session.add(stranger)
    session.commit()

    rows, total = repo.list_accessible(user_id=stranger.id, status=None, limit=50, offset=0)
    assert total == 0
    assert rows == []

    # Un profile invisible sigue siendo buscable por id (permiso se valida en la capa de servicio).
    assert repo.get(profiles[0].id) is not None


def test_repository_handles_missing_profiles_gracefully(session: Session) -> None:
    repo = SqlAlchemyProfileRepository(session)
    assert repo.get(uuid.uuid4()) is None
    assert repo.get_by_display_code("NO-EXISTE") is None
