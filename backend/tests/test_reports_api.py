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
)
from app.api.security import get_current_user
from app.main import create_app
from app.services.dashboard_service import DashboardService
from tests.fakes import build_services


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

    def accept_consent(self, pid: str) -> None:
        r = self.client.post(
            f"/api/profiles/{pid}/consents",
            json={"purpose": "data_processing", "declaration": True},
        )
        assert r.status_code == 201, r.text

    def profile(self, code: str = "BV-001", *, consent: bool = True) -> str:
        r = self.client.post("/api/profiles", json={"display_code": code})
        assert r.status_code == 201, r.text
        pid = r.json()["id"]
        if consent:
            self.accept_consent(pid)
        return pid

    def measure(self, pid: str) -> None:
        r = self.client.post(
            f"/api/profiles/{pid}/measurements",
            json={
                "metric_type": "weight",
                "value": 72.4,
                "unit": "kg",
                "measured_at": "2026-11-10T09:00:00+00:00",
                "method": "scale",
            },
        )
        assert r.status_code == 201, r.text


@pytest.fixture
def env() -> ApiEnv:
    return ApiEnv()


def _report_service(env: ApiEnv):
    return env.app.dependency_overrides[get_report_service]()


class TestAnalyticsEndpoint:
    def test_summary_shape(self, env):
        pid = env.profile()
        env.measure(pid)

        r = env.client.get(f"/api/profiles/{pid}/analytics?window_days=30")

        assert r.status_code == 200, r.text
        body = r.json()
        assert body["data_kind"] == "observed"
        assert body["window_days"] == 30
        weight = next(t for t in body["trends"] if t["metric_type"] == "weight")
        assert weight["count"] == 1
        assert weight["last_value"] == 72.4
        assert "disclaimer" in body

    def test_invalid_window_returns_422(self, env):
        pid = env.profile()
        assert env.client.get(f"/api/profiles/{pid}/analytics?window_days=14").status_code == 422

    def test_no_access_returns_404(self, env):
        pid = env.profile()
        stranger = env.services.new_user("beto")
        env.login(stranger)

        assert env.client.get(f"/api/profiles/{pid}/analytics").status_code == 404

    def test_requires_auth(self, env):
        pid = env.profile()
        env.app.dependency_overrides.pop(get_current_user, None)

        assert env.client.get(f"/api/profiles/{pid}/analytics").status_code == 401


class TestReportsEndpoint:
    def test_request_report_is_queued(self, env):
        pid = env.profile()
        env.measure(pid)

        r = env.client.post(
            f"/api/profiles/{pid}/reports",
            json={"kind": "measurements_csv"},
        )

        assert r.status_code == 201, r.text
        body = r.json()
        assert body["status"] == "queued"
        assert body["data_kind"] == "observed"
        assert body["format"] == "csv"
        assert body["download_url"] is None

    def test_request_is_idempotent(self, env):
        pid = env.profile()
        payload = {"kind": "measurements_pdf"}

        first = env.client.post(f"/api/profiles/{pid}/reports", json=payload)
        second = env.client.post(f"/api/profiles/{pid}/reports", json=payload)

        assert first.status_code == 201
        assert second.status_code == 200
        assert first.json()["id"] == second.json()["id"]

    def test_pose_report_rejects_metrics(self, env):
        pid = env.profile()

        r = env.client.post(
            f"/api/profiles/{pid}/reports",
            json={"kind": "pose_csv", "metrics": ["weight"]},
        )

        assert r.status_code == 422

    def test_inverted_range_is_422(self, env):
        pid = env.profile()
        r = env.client.post(
            f"/api/profiles/{pid}/reports",
            json={
                "kind": "measurements_csv",
                "date_from": "2026-11-20T00:00:00+00:00",
                "date_to": "2026-11-01T00:00:00+00:00",
            },
        )
        assert r.status_code == 422

    def test_generated_report_is_downloadable(self, env):
        from tests.test_reports_service import _worker

        pid = env.profile()
        env.measure(pid)
        created = env.client.post(f"/api/profiles/{pid}/reports", json={"kind": "measurements_csv"})
        report_id = created.json()["id"]

        _worker(env.services).run_once()

        detail = env.client.get(f"/api/reports/{report_id}").json()
        assert detail["status"] == "generated"
        assert detail["download_url"] == f"/api/reports/{report_id}/content"
        assert detail["size_bytes"] > 0

        content = env.client.get(f"/api/reports/{report_id}/content")
        assert content.status_code == 200
        assert content.headers["content-type"].startswith("text/csv")
        assert "attachment" in content.headers["content-disposition"]
        assert content.headers["cache-control"] == "private, no-store"
        assert content.content.startswith(b"# BODYVISION AI")

    def test_download_before_generation_is_409(self, env):
        pid = env.profile()
        report_id = env.client.post(
            f"/api/profiles/{pid}/reports", json={"kind": "measurements_csv"}
        ).json()["id"]

        r = env.client.get(f"/api/reports/{report_id}/content")

        assert r.status_code == 409

    def test_list_my_reports(self, env):
        pid = env.profile()
        env.client.post(f"/api/profiles/{pid}/reports", json={"kind": "pose_csv"})

        r = env.client.get("/api/reports")

        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert body["items"][0]["data_kind"] == "visual_estimate"

    def test_list_by_profile(self, env):
        pid = env.profile()
        env.client.post(f"/api/profiles/{pid}/reports", json={"kind": "measurements_csv"})

        r = env.client.get(f"/api/profiles/{pid}/reports")

        assert r.status_code == 200
        assert r.json()["total"] == 1

    def test_requires_auth(self, env):
        env.profile()
        env.app.dependency_overrides.pop(get_current_user, None)

        assert env.client.get("/api/reports").status_code == 401


class TestDashboardEndpoint:
    def test_summary_uses_real_data(self, env):
        pid = env.profile()
        env.measure(pid)

        r = env.client.get("/api/dashboard/summary")

        assert r.status_code == 200, r.text
        body = r.json()
        assert body["profiles_total"] == 1
        assert body["measurements_total"] == 1
        assert body["pose_analyses_total"] == 0
        assert body["recent_profiles"][0]["display_code"] == "BV-001"
        assert "Disponible en Fase 2" not in r.text

    def test_empty_dashboard(self, env):
        r = env.client.get("/api/dashboard/summary")

        assert r.status_code == 200
        assert r.json()["profiles_total"] == 0
        assert r.json()["pose_by_status"] == {}


def test_reports_expose_the_profile_code_for_context(env: ApiEnv):
    """La lista de `/api/reports` distingue a qué expediente pertenece cada documento.

    El código se lee del `parameters_json` congelado al solicitar el reporte.
    """
    pid = env.profile("BV-042")
    created = env.client.post(
        f"/api/profiles/{pid}/reports", json={"kind": "measurements_csv"}
    )
    assert created.status_code == 201, created.text
    assert created.json()["profile_display_code"] == "BV-042"

    listing = env.client.get("/api/reports")
    assert listing.status_code == 200, listing.text
    assert listing.json()["items"][0]["profile_display_code"] == "BV-042"
