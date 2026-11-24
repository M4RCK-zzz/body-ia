"""Middlewares transversales de la API (Fase 9).

Orden real de ejecución (Starlette añade los middlewares en orden inverso al
registro, así que se registran del más interno al más externo):

    request-id  →  seguridad (cabeceras)  →  rate limit  →  rutas

- `request_id`: genera/reutiliza `X-Request-ID`, lo guarda en el `ContextVar` de
  logging y en `request.state` para que la auditoría lo incluya.
- cabeceras: HSTS, CSP, `nosniff`, `frame-ancestors`, `Referrer-Policy`...
- rate limit: token bucket en memoria por clave (IP o usuario autenticado).
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import FastAPI, Request, Response

from app.core.logging import request_id_ctx

logger = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"


def register_request_id_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def add_request_id(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        incoming = request.headers.get(REQUEST_ID_HEADER)
        # Solo se acepta un id de cliente si es corto y "seguro" (sin control).
        request_id = _sanitize_request_id(incoming) or uuid4().hex
        request.state.request_id = request_id
        token = request_id_ctx.set(request_id)
        started = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
        finally:
            # El log se emite **antes** de limpiar el contexto: si no, el
            # `request_id` del registro sería `None`.
            logger.info(
                "%s %s -> %s",
                request.method,
                request.url.path,
                status,
                extra={
                    "route": _route_template(request),
                    "status": status,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                },
            )
            request_id_ctx.reset(token)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response


def _sanitize_request_id(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = value.strip()
    # Se acepta el id del cliente tal cual (contrato previo), acotado y sin
    # caracteres de control, para no permitir inyección en logs.
    if not 1 <= len(cleaned) <= 64:
        return None
    if not cleaned.isprintable() or any(char.isspace() for char in cleaned):
        return None
    return cleaned


def _route_template(request: Request) -> str:
    """Ruta con placeholders (`/api/profiles/{profile_id}`) para no loguear UUIDs."""
    route = request.scope.get("route")
    path_format = getattr(route, "path", None)
    return path_format if isinstance(path_format, str) else request.url.path
