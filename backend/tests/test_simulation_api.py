from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.deps import (
    get_analytics_service,
    get_consent_service,
    get_dashboard_service,
    get_measurement_service,
    get_profile_service,
    get_report_service,
    get_simulation_service,
)
from app.api.security import get_current_user
from app.main import create_app
from app.services.dashboard_service import DashboardService
from tests.fakes import build_services
from tests.test_simulation_service import seed, worker


class ApiEnv:
    def __init__(self) -> None:
        self.services = build_services()
        self.app = create_app()
        svc = self.services
        self.app.dependency_overrides[get_profile_service] = lambda: svc.profiles
        self.app.dependency_overrides[get_measurement_service] = lambda: svc.measurements
        self.app.dependency_overrides[get_consent_service] = lambda: svc.consent
        self.app.dependency_overrides[get_analytics_service] = lambda: svc.analytics
        self.app.dependency_overrides[get_report_service] = lambda: svc.reports
        self.app.dependency_overrides[get_simulation_service] = lambda: svc.simulations
        self.app.dependency_overrides[get_dashboard_service] = lambda: DashboardService(
            svc.profiles_repo,
            svc.analytics_repo,
            svc.pose_repo,
            svc.audit,
            svc.tx,
            clock=svc.clock,
        )
        self.client = TestClient(self.app)
        self.ana = svc.new_user("ana")
        self.login(self.ana)

    def login(self, user) -> None:
        self.app.dependency_overrides[get_current_user] = lambda: user

    def profile(self, code: str = "BV-001", *, consent: bool = True) -> str:
        response = self.client.post("/api/profiles", json={"display_code": code})
        assert response.status_code == 201, response.text
        pid = response.json()["id"]
        if consent:
            accepted = self.client.post(
                f"/api/profiles/{pid}/consents",
                json={"purpose": "data_processing", "declaration": True},
            )
            assert accepted.status_code == 201, accepted.text
            seed(self.services, self.ana, pid)
        return pid

    def simulate(self, pid: str, **kwargs) -> dict:
        payload = {
            "label": "Escenario A",
            "metrics": [{"metric_type": "waist", "mode": "delta_absolute", "value": "-4.40"}],
        }
        payload.update(kwargs)
        response = self.client.post(f"/api/profiles/{pid}/simulations", json=payload)
        assert response.status_code == 201, response.text
        return response.json()


@pytest.fixture
def env() -> ApiEnv:
    return ApiEnv()


class TestCreateEndpoint:
    def test_creates_queued_scenario(self, env):
        pid = env.profile()

        body = env.simulate(pid)

        assert body["status"] == "queued"
        assert body["data_kind"] == "simulation"
        assert body["engine_version"] == "1.0.0"
        assert body["baseline_hash"]
        assert body["disclaimer"]
        assert "simulation" in body["disclaimer"].lower() or "hipotético" in body["disclaimer"]

    def test_draft_without_run(self, env):
        pid = env.profile()
        body = env.simulate(pid, run_now=False)
        assert body["status"] == "draft"

    def test_rejects_height_parameter(self, env):
        pid = env.profile()
        response = env.client.post(
            f"/api/profiles/{pid}/simulations",
            json={
                "label": "X",
                "metrics": [{"metric_type": "height", "mode": "delta_absolute", "value": "2"}],
            },
        )
        assert response.status_code == 422

    def test_rejects_inverted_sign_overflow(self, env):
        pid = env.profile()
        response = env.client.post(
            f"/api/profiles/{pid}/simulations",
            json={
                "label": "X",
                "metrics": [{"metric_type": "waist", "mode": "delta_percent", "value": "-45"}],
            },
        )
        assert response.status_code == 422
        assert "supera" in response.text

    def test_rejects_duplicate_metric(self, env):
        pid = env.profile()
        response = env.client.post(
            f"/api/profiles/{pid}/simulations",
            json={
                "label": "X",
                "metrics": [
                    {"metric_type": "waist", "mode": "delta_absolute", "value": "-1"},
                    {"metric_type": "waist", "mode": "delta_percent", "value": "-1"},
                ],
            },
        )
        assert response.status_code == 422

    def test_missing_baseline_metric_is_422(self, env):
        pid = env.profile()
        response = env.client.post(
            f"/api/profiles/{pid}/simulations",
            json={
                "label": "X",
                "metrics": [{"metric_type": "chest", "mode": "delta_absolute", "value": "-2"}],
            },
        )
        assert response.status_code == 422
        assert "vigente" in response.text

    def test_requires_auth(self, env):
        pid = env.profile()
        env.app.dependency_overrides.pop(get_current_user, None)
        response = env.client.get(f"/api/profiles/{pid}/simulations")
        assert response.status_code == 401


