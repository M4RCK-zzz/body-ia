"""Separación de entornos (Fase 9): producción falla al arrancar, no avisa."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings

BASE = {
    "database_url": "postgresql+psycopg://u:p@localhost:5432/db",
    "jwt_secret": "x" * 48,
}


def _settings(**overrides) -> Settings:
    return Settings(**{**BASE, **overrides})


def test_production_requires_https_cors_origins() -> None:
    with pytest.raises(ValidationError, match="https"):
        _settings(environment="production", cors_origins="http://app.example.com")


def test_production_rejects_wildcard_cors() -> None:
    with pytest.raises(ValidationError, match="no admite"):
        _settings(environment="production", cors_origins="https://a.example, *")


def test_production_rejects_debug() -> None:
    with pytest.raises(ValidationError, match="DEBUG"):
        _settings(
            environment="production",
            cors_origins="https://app.example.com",
            debug=True,
        )


def test_production_rejects_public_api_docs() -> None:
    with pytest.raises(ValidationError, match="ENABLE_API_DOCS"):
        _settings(
            environment="production",
            cors_origins="https://app.example.com",
            enable_api_docs=True,
        )


def test_weak_jwt_secret_is_rejected_everywhere() -> None:
    with pytest.raises(ValidationError):
        Settings(database_url=BASE["database_url"], jwt_secret="change-me-please")
    with pytest.raises(ValidationError):
        Settings(database_url=BASE["database_url"], jwt_secret="corto")


def test_docs_are_on_outside_production_and_off_inside() -> None:
    assert _settings().docs_enabled is True
    assert _settings(environment="staging").docs_enabled is True
    assert (
        _settings(environment="production", cors_origins="https://app.example.com").docs_enabled
        is False
    )


def test_json_logs_and_hsts_follow_environment() -> None:
    local = _settings()
    assert local.json_logs is False
    assert local.hsts_header is None

    prod = _settings(environment="production", cors_origins="https://app.example.com")
    assert prod.json_logs is True
    assert prod.hsts_header is not None

    assert _settings(hsts_max_age=0).hsts_header is None
    assert _settings(security_headers=False).hsts_header is None


def test_retention_is_dry_run_by_default() -> None:
    assert _settings().retention_dry_run is True
    assert _settings(retention_dry_run=False).retention_dry_run is False
