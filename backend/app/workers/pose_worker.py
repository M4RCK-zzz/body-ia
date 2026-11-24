"""Worker de análisis de pose (Fase 5): cola PostgreSQL sin Redis.

Flujo por iteración:
1. Marca failed las tareas processing con started_at más antiguo que el umbral.
2. Reserva la siguiente tarea queued (SELECT ... FOR UPDATE SKIP LOCKED).
3. Marca processing y procesa el modelo (lazy mediapipe).
4. Persiste el resultado (completed / needs_review / failed) + auditoría.
5. Commit por iteración.
"""
from __future__ import annotations

import logging
import sys
import time
from collections.abc import Callable
from datetime import timedelta
from typing import Any

from app.core.clock import utcnow
from app.core.config import Settings
from app.domain.identity import AuditAction
from app.domain.media import MediaStatus
from app.domain.pose import PoseAnalysisStatus
from app.integrations.storage import StorageBackend
from app.integrations.storage.local import LocalStorageBackend
from app.models.pose import PoseAnalysis
from app.services.audit_service import AuditRecorder
from app.services.ports import Transaction
from app.workers.heartbeat import Heartbeat
from app.workers.pose_runner import PoseModelError, PoseModelRunner, PoseResult

logger = logging.getLogger(__name__)

STALE_REASON = "processing_stale"


class PoseWorker:
    """Ejecución de análisis de pose. Inyectable para tests sin BD/modelo."""

    def __init__(
        self,
        storage: StorageBackend,
        settings: Settings,
        runner: PoseModelRunner | None = None,
        *,
        pose_repo,
        media_repo,
        audit: AuditRecorder,
        tx: Transaction,
        heartbeat_repo=None,
        clock: Callable = utcnow,
    ) -> None:
        self._storage = storage
        self._settings = settings
        self._runner = runner if runner is not None else PoseModelRunner(settings.pose_model_path)
        self._pose_repo = pose_repo
        self._media_repo = media_repo
        self._audit = audit
        self._tx = tx
        self._clock = clock
        self._heartbeat = Heartbeat("pose", heartbeat_repo, tx, clock=clock)

    # --- internas ---

    def _audit_record(
        self,
        action: str,
        task: PoseAnalysis,
        detail: dict[str, Any],
    ) -> None:
        self._audit.record(
            action,
            actor_id=task.created_by_user_id,
            resource_type="pose_analysis",
            resource_id=str(task.id),
            profile_id=task.profile_id,
            detail=detail,
        )

    def _fail_and_commit(self, task: PoseAnalysis, reason_code: str, message: str) -> None:
        now = self._clock()
        task.status = PoseAnalysisStatus.FAILED.value
        task.error_message = message[:300]
        task.completed_at = now
        if task.started_at is not None:
            delta = now - task.started_at
            task.duration_ms = max(
                delta.days * 86_400_000 + delta.seconds * 1000 + delta.microseconds // 1000, 0
            )
        self._pose_repo.save(task)
        self._audit_record(
            AuditAction.POSE_FAILED,
            task,
            {"media_asset_id": str(task.media_asset_id), "reason": reason_code},
        )
        self._tx.commit()

    def _finalize(
        self,
        task: PoseAnalysis,
        result: PoseResult,
        analysis_started_at,
    ) -> None:
        now = self._clock()
        delta = now - analysis_started_at
        duration_ms = max(
            delta.days * 86_400_000 + delta.seconds * 1000 + delta.microseconds // 1000, 0
        )
        visible = result.visible_count
        if visible >= self._settings.pose_complete_threshold:
            status = PoseAnalysisStatus.COMPLETED.value
            audit_action = AuditAction.POSE_COMPLETED
        elif visible >= self._settings.pose_review_threshold:
            status = PoseAnalysisStatus.NEEDS_REVIEW.value
            audit_action = AuditAction.POSE_NEEDS_REVIEW
        else:
            status = PoseAnalysisStatus.FAILED.value
            audit_action = AuditAction.POSE_FAILED
        task.status = status
        task.duration_ms = duration_ms
        task.completed_at = now
        task.model_name = result.model_name
        task.model_version = result.model_version
        task.model_config = {
            "model_name": result.model_name,
            "model_sha256": result.model_sha256,
            "model_version_short": result.model_version,
            "mediapipe_version": result.mediapipe_version,
            "visibility_threshold": self._settings.pose_visibility_threshold,
            "complete_threshold": self._settings.pose_complete_threshold,
            "review_threshold": self._settings.pose_review_threshold,
            "image_width": result.image_width,
            "image_height": result.image_height,
        }
        if status in (PoseAnalysisStatus.COMPLETED.value, PoseAnalysisStatus.NEEDS_REVIEW.value):
            task.error_message = None
            task.landmarks_json = {
                "landmarks": result.landmarks,
                "pose_count": result.pose_count,
                "image_width": result.image_width,
                "image_height": result.image_height,
            }
            task.quality_flags_json = {
                "quality": result.quality,
                "flags": result.flags,
                "visible_landmarks": result.visible_count,
                "total_landmarks": result.total_count,
                "visibility_threshold": self._settings.pose_visibility_threshold,
                "pose_count": result.pose_count,
                "model_version": result.model_version,
            }
        else:
            task.error_message = "visibilidad_baja_o_pose_no_detectada"[:300]
            task.landmarks_json = None
            task.quality_flags_json = {
                "quality": result.quality,
                "flags": result.flags,
                "visible_landmarks": result.visible_count,
                "total_landmarks": result.total_count,
                "visibility_threshold": self._settings.pose_visibility_threshold,
                "pose_count": result.pose_count,
                "model_version": result.model_version,
            }
        self._pose_repo.save(task)
        self._audit_record(
            audit_action,
            task,
            {
                "media_asset_id": str(task.media_asset_id),
                "model_version": result.model_version,
                "quality": result.quality,
                "visible_landmarks": result.visible_count,
            },
        )
        self._tx.commit()

    # --- operaciones ---

    def mark_stale(self) -> int:
        stale_before = self._clock() - timedelta(
            seconds=self._settings.pose_stale_processing_seconds
        )
        return self._pose_repo.mark_stale_failed(
            stale_before, now=self._clock(), reason=STALE_REASON
        )

    def claim_next(self) -> PoseAnalysis | None:
        return self._pose_repo.claim_next()

    def run_once(self) -> bool:
        """Procesa una tarea. True si procesó/falló, False si no hay nada pendiente."""
        # 1. Stale pass (commit inmediato)
        try:
            stale_count = self.mark_stale()
            if stale_count:
                logger.info("marcadas como failed %d tareas stale", stale_count)
            self._tx.commit()
        except Exception:
            self._tx.rollback()
            logger.exception("Error en la pasada stale; reintentando en el próximo ciclo")

        # 2. Claim
        try:
            task = self.claim_next()
        except Exception:
            self._tx.rollback()
            logger.exception("Error al reservar la siguiente tarea")
            return False
        if task is None:
            self._tx.commit()
            self._heartbeat.beat()
            return False

        # 3. processing
        task.status = PoseAnalysisStatus.PROCESSING.value
        task.started_at = self._clock()
        self._pose_repo.save(task)

        # 4. Asset + bytes
        media_repo = self._media_repo
        asset = media_repo.get(task.media_asset_id)
        if asset is None:
            self._fail_and_commit(task, "asset_unavailable", "Archivo no disponible.")
            return True
        if asset.status != MediaStatus.READY.value:
            self._fail_and_commit(task, "asset_not_ready", "El archivo ya no está en estado ready.")
            return True
        if not asset.storage_key:
            self._fail_and_commit(
                task, "asset_unavailable", "El archivo no tiene clave de storage."
            )
            return True
        try:
            image_bytes = self._storage.get(asset.storage_key)
        except Exception:
            self._fail_and_commit(task, "asset_unreadable", "No se pudo leer el archivo.")
            return True

        # 5. Model
        try:
            result = self._runner.analyze(
                image_bytes,
                visibility_threshold=self._settings.pose_visibility_threshold,
                complete_threshold=self._settings.pose_complete_threshold,
                review_threshold=self._settings.pose_review_threshold,
            )
        except PoseModelError as exc:
            self._fail_and_commit(task, "model_unavailable", str(exc))
            return True
        except Exception as exc:
            logger.exception("Error inesperado al analizar el pose: %s", task.id)
            self._fail_and_commit(task, "analysis_failed", f"Error de análisis: {exc}"[:300])
            return True

        # 6. Finalize
        analysis_started_at = task.started_at
        try:
            self._finalize(task, result, analysis_started_at)
        except Exception:
            self._tx.rollback()
            logger.exception("Error al persistir el resultado de la tarea %s", task.id)
            return True  # la tarea queda processing en BD; la pasada stale la recupera
        return True

    def run_forever(self, poll_seconds: float | None = None) -> int:
        poll = poll_seconds if poll_seconds is not None else self._settings.pose_poll_seconds
        logger.info(
            "worker pose iniciado (poll=%.1fs, staleness=%ds)",
            poll,
            self._settings.pose_stale_processing_seconds,
        )
        try:
            while True:
                try:
                    self.run_once()
                    self._heartbeat.beat()
                except Exception:
                    logger.exception("Error inesperado en run_once")
                time.sleep(poll)
        except KeyboardInterrupt:
            logger.info("worker pose detenido por el usuario")
            return 0


