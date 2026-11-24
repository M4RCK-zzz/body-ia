"""Middleware HTTP de rate limiting (Fase 9).

Se aplica **antes** de tocar la base de datos: un ataque de fuerza bruta no debe
gastar conexiones ni argon2. La identidad se resuelve así:

1. `user`: el `sub` del JWT si la petición lo trae (sin verificarlo: solo cuenta).
2. `email`: el campo `email` del cuerpo JSON en `/auth/login`.
3. `ip`: `X-Forwarded-For` (primera IP) si el proxy es de confianza, si no la IP
   de la conexión.

La clave se guarda **hasheada** en la decisión y en la auditoría: nunca se
registra la IP ni el email en claro.
"""

from __future__ import annotations

import base64
import json
import logging
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from app.core.config import Settings
from app.core.rate_limit import LimitRule, SlidingWindowLimiter, is_exempt, rules_for_path
from app.core.security_headers import apply_to_response

logger = logging.getLogger(__name__)

MAX_BODY_PEEK = 4096


def _client_ip(request: Request, settings: Settings) -> str:
    if settings.trusted_proxies:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _token_subject(request: Request) -> str | None:
    """`sub` del JWT sin verificar firma: solo para contar, nunca para autorizar."""
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        return None
    parts = header[7:].strip().split(".")
    if len(parts) != 3:
        return None
    try:
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload))
    except (ValueError, TypeError):
        return None
    subject = data.get("sub")
    return subject if isinstance(subject, str) else None


async def _peek_email(request: Request) -> str | None:
    if request.headers.get("content-type", "").split(";")[0].strip() != "application/json":
        return None
    try:
        body = await request.body()
    except Exception:  # pragma: no cover - cuerpo no legible
        return None
    if len(body) > MAX_BODY_PEEK:
        return None
    try:
        data = json.loads(body)
    except (ValueError, TypeError):
        return None
    email = data.get("email") if isinstance(data, dict) else None
    return email.strip().lower() if isinstance(email, str) else None


def _identity(rule: LimitRule, request: Request, settings: Settings, email: str | None) -> str:
    if rule.key == "user":
        return _token_subject(request) or f"ip:{_client_ip(request, settings)}"
    if rule.key == "email":
        return f"email:{email}" if email else f"ip:{_client_ip(request, settings)}"
    return f"ip:{_client_ip(request, settings)}"


def register_rate_limit(app: FastAPI, settings: Settings, limiter: SlidingWindowLimiter) -> None:
    if not settings.rate_limit_enabled:
        return

    @app.middleware("http")
    async def rate_limit(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        path = request.url.path
        rules = rules_for_path(settings, path, request.method)
        if not rules or is_exempt(path) or request.method == "OPTIONS":
            return await call_next(request)

        email = await _peek_email(request) if any(rule.key == "email" for rule in rules) else None

        for rule in rules:
            decision = limiter.hit(rule, _identity(rule, request, settings, email))
            if decision.allowed:
                continue
            logger.warning(
                "rate limit alcanzado en %s (regla=%s, clave=%s…)",
                path,
                decision.rule,
                decision.key_hash[:6],
                extra={"route": path, "status": 429, "limit_rule": decision.rule},
            )
            response = JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "rate_limited",
                        "message": (
                            "Demasiadas peticiones. Espera unos segundos antes de reintentar."
                        ),
                        "retry_after": decision.retry_after,
                    }
                },
                headers={
                    "Retry-After": str(decision.retry_after),
                    "X-RateLimit-Limit": str(decision.limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Rule": decision.rule,
                },
            )
            request_id = getattr(request.state, "request_id", "")
            if request_id:
                response.headers["X-Request-ID"] = request_id
            apply_to_response(response, settings)
            return response

        return await call_next(request)
