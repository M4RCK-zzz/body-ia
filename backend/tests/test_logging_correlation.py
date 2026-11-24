"""Correlación `X-Request-ID` ↔ log ↔ auditoría (Fase 9, §4.1)."""

from __future__ import annotations

import json
import logging

from fastapi.testclient import TestClient

from app.core.logging import (
    JsonFormatter,
    RequestContextFilter,
    request_id_ctx,
    user_id_ctx,
)
from app.main import create_app


def _record(**extra) -> logging.LogRecord:
    record = logging.LogRecord(
        name="app.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hola %s",
        args=("mundo",),
        exc_info=None,
    )
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def test_json_formatter_emits_one_line_with_request_context() -> None:
    token = request_id_ctx.set("abc12345")
    try:
        record = _record(route="/api/profiles/{profile_id}", status=200, duration_ms=12.5)
        for filter_ in (RequestContextFilter(),):
            filter_.filter(record)
        payload = json.loads(JsonFormatter().format(record))
    finally:
        request_id_ctx.reset(token)

    assert payload["message"] == "hola mundo"
    assert payload["request_id"] == "abc12345"
    assert payload["route"] == "/api/profiles/{profile_id}"
    assert payload["status"] == 200
    assert payload["level"] == "INFO"
    assert "\n" not in json.dumps(payload)


def test_json_formatter_handles_missing_context() -> None:
    record = _record()
    RequestContextFilter().filter(record)
    payload = json.loads(JsonFormatter().format(record))
    assert payload["request_id"] is None
    assert payload["user_id"] is None


def test_request_id_appears_in_log_and_response() -> None:
    records: list[logging.LogRecord] = []

    class _Collector(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    collector = _Collector()
    collector.addFilter(RequestContextFilter())
    app_logger = logging.getLogger("app.core.middleware")
    previous_level = app_logger.level
    app_logger.addHandler(collector)
    app_logger.setLevel(logging.INFO)
    try:
        client = TestClient(create_app())
        response = client.get("/api/health/live", headers={"X-Request-ID": "corr-abcdef12"})
    finally:
        app_logger.removeHandler(collector)
        app_logger.setLevel(previous_level)

    assert response.headers["x-request-id"] == "corr-abcdef12"
    matching = [r for r in records if r.getMessage().startswith("GET /api/health/live")]
    assert matching, [r.getMessage() for r in records]
    assert matching[0].request_id == "corr-abcdef12"


def test_unhandled_error_keeps_request_id_and_headers() -> None:
    """El 500 sale por ServerErrorMiddleware: debe conservar id y cabeceras."""
    from app.api.deps import get_profile_service
    from app.api.security import get_current_user
    from tests.fakes import build_services

    class Exploding:
        def list_page(self, user, **_kwargs):
            raise RuntimeError("boom")

    services = build_services()
    app = create_app()
    app.dependency_overrides[get_profile_service] = lambda: Exploding()
    app.dependency_overrides[get_current_user] = lambda: services.new_user("ana")
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/api/profiles", headers={"X-Request-ID": "corr-error-1"})
    assert response.status_code == 500
    assert response.headers["x-request-id"] == "corr-error-1"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_user_context_variable_can_be_set_and_reset() -> None:
    token = user_id_ctx.set("user-42")
    try:
        record = _record()
        RequestContextFilter().filter(record)
        assert record.user_id == "user-42"
    finally:
        user_id_ctx.reset(token)


def test_audit_events_carry_request_id() -> None:
    """Un evento de auditoría se puede cruzar con el log por `request_id`."""
    from app.api.deps import get_profile_service
    from app.api.security import get_current_user
    from tests.fakes import build_services

    services = build_services()
    ana = services.new_user("ana")
    app = create_app()
    app.dependency_overrides[get_profile_service] = lambda: services.profiles
    app.dependency_overrides[get_current_user] = lambda: ana
    client = TestClient(app)

    response = client.post(
        "/api/profiles", json={"display_code": "BV-TRACE"}, headers={"X-Request-ID": "trace-9999"}
    )
    assert response.status_code == 201

    created = [e for e in services.audit_repo.events if e.action == "profile.created"]
    assert created, [e.action for e in services.audit_repo.events]
    assert created[-1].detail["request_id"] == "trace-9999"
    assert created[-1].detail["request_id"] == response.headers["x-request-id"]


def test_audit_without_request_context_stays_clean() -> None:
    """Fuera de una petición (workers) no se inventa un `request_id`."""
    from app.services.audit_service import AuditRecorder
    from tests.identity_fakes import InMemoryAuditRepository

    repo = InMemoryAuditRepository()
    AuditRecorder(repo).record("worker.beat", actor_id=None, detail={"ok": True})
    assert "request_id" not in repo.events[-1].detail
