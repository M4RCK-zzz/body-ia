"""Rate limiting (Fase 9): límites, 429 con Retry-After y salud exenta."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.rate_limit import (
    LimitRule,
    SlidingWindowLimiter,
    is_exempt,
    rules_for_path,
)
from app.main import create_app

BASE = {
    "database_url": "postgresql+psycopg://u:p@localhost:5432/db",
    "jwt_secret": "x" * 48,
    "cors_origins": "http://localhost:5173",
}


def _settings(**overrides) -> Settings:
    return Settings(**{**BASE, **overrides})


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_sliding_window_allows_then_blocks() -> None:
    clock = FakeClock()
    limiter = SlidingWindowLimiter(clock=clock)
    rule = LimitRule("test", 2, 60)

    assert limiter.hit(rule, "ip:1").allowed
    assert limiter.hit(rule, "ip:1").allowed
    blocked = limiter.hit(rule, "ip:1")
    assert not blocked.allowed
    assert blocked.retry_after >= 1


def test_sliding_window_recovers_after_window() -> None:
    clock = FakeClock()
    limiter = SlidingWindowLimiter(clock=clock)
    rule = LimitRule("test", 1, 30)
    assert limiter.hit(rule, "ip:1").allowed
    assert not limiter.hit(rule, "ip:1").allowed
    clock.advance(31)
    assert limiter.hit(rule, "ip:1").allowed


def test_keys_are_isolated_and_hashed() -> None:
    limiter = SlidingWindowLimiter(clock=FakeClock())
    rule = LimitRule("test", 1, 60)
    first = limiter.hit(rule, "ip:1.2.3.4")
    second = limiter.hit(rule, "ip:1.2.3.4")
    other = limiter.hit(rule, "ip:5.6.7.8")
    assert first.allowed and not second.allowed
    assert other.allowed  # otra IP no hereda el castigo
    assert "1.2.3.4" not in first.key_hash  # la clave nunca se guarda en claro


def test_health_is_never_limited() -> None:
    assert is_exempt("/api/health")
    assert is_exempt("/api/health/live")
    assert is_exempt("/api/health/ready")
    assert is_exempt("/api/docs")
    assert not is_exempt("/api/profiles")


def test_login_gets_stricter_rules_than_reads() -> None:
    settings = _settings()
    login = rules_for_path(settings, "/api/auth/login", "POST")
    names = {rule.name for rule in login}
    assert {"global", "login_ip", "login_email"} <= names
    reads = rules_for_path(settings, "/api/profiles", "GET")
    assert [rule.name for rule in reads] == ["global"]


class _RejectingAuthService:
    """Login que falla sin tocar la BD: aquí se mide el limitador, no la identidad."""

    def login(self, *, email: str, password: str):
        from app.core.security_errors import AuthenticationError

        raise AuthenticationError("Credenciales inválidas.")


def test_login_is_rate_limited_with_retry_after(monkeypatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_LOGIN_PER_MINUTE", "1")
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        from app.api.deps import get_auth_service

        app = create_app()
        app.dependency_overrides[get_auth_service] = lambda: _RejectingAuthService()
        client = TestClient(app)
        first = client.post("/api/auth/login", json={"email": "a@b.co", "password": "no-valida-1"})
        assert first.status_code != 429
        second = client.post("/api/auth/login", json={"email": "a@b.co", "password": "no-valida-1"})
        assert second.status_code == 429
        assert second.json()["error"]["code"] == "rate_limited"
        assert int(second.headers["retry-after"]) >= 1
        assert second.headers["x-ratelimit-rule"] == "login_ip"
        # El 429 también lleva cabeceras de seguridad y request id.
        assert second.headers["x-content-type-options"] == "nosniff"
        assert second.headers["x-request-id"]
    finally:
        get_settings.cache_clear()


def test_health_endpoints_are_not_limited(monkeypatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "1")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        client = TestClient(create_app())
        for _ in range(5):
            assert client.get("/api/health/live").status_code == 200
    finally:
        get_settings.cache_clear()


# --- A2: identidad de la IP y spoofing de cabeceras ---------------------------


def test_client_ip_ignores_forwarded_for_when_proxies_are_untrusted() -> None:
    """`TRUSTED_PROXIES=false` (el default): la cabecera del cliente no cuenta."""
    from starlette.requests import Request

    from app.core.rate_limit_middleware import _client_ip

    settings = _settings(trusted_proxies=False)
    scope = {
        "type": "http",
        "headers": [(b"x-forwarded-for", b"1.2.3.4"), (b"x-real-ip", b"5.6.7.8")],
        "client": ("10.0.0.9", 12345),
    }
    assert _client_ip(Request(scope), settings) == "10.0.0.9"


def test_client_ip_prefers_real_ip_from_the_trusted_proxy() -> None:
    """Con proxy de confianza manda `X-Real-IP` (lo reescribe Nginx), no XFF."""
    from starlette.requests import Request

    from app.core.rate_limit_middleware import _client_ip

    settings = _settings(trusted_proxies=True)
    scope = {
        "type": "http",
        "headers": [(b"x-forwarded-for", b"1.2.3.4"), (b"x-real-ip", b"203.0.113.7")],
        "client": ("10.0.0.9", 12345),
    }
    assert _client_ip(Request(scope), settings) == "203.0.113.7"


def test_trusted_proxies_false_is_not_truthy() -> None:
    """Regresión: con `str`, el literal "false" activaba la confianza en el proxy."""
    assert _settings(trusted_proxies="false").trusted_proxies is False
    assert _settings(trusted_proxies="0").trusted_proxies is False
    assert _settings(trusted_proxies="true").trusted_proxies is True
    assert _settings().trusted_proxies is False


def test_rotating_headers_does_not_evade_the_ip_limit(monkeypatch) -> None:
    """Rotar `X-Forwarded-For` no abre la puerta: el límite va por la IP real."""
    monkeypatch.setenv("RATE_LIMIT_LOGIN_PER_MINUTE", "2")
    monkeypatch.setenv("TRUSTED_PROXIES", "false")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        from app.api.deps import get_auth_service

        app = create_app()
        app.dependency_overrides[get_auth_service] = lambda: _RejectingAuthService()
        client = TestClient(app)
        codes = [
            client.post(
                "/api/auth/login",
                json={"email": "a@b.co", "password": "no-valida-1"},
                headers={"X-Forwarded-For": f"198.51.100.{i}", "X-Real-IP": f"198.51.100.{i}"},
            ).status_code
            for i in range(4)
        ]
        assert codes[:2] == [401, 401]
        assert codes[2] == 429, codes
        assert codes[3] == 429, codes
    finally:
        get_settings.cache_clear()
