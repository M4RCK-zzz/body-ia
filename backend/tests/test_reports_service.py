from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.core.errors import BusinessRuleError, ConflictError, NotFoundError
from app.domain.measurements import (
    MeasurementMethod,
    MeasurementType,
    MeasurementUnit,
    NewMeasurement,
)
from app.domain.reports import DISCLAIMER, ReportKind, ReportStatus
from app.workers.report_worker import ReportWorker
from tests.fakes import build_services

UTC = UTC
BASE = datetime(2026, 11, 1, 9, 0, tzinfo=UTC)


def _env(clock=None):
    return build_services()


def _settings():
    from app.core.config import Settings

    return Settings(
        database_url="postgresql+psycopg://test:test@localhost:5432/test",
        jwt_secret="test-secret-only-for-pytest-0123456789-abcdef",
        report_poll_seconds=1,
        report_stale_processing_seconds=600,
    )


def _measurements(env, owner, pid, values=(72.0, 72.4, 72.1, 71.8, 72.2)):
    for index, value in enumerate(values):
        env.measurements.record(
            owner,
            pid,
            NewMeasurement(
                metric_type=MeasurementType.WEIGHT,
                value=Decimal(str(value)),
                unit=MeasurementUnit.KG,
                measured_at=BASE + timedelta(days=index),
                method=MeasurementMethod.SCALE,
                created_by=owner.full_name,
            ),
        )


def _profile(env, owner, code="BV-001"):
    pid = env.profile_for(owner, code)
    env.accept_consent(owner, pid)
    return pid


def _worker(env, now=None):
    return ReportWorker(
        env.storage,
        _settings(),
        report_repo=env.reports_repo,
        analytics=env.analytics,
        pose_repo=env.pose_repo,
        audit=env.audit,
        tx=env.tx,
        clock=(lambda: now) if now else env.clock,
    )


class TestRequest:
    def test_enqueue_snapshot_and_audit(self):
        env = _env()
        owner = env.new_user("ana")
        pid = _profile(env, owner)

        report, created = env.reports.request(
            owner, pid, kind=ReportKind.MEASUREMENTS_CSV, date_from=None, date_to=None
        )

        assert created is True
        assert report.status == ReportStatus.QUEUED.value
        assert report.data_kind == "observed"
        assert report.format == "csv"
        assert report.requested_by_snapshot == owner.full_name
        assert report.parameters_json["profile_code"] == "BV-001"
        assert "report.requested" in env.audit_repo.actions()

    def test_idempotent_returns_same_report(self):
        env = _env()
        owner = env.new_user("ana")
        pid = _profile(env, owner)

        first, created_first = env.reports.request(
            owner, pid, kind=ReportKind.POSE_PDF, date_from=None, date_to=None
        )
        second, created_second = env.reports.request(
            owner, pid, kind=ReportKind.POSE_PDF, date_from=None, date_to=None
        )

        assert created_first is True
        assert created_second is False
        assert second.id == first.id
        assert len(env.reports_repo.items) == 1

    def test_pose_report_is_never_marked_observed(self):
        env = _env()
        owner = env.new_user("ana")
        pid = _profile(env, owner)

        report, _ = env.reports.request(
            owner, pid, kind=ReportKind.POSE_CSV, date_from=None, date_to=None
        )

        assert report.data_kind == "visual_estimate"
        assert report.data_kind != "observed"

    def test_rejects_inverted_dates(self):
        env = _env()
        owner = env.new_user("ana")
        pid = _profile(env, owner)

        with pytest.raises(BusinessRuleError):
            env.reports.request(
                owner,
                pid,
                kind=ReportKind.MEASUREMENTS_CSV,
                date_from=BASE + timedelta(days=5),
                date_to=BASE,
            )

    def test_requires_access(self):
        env = _env()
        owner = env.new_user("ana")
        stranger = env.new_user("beto")
        pid = _profile(env, owner)

        # El guard no filtra la existencia del expediente a quien no tiene acceso.
        with pytest.raises(NotFoundError):
            env.reports.request(
                stranger, pid, kind=ReportKind.MEASUREMENTS_CSV, date_from=None, date_to=None
            )


