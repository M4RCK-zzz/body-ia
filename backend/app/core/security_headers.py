"""Cabeceras de seguridad en la respuesta (Fase 9).

Se aplican en la API y también en Nginx (defensa en dos capas). La CSP está
pensada para lo que las fases 2–8 realmente cargan:

- `img-src 'self' blob: data:` → miniaturas de captura (blob) y placeholders.
- `worker-src 'self' blob:` → workers del visor 3D / decodificador Draco.
- `script-src 'self' 'wasm-unsafe-eval'` → **Draco WASM** (`/draco/`): compilar
  WebAssembly requiere `wasm-unsafe-eval`, que no habilita `eval` de JavaScript.
- `style-src 'self' 'unsafe-inline'` → React aplica estilos inline en el visor.

Nunca se añade `unsafe-eval` ni `unsafe-inline` a `script-src`.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response

from app.core.config import Settings

CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self' 'wasm-unsafe-eval'",
        "worker-src 'self' blob:",
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' blob: data:",
        "font-src 'self'",
        "connect-src 'self'",
        "media-src 'self'",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ]
)

BASE_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
    "Content-Security-Policy": CONTENT_SECURITY_POLICY,
}


def security_headers(settings: Settings) -> dict[str, str]:
    if not settings.security_headers:
        return {}
    headers = dict(BASE_HEADERS)
    hsts = settings.hsts_header
    if hsts:
        headers["Strict-Transport-Security"] = hsts
    return headers


def apply_to_response(response: Response, settings: Settings) -> None:
    """Aplica las cabeceras a una respuesta suelta (p. ej. un 500 de Starlette)."""
    for name, value in security_headers(settings).items():
        response.headers.setdefault(name, value)


def register_security_headers(app: FastAPI, settings: Settings) -> None:
    if not settings.security_headers:
        return

    headers = security_headers(settings)

    @app.middleware("http")
    async def add_security_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Una excepción no controlada se deja propagar: el handler global
        # (`register_exception_handlers`) construye el 500 y las cabeceras se
        # añaden en el `ServerErrorMiddleware` por `apply_to_response`.
        response = await call_next(request)
        for name, value in headers.items():
            response.headers.setdefault(name, value)
        return response
