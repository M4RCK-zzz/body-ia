FRONTEND_ORIGIN = "http://localhost:5173"

def test_health_ok(client_factory):
    response = client_factory(True).get("/api/health")
    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "ok"
    assert body["database"] == "up"
    assert body["service"] == "BODYVISION AI"

def test_health_degraded_when_database_down(client_factory):
    response = client_factory(False).get("/api/health")
    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "degraded"
    assert body["database"] == "down"

def test_cors_preflight_allows_local_frontend(client_factory):
    response = client_factory(True).options(
        "/api/health",
        headers={"Origin": FRONTEND_ORIGIN, "Access-Control-Request-Method": "GET"},
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == FRONTEND_ORIGIN

def test_cors_does_not_allow_unknown_origin(client_factory):
    response = client_factory(True).get("/api/health", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in response.headers

def test_request_id_is_generated_and_propagated(client_factory):
    client = client_factory(True)
    assert client.get("/api/health").headers["x-request-id"]
    echoed = client.get("/api/health", headers={"X-Request-ID": "abc-123"})
    assert echoed.headers["x-request-id"] == "abc-123"

# --- Fase 9: readiness, liveness y latidos de workers ------------------------


def test_liveness_does_not_need_database(client_factory):
    response = client_factory(False).get("/api/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_readiness_ok_when_everything_is_up(client_factory):
    response = client_factory(True).get("/api/health/ready")
    body = response.json()
    assert response.status_code == 200
    assert body["ready"] is True
    names = {component["name"] for component in body["components"]}
    assert names == {"database", "storage", "migrations"}
    assert all(component["ok"] for component in body["components"])


def test_readiness_returns_503_when_database_is_down(client_factory):
    response = client_factory(False).get("/api/health/ready")
    body = response.json()
    assert response.status_code == 503
    assert body["ready"] is False
    assert body["status"] == "unavailable"
    database = next(c for c in body["components"] if c["name"] == "database")
    assert database["ok"] is False


def test_readiness_returns_503_when_storage_fails(client_factory, app):
    from app.api.deps import get_storage

    class BrokenStorage:
        def put(self, key, data):
            raise OSError("disco lleno")

        def get(self, key):
            raise OSError

        def exists(self, key):
            return False

        def delete(self, key):
            return None

    client = client_factory(True)  # fija los overrides por defecto
    app.dependency_overrides[get_storage] = lambda: BrokenStorage()
    response = client.get("/api/health/ready")
    assert response.status_code == 503
    storage = next(c for c in response.json()["components"] if c["name"] == "storage")
    assert storage["ok"] is False


def _identity_api(test_client, roles: list[str]):
    """Cliente con identidad real de `identity_fakes` encima de los fakes de salud.

    `create_app()` ya está construido por la fixture `app`; aquí solo se añaden
    los overrides de identidad y se devuelven `(client, email)` para pedir token.
    """
    from datetime import timedelta

    from app.api.deps import get_auth_service, get_user_admin_service
    from app.core.tokens import JwtTokenService
    from tests.identity_fakes import build_identity_env

    env = build_identity_env()
    env.tokens = JwtTokenService(
        secret="s" * 40, algorithm="HS256", issuer="test", ttl=timedelta(minutes=30)
    )
    user = env.users.create(
        email="quien@example.com",
        password_hash=env.hasher.hash("clave-segura-123"),
        full_name="Quien Sea",
        role_names=roles,
    )
    test_client.app.dependency_overrides[get_auth_service] = lambda: env.auth
    test_client.app.dependency_overrides[get_user_admin_service] = lambda: env.admin
    return test_client, user.email


def _login_headers(client, email: str) -> dict[str, str]:
    token = client.post(
        "/api/auth/login", json={"email": email, "password": "clave-segura-123"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _heartbeats(rows) -> "object":
    from tests.conftest import FakeHeartbeatRepository

    repo = FakeHeartbeatRepository()
    repo.rows = list(rows)
    return repo


def test_workers_endpoint_requires_admin(client_factory):
    """M1: el estado interno de los workers no se filtra a anónimos ni a usuarios."""
    from app.api.deps import get_worker_heartbeat_repository

    client = client_factory(True)
    client.app.dependency_overrides[get_worker_heartbeat_repository] = lambda: _heartbeats([])

    assert client.get("/api/health/workers").status_code == 401

    client, email = _identity_api(client, ["user"])
    response = client.get("/api/health/workers", headers=_login_headers(client, email))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_workers_endpoint_reports_liveness(client_factory):
    from datetime import UTC, datetime, timedelta

    from app.api.deps import get_worker_heartbeat_repository
    from app.models.worker_heartbeat import WorkerHeartbeat

    now = datetime.now(UTC)
    repo = _heartbeats(
        [
            WorkerHeartbeat(
                name="report",
                worker_version="0.1.0",
                started_at=now - timedelta(hours=1),
                last_seen_at=now - timedelta(seconds=5),
                iterations=12,
            ),
            WorkerHeartbeat(
                name="simulation",
                worker_version="0.1.0",
                started_at=now - timedelta(hours=1),
                last_seen_at=now - timedelta(hours=2),
                iterations=3,
                last_error="boom",
            ),
        ]
    )
    client = client_factory(True)
    client.app.dependency_overrides[get_worker_heartbeat_repository] = lambda: repo
    client, email = _identity_api(client, ["admin"])

    response = client.get("/api/health/workers", headers=_login_headers(client, email))
    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "degraded"
    workers = {worker["name"]: worker for worker in body["workers"]}
    assert workers["report"]["alive"] is True
    assert workers["simulation"]["alive"] is False
    assert workers["simulation"]["last_error"] == "boom"


def test_workers_endpoint_without_heartbeats_is_unknown(client_factory):
    from app.api.deps import get_worker_heartbeat_repository

    client = client_factory(True)
    client.app.dependency_overrides[get_worker_heartbeat_repository] = lambda: _heartbeats([])
    client, email = _identity_api(client, ["admin"])

    response = client.get("/api/health/workers", headers=_login_headers(client, email))
    assert response.json()["status"] == "unknown"


def test_retention_heartbeat_never_degrades_the_service(client_factory):
    """M2: `retention` es one-shot; su último latido informa, no degrada."""
    from datetime import UTC, datetime, timedelta

    from app.api.deps import get_worker_heartbeat_repository
    from app.models.worker_heartbeat import WorkerHeartbeat

    now = datetime.now(UTC)
    repo = _heartbeats(
        [
            WorkerHeartbeat(
                name=name,
                worker_version="0.1.0",
                started_at=now - timedelta(hours=2),
                last_seen_at=now - timedelta(seconds=5),
                iterations=4,
            )
            for name in ("pose", "report", "simulation")
        ]
        + [
            WorkerHeartbeat(
                name="retention",
                worker_version="0.1.0",
                started_at=now - timedelta(days=3),
                last_seen_at=now - timedelta(days=1),
                iterations=1,
            )
        ]
    )
    client = client_factory(True)
    client.app.dependency_overrides[get_worker_heartbeat_repository] = lambda: repo
    client, email = _identity_api(client, ["admin"])

    body = client.get("/api/health/workers", headers=_login_headers(client, email)).json()
    workers = {worker["name"]: worker for worker in body["workers"]}
    assert body["status"] == "ok", "una pasada de retención vieja no es un worker caído"
    assert workers["retention"]["continuous"] is False
    assert workers["retention"]["alive"] is True
    assert workers["retention"]["age_seconds"] > body["stale_after_seconds"]
    assert all(workers[name]["continuous"] is True for name in ("pose", "report", "simulation"))
