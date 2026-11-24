from __future__ import annotations

from app.services.dashboard_service import DashboardService
from tests.fakes import build_services
from tests.test_reports_service import _env, _measurements, _profile


def _service(env) -> DashboardService:
    return DashboardService(
        env.profiles_repo,
        env.analytics_repo,
        env.pose_repo,
        env.audit,
        env.tx,
        clock=env.clock,
    )


class TestDashboardSummary:
    def test_counts_only_accessible_profiles(self):
        env = _env()
        owner = env.new_user("ana")
        other = env.new_user("beto")
        pid = _profile(env, owner, "BV-001")
        _measurements(env, owner, pid)
        _profile(env, other, "BV-002")

        summary = _service(env).summary(owner)

        assert summary.profiles_total == 1
        assert summary.profiles_active == 1
        assert summary.measurements_total == 5
        assert summary.profiles_without_measurements == 0

    def test_profiles_without_measurements_are_counted(self):
        env = _env()
        owner = env.new_user("ana")
        _profile(env, owner, "BV-001")

        summary = _service(env).summary(owner)

        assert summary.measurements_total == 0
        assert summary.profiles_without_measurements == 1

    def test_pose_is_counted_separately_from_measurements(self):
        env = _env()
        owner = env.new_user("ana")
        pid = _profile(env, owner)
        _measurements(env, owner, pid)

        summary = _service(env).summary(owner)

        # Nunca se suman: las estimaciones de pose no son mediciones observadas.
        assert summary.measurements_total == 5
        assert summary.pose_analyses_total == 0
        assert summary.pose_by_status == {}

    def test_recent_profiles_include_measurement_counts(self):
        env = _env()
        owner = env.new_user("ana")
        pid = _profile(env, owner)
        _measurements(env, owner, pid)

        summary = _service(env).summary(owner)

        assert len(summary.recent_profiles) == 1
        recent = summary.recent_profiles[0]
        assert recent.profile_id == pid
        assert recent.display_code == "BV-001"
        assert recent.measurement_count == 5
        assert recent.last_measurement_at is not None

    def test_summary_is_audited(self):
        env = _env()
        owner = env.new_user("ana")
        _profile(env, owner)

        _service(env).summary(owner)

        assert "dashboard.viewed" in env.audit_repo.actions()

    def test_empty_state(self):
        env = _env()
        owner = env.new_user("ana")

        summary = _service(env).summary(owner)

        assert summary.profiles_total == 0
        assert summary.measurements_total == 0
        assert summary.recent_profiles == ()
        assert summary.pose_by_status == {}


def test_build_services_has_report_and_analytics_services():
    env = build_services()
    assert env.reports is not None
    assert env.analytics is not None
