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