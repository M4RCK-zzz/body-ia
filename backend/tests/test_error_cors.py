"""Los errores del backend deben conservar cabeceras CORS.

Bug real: una excepción no controlada (p. ej. error de BD) llegaba a
ServerErrorMiddleware y la respuesta 500 no incluía
`Access-Control-Allow-Origin`, con lo que el navegador bloqueaba la
respuesta y la UI mostraba "No se pudo conectar con la API" en lugar del
error real.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_profile_service
from app.api.security import get_current_user
from app.main import create_app
from tests.fakes import build_services


class _ExplodingProfilesService:
    """Servicio que dispara una excepción no controlada, como un fallo de BD."""

    def list_page(self, user, **_kwargs):
        raise RuntimeError("db exploded")

    def create(self, user, display_code):
        raise RuntimeError("db exploded")


@pytest.fixture
def exploding_client() -> TestClient:
    services = build_services()
    app = create_app()
    app.dependency_overrides[get_profile_service] = lambda: _ExplodingProfilesService()
    ana = services.new_user("ana")
    app.dependency_overrides[get_current_user] = lambda: ana
    return TestClient(app, raise_server_exceptions=False)


def test_unhandled_error_keeps_cors_headers(exploding_client: TestClient) -> None:
    r = exploding_client.get(
        "/api/profiles?limit=50",
        headers={"Origin": "http://localhost:5173"},
    )
    assert r.status_code == 500
    assert r.json()["error"]["code"] == "internal_error"
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert r.headers.get("access-control-allow-credentials") == "true"


def test_unhandled_error_without_origin_keeps_500(exploding_client: TestClient) -> None:
    r = exploding_client.get("/api/profiles")
    assert r.status_code == 500
    # Sin Origin no se emite Access-Control-Allow-Origin (nada a reflejar).
    assert r.headers.get("access-control-allow-origin") is None
