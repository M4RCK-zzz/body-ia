import os

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@localhost:5432/test")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5173")
os.environ.setdefault("JWT_SECRET", "test-secret-only-for-pytest-0123456789-abcdef")

from collections.abc import Callable, Iterator  # noqa: E402

import pytest  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.api.deps import get_health_repository  # noqa: E402
from app.main import create_app  # noqa: E402
from app.repositories.health import HealthRepository  # noqa: E402


class FakeHealthRepository(HealthRepository):
    def __init__(self, alive: bool) -> None:
        self._alive = alive

    def ping(self) -> bool:
        return self._alive


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
        return TestClient(app)

    return _make