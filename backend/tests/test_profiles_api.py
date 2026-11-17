from datetime import UTC, datetime, timedelta
import pytest
from fastapi.testclient import TestClient
from app.api.deps import get_measurement_service, get_profile_service
from app.main import create_app
from tests.fakes import build_services

@pytest.fixture
def api() -> TestClient:
    services = build_services()
    app = create_app()
    app.dependency_overrides[get_profile_service] = lambda: services.profiles
    app.dependency_overrides[get_measurement_service] = lambda: services.measurements
    return TestClient(app)

def _iso(hours_ago: int) -> str:
    return (datetime.now(UTC) - timedelta(hours=hours_ago)).isoformat()

def test_create_profile_normalizes_code(api):
    r = api.post("/api/profiles", json={"display_code": " bv-001 "})
    assert r.status_code == 201
    body = r.json()
    assert body["display_code"] == "BV-001"
    assert body["status"] == "active"

def test_duplicate_profile_returns_409_with_error_envelope(api):
    api.post("/api/profiles", json={"display_code": "BV-001"})
    r = api.post("/api/profiles", json={"display_code": "bv-001"})
    assert r.status_code == 409
    assert r.json()["error"]["message"]

def test_invalid_payload_uses_error_envelope(api):
    r = api.post("/api/profiles", json={"display_code": "a"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"

def test_measurement_flow_with_non_destructive_correction(api):
    pid = api.post("/api/profiles", json={"display_code": "BV-001"}).json()["id"]
    base = f"/api/profiles/{pid}/measurements"

    created = api.post(
        base,
        json={
            "metric_type": "weight",
            "value": 72.5,
            "unit": "kg",
            "measured_at": _iso(2),
            "method": "scale",
            "created_by": "Ana",
        },
    )
    assert created.status_code == 201
    original = created.json()
    assert original["kind"] == "observed"
    assert original["value"] == 72.5

    fixed = api.post(
        f"{base}/{original['id']}/corrections",
        json={"value": 71.8, "created_by": "Luis", "reason": "Error de lectura"},
    )
    assert fixed.status_code == 201
    assert fixed.json()["supersedes_id"] == original["id"]

    current = api.get(base).json()
    assert current["total"] == 1 and current["items"][0]["value"] == 71.8

    everything = api.get(base, params={"include_superseded": "true"}).json()
    flags = {i["id"]: i["is_current"] for i in everything["items"]}
    assert flags[original["id"]] is False

    series = api.get(f"{base}/series", params={"metric_type": "weight"}).json()
    assert series["kind"] == "observed"
    assert [p["value"] for p in series["points"]] == [71.8]
    assert series["points"][0]["corrected"] is True

def test_measurement_catalog_exposes_metrics_and_methods(api):
    body = api.get("/api/catalog/measurements").json()
    assert {m["metric_type"] for m in body["metrics"]} >= {"weight", "height", "waist"}
    assert "manual_tape" in {m["value"] for m in body["methods"]}