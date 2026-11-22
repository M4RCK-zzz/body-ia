from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.domain.pose import PoseAnalysisStatus
from app.workers.pose_runner import PoseModelError, PoseResult
from app.workers.pose_worker import PoseWorker
from tests.fakes import build_services


def _make_result(visible_count=30, pose_count=1, quality="good", flags=None) -> PoseResult:
    landmarks = [
        {
            "index": i, "x": 0.1 * i, "y": 0.2 * i, "z": 0.0,
            "visibility": 0.9 if i < visible_count else 0.2,
        }
        for i in range(33)
    ]
    return PoseResult(
        landmarks=landmarks,
        visible_count=visible_count,
        total_count=33,
        quality=quality,
        flags=flags if flags is not None else ["pose_complete"],
        pose_count=pose_count,
        model_name="pose_landmarker_full",
        model_version="abc123def456",
        model_sha256="a" * 64,
        mediapipe_version="1.2.3",
        image_width=64,
        image_height=96,
    )


class FakeRunner:
    """Ejecutor fake: no depende de mediapipe ni de archivos .task."""

    def __init__(self, result: PoseResult | None = None, error: Exception | None = None):
        self._result = result
        self._error = error
        self.calls: list[dict] = []

    def analyze(self, image_bytes, **kwargs):
        self.calls.append({"kwargs": kwargs, "bytes": image_bytes})
        if self._error is not None:
            raise self._error
        return self._result


def _build(env, runner, clock=None):
    from app.services.audit_service import AuditRecorder
    from tests.fakes import InMemoryAuditRepository

    audit_repo = InMemoryAuditRepository()
    audit = AuditRecorder(audit_repo, clock=clock or (lambda: datetime.now(UTC)))
    settings = _settings()
    worker = PoseWorker(
        env.storage,
        settings,
        runner=runner,
        pose_repo=env.pose_repo,
        media_repo=env.media_repo,
        audit=audit,
        tx=env.tx,
        clock=clock or (lambda: datetime.now(UTC)),
    )
    return worker, audit_repo


def _settings():
    # Sin DATABASE_URL ni JWT_SECRET: la construcción es config-only; los umbrales solo
    # se leen en _finalize/_fail, y los valores por defecto son correctos para los tests.
    import os

    from app.core.config import Settings

    os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@localhost:5432/test")
    os.environ.setdefault("JWT_SECRET", "test-secret-only-for-pytest-0123456789-abcdef")
    return Settings(
        database_url="postgresql+psycopg://test:test@localhost:5432/test",
        jwt_secret="test-secret-only-for-pytest-0123456789-abcdef",
        pose_complete_threshold=25,
        pose_review_threshold=10,
    )


def _enqueue_task(env, owner):
    from tests.fakes import InMemoryMediaRepository  # noqa: F401

    pid_code = "BV-001"
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (32, 32), (10, 20, 30)).save(buf, "JPEG")

    pid = env.profile_for(owner, pid_code)
    env.accept_consent(owner, pid)
    asset = env.media.upload(owner, pid, data=buf.getvalue(), declared_mime="image/jpeg")
    analysis, created = env.pose.enqueue(owner, asset.id)
    assert created is True
    return pid, asset, analysis