def main(argv=None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s"
    )
    from app.core.config import get_settings
    from app.db.session import SessionLocal

    settings = get_settings()
    runner = PoseModelRunner(settings.pose_model_path)
    try:
        runner.ensure_ready()
    except PoseModelError as exc:
        logger.error("No se puede arrancar el worker de pose: %s", exc)
        return 2

    from app.db.transaction import SessionTransaction
    from app.repositories.sqlalchemy_audit_repository import SqlAlchemyAuditRepository
    from app.repositories.sqlalchemy_media_repository import SqlAlchemyMediaRepository
    from app.repositories.sqlalchemy_pose_repository import SqlAlchemyPoseRepository
    from app.repositories.worker_heartbeat_repository import (
        SqlAlchemyWorkerHeartbeatRepository,
    )
    from app.services.audit_service import AuditRecorder

    storage = LocalStorageBackend(settings.upload_dir)
    session = SessionLocal()
    try:

        audit = AuditRecorder(SqlAlchemyAuditRepository(session))
        worker = PoseWorker(
            storage,
            settings,
            runner=runner,
            pose_repo=SqlAlchemyPoseRepository(session),
            media_repo=SqlAlchemyMediaRepository(session),
            audit=audit,
            tx=SessionTransaction(session),
            heartbeat_repo=SqlAlchemyWorkerHeartbeatRepository(session),
        )
        return worker.run_forever()
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