class TestWorkerGeneration:
    def test_measurements_csv_is_generated_and_stored_privately(self):
        env = _env()
        owner = env.new_user("ana")
        pid = _profile(env, owner)
        _measurements(env, owner, pid)
        report, _ = env.reports.request(
            owner, pid, kind=ReportKind.MEASUREMENTS_CSV, date_from=None, date_to=None
        )

        assert _worker(env).run_once() is True

        assert report.status == ReportStatus.GENERATED.value
        assert report.storage_key.endswith(".csv")
        assert report.size_bytes and report.size_bytes > 0
        assert len(report.checksum_sha256) == 64
        data = env.storage.get(report.storage_key)
        text = data.decode("utf-8")
        assert "# data_kind;observed" in text
        assert "72.20" in text
        assert DISCLAIMER.split(".")[0] in text

    def test_measurements_pdf_is_a_real_pdf(self):
        env = _env()
        owner = env.new_user("ana")
        pid = _profile(env, owner)
        _measurements(env, owner, pid)
        report, _ = env.reports.request(
            owner, pid, kind=ReportKind.MEASUREMENTS_PDF, date_from=None, date_to=None
        )

        _worker(env).run_once()

        data = env.storage.get(report.storage_key)
        assert data.startswith(b"%PDF-")
        assert data.rstrip().endswith(b"%%EOF")
        assert report.summary_json["measurements"] == 5

    def test_pose_report_uses_visual_estimate_kind(self):
        env = _env()
        owner = env.new_user("ana")
        pid = _profile(env, owner)
        report, _ = env.reports.request(
            owner, pid, kind=ReportKind.POSE_CSV, date_from=None, date_to=None
        )

        _worker(env).run_once()

        text = env.storage.get(report.storage_key).decode("utf-8")
        assert report.status == ReportStatus.GENERATED.value
        assert "visual_estimate" in text
        assert "observed" not in text

    def test_generation_failure_is_recorded(self):
        env = _env()
        owner = env.new_user("ana")
        pid = _profile(env, owner)
        report, _ = env.reports.request(
            owner, pid, kind=ReportKind.MEASUREMENTS_CSV, date_from=None, date_to=None
        )
        env.storage.fail_on_put = True

        _worker(env).run_once()

        assert report.status == ReportStatus.FAILED.value
        assert report.storage_key is None
        assert report.error_message
        assert "report.failed" in env.audit_repo.actions()

    def test_no_pending_returns_false(self):
        env = _env()
        assert _worker(env).run_once() is False

    def test_stale_processing_is_failed(self):
        env = _env()
        owner = env.new_user("ana")
        pid = _profile(env, owner)
        report, _ = env.reports.request(
            owner, pid, kind=ReportKind.MEASUREMENTS_CSV, date_from=None, date_to=None
        )
        report.status = ReportStatus.PROCESSING.value
        report.started_at = BASE - timedelta(days=5)

        worker = _worker(env, now=BASE + timedelta(days=1))
        assert worker.mark_stale() == 1
        assert report.status == ReportStatus.FAILED.value


class TestContent:
    def _generated(self, env, owner, pid):
        _measurements(env, owner, pid)
        report, _ = env.reports.request(
            owner, pid, kind=ReportKind.MEASUREMENTS_CSV, date_from=None, date_to=None
        )
        _worker(env).run_once()
        return report

    def test_download_returns_bytes_and_audits(self):
        env = _env()
        owner = env.new_user("ana")
        pid = _profile(env, owner)
        report = self._generated(env, owner, pid)

        _, data = env.reports.content(owner, report.id)

        assert data.startswith(b"# BODYVISION AI")
        assert "report.downloaded" in env.audit_repo.actions()

    def test_download_before_generation_is_rejected(self):
        env = _env()
        owner = env.new_user("ana")
        pid = _profile(env, owner)
        report, _ = env.reports.request(
            owner, pid, kind=ReportKind.MEASUREMENTS_CSV, date_from=None, date_to=None
        )

        # 409: el recurso existe pero el binario todavía no se generó.
        with pytest.raises(ConflictError):
            env.reports.content(owner, report.id)

    def test_checksum_mismatch_is_rejected(self):
        env = _env()
        owner = env.new_user("ana")
        pid = _profile(env, owner)
        report = self._generated(env, owner, pid)
        # Simula un binario alterado fuera del flujo del worker.
        env.storage.files[report.storage_key] = b"manipulado"

        # 409: el recurso existe pero el binario todavía no se generó.
        with pytest.raises(ConflictError):
            env.reports.content(owner, report.id)

    def test_unknown_report_is_not_found(self):
        env = _env()
        owner = env.new_user("ana")

        with pytest.raises(NotFoundError):
            env.reports.content(owner, owner.id)

    def test_stranger_cannot_download(self):
        env = _env()
        owner = env.new_user("ana")
        stranger = env.new_user("beto")
        pid = _profile(env, owner)
        report = self._generated(env, owner, pid)

        with pytest.raises(NotFoundError):
            env.reports.content(stranger, report.id)


class TestListings:
    def test_list_for_profile_and_mine(self):
        env = _env()
        owner = env.new_user("ana")
        pid = _profile(env, owner)
        env.reports.request(
            owner, pid, kind=ReportKind.MEASUREMENTS_CSV, date_from=None, date_to=None
        )
        env.reports.request(owner, pid, kind=ReportKind.POSE_PDF, date_from=None, date_to=None)

        rows, total = env.reports.list_for_profile(owner, pid)
        mine, mine_total = env.reports.list_mine(owner)

        assert total == 2 and len(rows) == 2
        assert mine_total == 2

    def test_mine_hides_revoked_profiles(self):
        env = _env()
        owner = env.new_user("ana")
        editor = env.new_user("beto")
        pid = _profile(env, owner)
        env.grant_direct(pid, editor, "editor")
        env.reports.request(editor, pid, kind=ReportKind.POSE_CSV, date_from=None, date_to=None)
        env.access_service.revoke(owner, pid, editor.id)

        mine, total = env.reports.list_mine(editor)

        assert total == 0 and mine == []