class TestWorkerHappyPath:
    def test_complete_pose_persists_completed(self):
        env = build_services()
        owner = env.new_user("ana")
        pid, asset, analysis = _enqueue_task(env, owner)
        runner = FakeRunner(result=_make_result(visible_count=30, quality="good"))
        worker, audit_repo = _build(env, runner)

        assert worker.run_once() is True

        task = env.pose_repo.items[0]
        assert task.status == PoseAnalysisStatus.COMPLETED.value
        assert task.completed_at is not None
        assert task.duration_ms is not None
        assert task.model_version == "abc123def456"
        assert task.landmarks_json is not None
        assert len(task.landmarks_json["landmarks"]) == 33
        assert task.quality_flags_json["quality"] == "good"
        assert "pose.completed" in audit_repo.actions()

    def test_partial_pose_needs_review(self):
        env = build_services()
        owner = env.new_user("ana")
        pid, asset, analysis = _enqueue_task(env, owner)
        runner = FakeRunner(
            result=_make_result(visible_count=15, quality="partial", flags=["pose_partial"])
        )
        worker, audit_repo = _build(env, runner)

        assert worker.run_once() is True

        task = env.pose_repo.items[0]
        assert task.status == PoseAnalysisStatus.NEEDS_REVIEW.value
        assert task.landmarks_json is not None
        assert task.quality_flags_json["quality"] == "partial"
        assert "pose.needs_review" in audit_repo.actions()

    def test_low_visibility_fails(self):
        env = build_services()
        owner = env.new_user("ana")
        pid, asset, analysis = _enqueue_task(env, owner)
        runner = FakeRunner(
            result=_make_result(visible_count=3, quality="low", flags=["low_visibility"])
        )
        worker, audit_repo = _build(env, runner)

        assert worker.run_once() is True

        task = env.pose_repo.items[0]
        assert task.status == PoseAnalysisStatus.FAILED.value
        assert task.landmarks_json is None  # failed no guarda landmarks
        assert task.quality_flags_json is not None
        assert "pose.failed" in audit_repo.actions()


class TestWorkerFailures:
    def test_model_unavailable_fails(self):
        env = build_services()
        owner = env.new_user("ana")
        pid, asset, analysis = _enqueue_task(env, owner)
        runner = FakeRunner(error=PoseModelError("Modelo de pose no encontrado"))
        worker, audit_repo = _build(env, runner)

        assert worker.run_once() is True

        task = env.pose_repo.items[0]
        assert task.status == PoseAnalysisStatus.FAILED.value
        assert "Modelo" in task.error_message
        assert "pose.failed" in audit_repo.actions()

    def test_asset_deleted_fails(self):
        env = build_services()
        owner = env.new_user("ana")
        pid, asset, analysis = _enqueue_task(env, owner)
        asset.status = "deleted"
        runner = FakeRunner(result=_make_result())
        worker, audit_repo = _build(env, runner)

        assert worker.run_once() is True

        task = env.pose_repo.items[0]
        assert task.status == PoseAnalysisStatus.FAILED.value

    def test_storage_missing_file_fails(self):
        env = build_services()
        owner = env.new_user("ana")
        pid, asset, analysis = _enqueue_task(env, owner)
        env.storage.files.pop(asset.storage_key, None)
        runner = FakeRunner(result=_make_result())
        worker, audit_repo = _build(env, runner)

        assert worker.run_once() is True

        task = env.pose_repo.items[0]
        assert task.status == PoseAnalysisStatus.FAILED.value

    def test_no_pending_work_returns_false(self):
        env = build_services()
        runner = FakeRunner(result=_make_result())
        worker, _ = _build(env, runner)
        assert worker.run_once() is False


class TestWorkerStale:
    def test_stale_processing_marked_failed(self):
        env = build_services()
        owner = env.new_user("ana")
        pid, asset, analysis = _enqueue_task(env, owner)
        # Force the task to a stale processing state
        analysis.status = PoseAnalysisStatus.PROCESSING.value
        analysis.started_at = datetime.now(UTC) - timedelta(hours=2)
        runner = FakeRunner(result=_make_result())
        worker, _ = _build(env, runner)

        worker.mark_stale()

        assert analysis.status == PoseAnalysisStatus.FAILED.value
        assert analysis.error_message == "processing_stale"


class TestWorkerIdempotency:
    def test_task_processed_once(self):
        """Una tarea procesada no se reprocesa en la siguiente pasada."""
        env = build_services()
        owner = env.new_user("ana")
        pid, asset, analysis = _enqueue_task(env, owner)
        runner = FakeRunner(result=_make_result(visible_count=30))
        worker, _ = _build(env, runner)

        assert worker.run_once() is True
        assert worker.run_once() is False  # nada pendiente
        assert len(env.pose_repo.items) == 1
