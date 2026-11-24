"""Cabeceras de seguridad, CORS estricto y CSP del visor 3D (Fase 9)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.security_headers import CONTENT_SECURITY_POLICY, security_headers
from app.main import create_app


def _settings(**overrides) -> Settings:
    base = {
        "database_url": "postgresql+psycopg://u:p@localhost:5432/db",
        "jwt_secret": "x" * 48,
        "cors_origins": "http://localhost:5173",
    }
    base.update(overrides)
    return Settings(**base)


def test_csp_allows_draco_wasm_and_workers_without_unsafe_eval() -> None:
    """El visor 3D necesita WASM (Draco) y workers; nunca `unsafe-eval` de JS."""
    policy = CONTENT_SECURITY_POLICY
    assert "script-src 'self' 'wasm-unsafe-eval'" in policy
    assert "worker-src 'self' blob:" in policy
    assert "img-src 'self' blob: data:" in policy
    assert "unsafe-eval" not in policy.replace("wasm-unsafe-eval", "")
    assert "'unsafe-inline'" not in policy.split("script-src")[1].split(";")[0]
    assert "object-src 'none'" in policy
    assert "frame-ancestors 'none'" in policy


def test_hsts_only_outside_local() -> None:
    assert _settings(environment="local").hsts_header is None
    staging = _settings(environment="staging").hsts_header
    assert staging is not None and "max-age=31536000" in staging
    assert "includeSubDomains" in staging


def test_security_headers_can_be_disabled() -> None:
    """Con `SECURITY_HEADERS=false` no se inyecta ninguna cabecera propia."""
    assert "X-Frame-Options" not in security_headers(_settings(security_headers=False))


def test_api_responses_carry_security_headers() -> None:
    client = TestClient(create_app())
    response = client.get("/api/health/live")
    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["content-security-policy"] == CONTENT_SECURITY_POLICY
    assert response.headers["permissions-policy"].startswith("camera=()")


def test_request_id_is_logged_and_returned() -> None:
    client = TestClient(create_app())
    response = client.get("/api/health/live", headers={"X-Request-ID": "corr-12345678"})
    assert response.headers["x-request-id"] == "corr-12345678"


def test_cors_preflight_only_lists_allowed_methods_and_headers() -> None:
    client = TestClient(create_app())
    response = client.options(
        "/api/health/live",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization",
        },
    )
    assert response.status_code == 200
    allowed = response.headers["access-control-allow-headers"].lower()
    assert "authorization" in allowed
    assert "*" not in allowed
    methods = response.headers["access-control-allow-methods"]
    assert "*" not in methods


def test_cors_rejects_unknown_origin() -> None:
    client = TestClient(create_app())
    response = client.get("/api/health/live", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in response.headers
