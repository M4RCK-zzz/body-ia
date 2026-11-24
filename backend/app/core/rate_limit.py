"""Rate limiting en memoria (Fase 9, decisión D5).

Token bucket por clave y ventana deslizante, sin Redis ni dependencias nuevas:
la cola del sistema sigue siendo PostgreSQL. Nginx aplica una segunda barrera
(`limit_req`) en el borde.

Limitaciones aceptadas y documentadas:

- El estado vive en el proceso: con N réplicas el límite efectivo es N×.
- Si el proceso se reinicia, los contadores arrancan de cero.
- La clave nunca guarda la IP ni el email en claro: se usa su SHA-256 truncado.

Nunca se limita `/api/health*`: los healthchecks de la infraestructura no deben
caer por tráfico ajeno.
"""

from __future__ import annotations

import hashlib
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Literal

LimitKey = Literal["ip", "user", "email"]


@dataclass(frozen=True, slots=True)
class LimitRule:
    """Ventana deslizante: `max_events` por `window_seconds`."""

    name: str
    max_events: int
    window_seconds: int
    key: LimitKey = "ip"


@dataclass(frozen=True, slots=True)
class RateLimitDecision:
    allowed: bool
    rule: str
    limit: int
    window_seconds: int
    retry_after: int
    key_hash: str


class SlidingWindowLimiter:
    """Contadores en memoria, thread-safe, con purga perezosa."""

    def __init__(self, clock=time.monotonic) -> None:
        self._clock = clock
        self._events: dict[tuple[str, str], deque[float]] = {}
        self._lock = threading.Lock()
        self._last_sweep = clock()

    def hit(self, rule: LimitRule, identity: str) -> RateLimitDecision:
        now = self._clock()
        key = (rule.name, _hash_identity(identity))
        window_start = now - rule.window_seconds
        with self._lock:
            bucket = self._events.setdefault(key, deque())
            while bucket and bucket[0] <= window_start:
                bucket.popleft()
            allowed = len(bucket) < rule.max_events
            if allowed:
                bucket.append(now)
            retry_after = (
                0
                if allowed or not bucket
                else max(1, int(rule.window_seconds - (now - bucket[0])) + 1)
            )
            self._maybe_sweep(now, rule.window_seconds)
        return RateLimitDecision(
            allowed=allowed,
            rule=rule.name,
            limit=rule.max_events,
            window_seconds=rule.window_seconds,
            retry_after=retry_after,
            key_hash=key[1],
        )

    def reset(self) -> None:
        with self._lock:
            self._events.clear()

    def _maybe_sweep(self, now: float, window: int) -> None:
        """Purga buckets vacíos cada minuto para no crecer sin límite."""
        if now - self._last_sweep < 60:
            return
        self._last_sweep = now
        stale = [
            key
            for key, bucket in self._events.items()
            if not bucket or bucket[-1] <= now - max(window, 3600)
        ]
        for key in stale:
            self._events.pop(key, None)


def _hash_identity(identity: str) -> str:
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]


# Rutas POST que encolan trabajo pesado (fases 4, 5, 7 y 8).
_WORKER_TRIGGER_SUFFIXES = (
    "/media",
    "/pose-analyses",
    "/reports",
    "/simulations",
    "/run",
    "/archive",
)


def rules_for_path(settings, path: str, method: str) -> list[LimitRule]:
    """Reglas aplicables a una ruta. La primera que se agota bloquea."""
    minute = settings.rate_limit_per_minute
    rules = [LimitRule("global", minute, 60, "ip")]

    if method == "POST" and path.endswith("/auth/login"):
        rules.append(LimitRule("login_ip", settings.rate_limit_login_per_minute, 60, "ip"))
        rules.append(LimitRule("login_email", settings.rate_limit_login_per_hour, 3600, "email"))
    elif method == "POST" and path.endswith("/auth/register"):
        rules.append(LimitRule("register_ip", settings.rate_limit_register_per_hour, 3600, "ip"))
    elif method == "POST" and path.endswith(_WORKER_TRIGGER_SUFFIXES):
        rules.append(
            LimitRule("worker_trigger", settings.rate_limit_worker_trigger_per_hour, 3600, "user")
        )
    elif method == "GET" and path.endswith("/content"):
        rules.append(
            LimitRule("download", settings.rate_limit_download_per_hour, 3600, "user")
        )
    return rules


def is_exempt(path: str) -> bool:
    """Healthchecks y documentación de la API nunca se limitan."""
    return (
        path.startswith("/api/health")
        or path in {"/api/docs", "/api/redoc", "/api/openapi.json"}
        or path.startswith("/api/docs/")
    )
