from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import (
    get_consent_service,
    get_measurement_service,
    get_profile_access_service,
    get_profile_service,
)
from app.api.security import get_current_user
from app.main import create_app
from tests.fakes import Services, build_services


@dataclass
class ApiEnv:
    client: TestClient
    app: FastAPI
    services: Services
    ana: object
    luis: object
    root: object

    def login(self, user) -> None:
        self.app.dependency_overrides[get_current_user] = lambda: user


@pytest.fixture
def env() -> ApiEnv:
    services = build_services()
    app = create_app()
    app.dependency_overrides[get_profile_service] = lambda: services.profiles
    app.dependency_overrides[get_measurement_service] = lambda: services.measurements
    app.dependency_overrides[get_consent_service] = lambda: services.consent
    app.dependency_overrides[get_profile_access_service] = lambda: services.access_service
    e = ApiEnv(
        client=TestClient(app),
        app=app,
        services=services,
        ana=services.new_user("ana"),
        luis=services.new_user("luis"),
        root=services.new_user("root", role="admin"),
    )
    e.login(e.ana)
    return e


def _iso(hours_ago: int) -> str:
    return (datetime.now(UTC) - timedelta(hours=hours_ago)).isoformat()


def _weight(**extra) -> dict:
    return {
        "metric_type": "weight",
        "value": 72.5,
        "unit": "kg",
        "measured_at": _iso(2),
        "method": "scale",
        **extra,
    }


def _new_profile(env: ApiEnv, code: str = "BV-001") -> str:
    r = env.client.post("/api/profiles", json={"display_code": code})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _accept_consent(env: ApiEnv, pid: str) -> None:
    r = env.client.post(
        f"/api/profiles/{pid}/consents",
        json={"purpose": "data_processing", "declaration": True},
    )
    assert r.status_code == 201, r.text


def _grant(env: ApiEnv, pid: str, user, level: str):
    r = env.client.post(f"/api/profiles/{pid}/access", json={"email": user.email, "level": level})
    assert r.status_code in (200, 201), r.text


def test_create_profile_normalizes_code_and_reports_owner(env):
    r = env.client.post("/api/profiles", json={"display_code": " bv-001 "})
    assert r.status_code == 201
    body = r.json()
    assert body["display_code"] == "BV-001"
    assert body["status"] == "active"
    assert body["my_access"] == "owner"


def test_duplicate_profile_returns_409_with_error_envelope(env):
    _new_profile(env)
    r = env.client.post("/api/profiles", json={"display_code": "bv-001"})
    assert r.status_code == 409
    assert r.json()["error"]["message"]


def test_invalid_payload_uses_error_envelope(env):
    r = env.client.post("/api/profiles", json={"display_code": "a"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


def test_list_only_returns_accessible_profiles(env):
    _new_profile(env)
    mine = env.client.get("/api/profiles").json()
    assert mine["total"] == 1 and mine["items"][0]["my_access"] == "owner"
    env.login(env.luis)
    assert env.client.get("/api/profiles").json()["total"] == 0


def test_profile_of_another_user_is_404(env):
    pid = _new_profile(env)
    env.login(env.luis)
    assert env.client.get(f"/api/profiles/{pid}").status_code == 404


def test_admin_has_no_implicit_access(env):
    pid = _new_profile(env)
    env.login(env.root)
    assert env.client.get(f"/api/profiles/{pid}").status_code == 404


def test_viewer_can_read_with_my_access_viewer(env):
    pid = _new_profile(env)
    _grant(env, pid, env.luis, "viewer")
    env.login(env.luis)
    r = env.client.get(f"/api/profiles/{pid}")
    assert r.status_code == 200 and r.json()["my_access"] == "viewer"


def test_measurement_requires_consent(env):
    pid = _new_profile(env)
    r = env.client.post(f"/api/profiles/{pid}/measurements", json=_weight())
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "consent_required"
    _accept_consent(env, pid)
    assert env.client.post(f"/api/profiles/{pid}/measurements", json=_weight()).status_code == 201


def test_client_cannot_send_created_by(env):
    pid = _new_profile(env)
    _accept_consent(env, pid)
    r = env.client.post(f"/api/profiles/{pid}/measurements", json=_weight(created_by="Otro"))
    assert r.status_code == 422


def test_viewer_cannot_record_measurements(env):
    pid = _new_profile(env)
    _accept_consent(env, pid)
    _grant(env, pid, env.luis, "viewer")
    env.login(env.luis)
    r = env.client.post(f"/api/profiles/{pid}/measurements", json=_weight())
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "insufficient_access"


def test_editor_can_record_and_author_is_server_side(env):
    pid = _new_profile(env)
    _accept_consent(env, pid)
    _grant(env, pid, env.luis, "editor")
    env.login(env.luis)
    r = env.client.post(f"/api/profiles/{pid}/measurements", json=_weight())
    assert r.status_code == 201
    assert r.json()["created_by"] == "Luis"


def test_measurement_flow_with_non_destructive_correction(env):
    pid = _new_profile(env)
    _accept_consent(env, pid)
    base = f"/api/profiles/{pid}/measurements"
    created = env.client.post(base, json=_weight())
    assert created.status_code == 201
    original = created.json()
    assert original["kind"] == "observed"
    assert original["value"] == 72.5
    assert original["created_by"] == "Ana"
    fixed = env.client.post(
        f"{base}/{original['id']}/corrections",
        json={"value": 71.8, "reason": "Error de lectura"},
    )
    assert fixed.status_code == 201
    assert fixed.json()["supersedes_id"] == original["id"]
    current = env.client.get(base).json()
    assert current["total"] == 1 and current["items"][0]["value"] == 71.8
    everything = env.client.get(base, params={"include_superseded": "true"}).json()
    flags = {i["id"]: i["is_current"] for i in everything["items"]}
    assert flags[original["id"]] is False
    series = env.client.get(f"{base}/series", params={"metric_type": "weight"}).json()
    assert series["kind"] == "observed"
    assert [p["value"] for p in series["points"]] == [71.8]
    assert series["points"][0]["corrected"] is True


def test_consent_requires_true_declaration(env):
    pid = _new_profile(env)
    r = env.client.post(
        f"/api/profiles/{pid}/consents",
        json={"purpose": "data_processing", "declaration": False},
    )
    assert r.status_code == 422


def test_grant_and_revoke_access_over_http(env):
    pid = _new_profile(env)
    _grant(env, pid, env.luis, "viewer")
    env.login(env.luis)
    assert env.client.get(f"/api/profiles/{pid}").status_code == 200
    env.login(env.ana)
    r = env.client.delete(f"/api/profiles/{pid}/access/{env.luis.id}")
    assert r.status_code == 204
    env.login(env.luis)
    assert env.client.get(f"/api/profiles/{pid}").status_code == 404


def test_measurement_catalog_exposes_metrics_and_methods(env):
    body = env.client.get("/api/catalog/measurements").json()
    assert {m["metric_type"] for m in body["metrics"]} >= {"weight", "height", "waist"}
    assert "manual_tape" in {m["value"] for m in body["methods"]}