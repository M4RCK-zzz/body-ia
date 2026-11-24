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


def test_workers_endpoint_reports_liveness(client_factory, app):
    from datetime import UTC, datetime, timedelta

    from app.api.deps import get_worker_heartbeat_repository
    from app.models.worker_heartbeat import WorkerHeartbeat
    from tests.conftest import FakeHeartbeatRepository

    now = datetime.now(UTC)
    repo = FakeHeartbeatRepository()
    repo.rows = [
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
    client = client_factory(True)
    app.dependency_overrides[get_worker_heartbeat_repository] = lambda: repo

    response = client.get("/api/health/workers")
    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "degraded"
    workers = {worker["name"]: worker for worker in body["workers"]}
    assert workers["report"]["alive"] is True
    assert workers["simulation"]["alive"] is False
    assert workers["simulation"]["last_error"] == "boom"


def test_workers_endpoint_without_heartbeats_is_unknown(client_factory):
    response = client_factory(True).get("/api/health/workers")
    assert response.json()["status"] == "unknown"
