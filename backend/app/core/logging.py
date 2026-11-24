"""Logging de la aplicación (Fase 9).

Dos formatos, mismos campos:

- `local`: texto legible para la consola.
- `staging`/`production`: **una línea JSON por registro**, para que el agregador
  pueda filtrar por `request_id`, `user_id` o `status`.

El `correlation_id` vive en un `ContextVar` que rellena el middleware HTTP: así
cualquier log emitido durante la petición (incluida una excepción no controlada)
lleva el identificador que el cliente recibió en `X-Request-ID`.
"""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

# Contexto de la petición en curso. `None` fuera de una petición (workers).
request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)
user_id_ctx: ContextVar[str | None] = ContextVar("user_id", default=None)

# Campos que el formateador añade siempre; nunca se duplican desde `extra`.
_RESERVED = {
    "ts",
    "level",
    "logger",
    "message",
    "request_id",
    "user_id",
    "exc_info",
    "stack_info",
}


class RequestContextFilter(logging.Filter):
    """Inyecta `request_id`/`user_id` en cada registro."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not getattr(record, "request_id", None):
            record.request_id = request_id_ctx.get()
        if not getattr(record, "user_id", None):
            record.user_id = user_id_ctx.get()
        return True


class JsonFormatter(logging.Formatter):
    """Una línea JSON por registro, con campos estables."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", None),
            "user_id": getattr(record, "user_id", None),
        }
        # Campos extra declarados por el emisor (route, status, duration_ms...).
        for key, value in record.__dict__.items():
            if key in _RESERVED or key.startswith("_"):
                continue
            if key in logging.LogRecord.__dict__ or key in {"args", "msg", "levelno"}:
                continue
            if isinstance(value, str | int | float | bool) or value is None:
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


class TextFormatter(logging.Formatter):
    """Formato legible con el mismo `request_id` al principio."""

    def __init__(self) -> None:
        super().__init__(
            "%(asctime)s %(levelname)-8s [%(request_id)s] [%(name)s] %(message)s"
        )

    def format(self, record: logging.LogRecord) -> str:
        if not getattr(record, "request_id", None):
            record.request_id = "-"
        return super().format(record)


def configure_logging(level: str = "INFO", *, json_output: bool = False) -> None:
    """Configura el logging raíz una sola vez (idempotente, `force=True`)."""
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RequestContextFilter())
    handler.setFormatter(JsonFormatter() if json_output else TextFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())

    # uvicorn trae sus propios handlers: se enrutan por el mismo formateador.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True
        uvicorn_logger.setLevel(level.upper())
