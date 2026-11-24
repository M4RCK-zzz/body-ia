import os

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@localhost:5432/test")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5173")
os.environ.setdefault("JWT_SECRET", "test-secret-only-for-pytest-0123456789-abcdef")

from collections.abc import Callable, Iterator  # noqa: E402

import pytest  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.api.deps import (  # noqa: E402
    get_health_repository,
    get_storage,
    get_worker_heartbeat_repository,
)
from app.main import create_app  # noqa: E402
from app.repositories.health import HealthRepository  # noqa: E402


class FakeHealthRepository(HealthRepository):
    def __init__(self, alive: bool, revision: str | None = "0009") -> None:
        self._alive = alive
        self._revision = revision

    def ping(self) -> bool:
        return self._alive

    def current_revision(self) -> str | None:
        return self._revision


class FakeStorage:
    """Storage en memoria para readiness (no toca disco)."""

    def __init__(self) -> None:
        self._data: dict[str, bytes] = {}

    def put(self, key: str, data: bytes) -> None:
        self._data[key] = data

    def get(self, key: str) -> bytes:
        return self._data[key]

    def exists(self, key: str) -> bool:
        return key in self._data

    def delete(self, key: str) -> None:
        self._data.pop(key, None)


class FakeHeartbeatRepository:
    def __init__(self) -> None:
        self.rows: list = []

    def beat(self, name, *, version, now):
        raise NotImplementedError

    def record_error(self, name, *, message, now) -> None:
        return None

    def list_all(self):
        return list(self.rows)


@pytest.fixture
def app() -> Iterator[FastAPI]:
    application = create_app()
    yield application
    application.dependency_overrides.clear()


@pytest.fixture
def client_factory(app: FastAPI) -> Callable[[bool], TestClient]:
    def _make(database_alive: bool = True) -> TestClient:
        app.dependency_overrides[get_health_repository] = lambda: FakeHealthRepository(
            database_alive
        )
        app.dependency_overrides[get_storage] = lambda: FakeStorage()
        app.dependency_overrides[get_worker_heartbeat_repository] = (
            lambda: FakeHeartbeatRepository()
        )
        return TestClient(app)

    return _make