class TestRunAndCompare:
    def test_execution_then_comparison(self, env):
        pid = env.profile()
        created = env.simulate(pid)

        worker(env.services).run_once()

        detail = env.client.get(f"/api/simulations/{created['id']}").json()
        assert detail["status"] == "completed"
        assert detail["result_checksum"]

        comparison = env.client.get(f"/api/simulations/{created['id']}/comparison")
        assert comparison.status_code == 200
        body = comparison.json()
        assert body["data_kind"] == "simulation"
        assert body["baseline"]["metrics"]
        assert body["scenario"]["metrics"][0]["metric_type"] == "waist"
        assert body["scenario"]["metrics"][0]["value"] == 83.6
        assert "waist_height" in body["derived"]
        assert "escenario hipotético" in body["banner"].lower()
        assert body["warnings"]

    def test_run_endpoint_for_draft(self, env):
        pid = env.profile()
        draft = env.simulate(pid, run_now=False)

        run = env.client.post(f"/api/simulations/{draft['id']}/run")

        assert run.status_code == 200
        assert run.json()["status"] == "queued"

    def test_archive_endpoint(self, env):
        pid = env.profile()
        created = env.simulate(pid)
        worker(env.services).run_once()

        archived = env.client.post(f"/api/simulations/{created['id']}/archive")

        assert archived.status_code == 200
        assert archived.json()["status"] == "archived"
        assert archived.json()["archived_at"]

    def test_lists(self, env):
        pid = env.profile()
        env.simulate(pid)

        by_profile = env.client.get(f"/api/profiles/{pid}/simulations")
        mine = env.client.get("/api/simulations")

        assert by_profile.status_code == 200
        assert by_profile.json()["total"] == 1
        assert mine.json()["total"] == 1

    def test_limits_endpoint(self, env):
        response = env.client.get("/api/simulations/limits")

        assert response.status_code == 200
        body = response.json()
        assert body["max_delta_percent"] == 30.0
        assert body["height_as_reference_only"] is True
        assert {row["metric_type"] for row in body["metrics"]} == {
            "weight",
            "waist",
            "hip",
            "chest",
            "arm",
            "thigh",
        }

    def test_stranger_cannot_read(self, env):
        pid = env.profile()
        created = env.simulate(pid)
        stranger = env.services.new_user("beto")
        env.login(stranger)

        assert env.client.get(f"/api/simulations/{created['id']}").status_code == 404


class TestIsolation:
    """La API de simulación no se filtra a los endpoints observados."""

    def test_measurements_endpoint_unchanged(self, env):
        pid = env.profile()
        before = env.client.get(
            f"/api/profiles/{pid}/measurements", params={"metric_type": "weight"}
        ).json()["total"]

        env.simulate(pid)
        worker(env.services).run_once()

        after = env.client.get(
            f"/api/profiles/{pid}/measurements", params={"metric_type": "weight"}
        ).json()["total"]
        assert after == before

    def test_analytics_endpoint_unchanged(self, env):
        pid = env.profile()
        before = env.client.get(f"/api/profiles/{pid}/analytics").json()

        env.simulate(pid)
        worker(env.services).run_once()

        after = env.client.get(f"/api/profiles/{pid}/analytics").json()
        assert after["total_measurements"] == before["total_measurements"]
        assert [t["last_value"] for t in after["trends"]] == [
            t["last_value"] for t in before["trends"]
        ]

    def test_reports_reject_simulation_kind(self, env):
        pid = env.profile()
        response = env.client.post(
            f"/api/profiles/{pid}/reports", json={"kind": "simulation_pdf"}
        )
        assert response.status_code == 422

    def test_dashboard_does_not_count_simulations(self, env):
        pid = env.profile()
        env.simulate(pid)
        worker(env.services).run_once()

        response = env.client.get("/api/dashboard/summary")

        assert response.status_code == 200
        # Las simulaciones no son mediciones ni estimaciones: no aparecen en el resumen.
        assert response.json()["measurements_total"] == 4
        assert response.json()["pose_analyses_total"] == 0
        assert "simulation" not in response.text.lower()
