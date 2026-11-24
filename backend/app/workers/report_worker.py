"""Worker de reportes (Fase 7): generación asíncrona en cola PostgreSQL.

Mismo patrón que el worker de pose (Fase 5), sin Redis ni Celery:

1. Marca failed los reportes `processing` con `started_at` más antiguo que el umbral.
2. Reserva el siguiente `queued` con `SELECT ... FOR UPDATE SKIP LOCKED`.
3. Marca `processing`, calcula los datos (solo lecturas) y renderiza CSV/PDF.
4. Escribe el binario en el storage privado (clave UUID + extensión).
5. Persiste `generated` (checksum SHA-256, tamaño, resumen) o `failed`, con auditoría.
6. Commit por iteración.

El binario **nunca** entra en PostgreSQL: solo la clave y el checksum.
"""
from __future__ import annotations

import hashlib
import logging
import sys
import time
from collections.abc import Callable
from datetime import timedelta
from typing import Any
from uuid import uuid4

from app.core.clock import utcnow
from app.core.config import Settings
from app.domain.identity import AuditAction
from app.domain.reports import (
    CONTENT_TYPES,
    REPORT_DATA_KIND,
    REPORT_FORMAT,
    ReportStatus,
    is_measurement_report,
)
from app.integrations.storage import StorageBackend
from app.models.report import Report
from app.services.analytics_service import AnalyticsService
from app.services.audit_service import AuditRecorder
from app.services.ports import Transaction
from app.services.report_renderers import ReportContext, render_report

logger = logging.getLogger(__name__)

STALE_REASON = "processing_stale"


class ReportWorker:
    """Generador de reportes. Inyectable para pruebas sin BD ni storage real."""

    def __init__(
        self,
        storage: StorageBackend,
        settings: Settings,
        *,
        report_repo,
        analytics: AnalyticsService,
        pose_repo,
        audit: AuditRecorder,
        tx: Transaction,
        clock: Callable = utcnow,
    ) -> None:
        self._storage = storage
        self._settings = settings
        self._reports = report_repo
        self._analytics = analytics
        self._pose_repo = pose_repo
        self._audit = audit
        self._tx = tx
        self._clock = clock

    # --- internas ---

    def _audit_record(self, action: str, report: Report, detail: dict[str, Any]) -> None:
        self._audit.record(
            action,
            actor_id=report.requested_by_user_id,
            resource_type="report",
            resource_id=str(report.id),
            profile_id=report.profile_id,
            detail=detail,
        )

    def _duration_ms(self, started_at, finished_at) -> int:
        delta = finished_at - started_at
        return max(
            delta.days * 86_400_000 + delta.seconds * 1000 + delta.microseconds // 1000, 0
        )

    def _fail_and_commit(self, report: Report, reason_code: str, message: str) -> None:
        now = self._clock()
        report.status = ReportStatus.FAILED.value
        report.error_message = message[:300]
        report.completed_at = now
        if report.started_at is not None:
            report.duration_ms = self._duration_ms(report.started_at, now)
        self._reports.save(report)
        self._audit_record(
            AuditAction.REPORT_FAILED,
            report,
            {"kind": report.kind, "reason": reason_code},
        )
        self._tx.commit()

    def _context(self, report: Report) -> ReportContext:
        params = report.parameters_json or {}
        requested_at = report.created_at or self._clock()
        return ReportContext(
            report_id=str(report.id),
            profile_code=str(params.get("profile_code") or "—"),
            data_kind=report.data_kind,
            requested_by=str(params.get("requested_by") or report.requested_by_snapshot),
            requested_at=requested_at,
            date_from=report.date_from,
            date_to=report.date_to,
        )

    def _build(self, report: Report) -> tuple[bytes, str, dict[str, Any]]:
        """Calcula los datos y renderiza. Devuelve (bytes, mime, resumen)."""
        context = self._context(report)
        metric_types = None
        if report.metrics_json:
            from app.domain.measurements import MeasurementType

            metric_types = [MeasurementType(value) for value in report.metrics_json]

        if is_measurement_report(report.kind):
            series = self._analytics.series_rows(
                self._requester(report),
                report.profile_id,
                date_from=report.date_from,
                date_to=report.date_to,
                metric_types=metric_types,
            )
            data, mime = render_report(kind=report.kind, context=context, series=series)
            summary = {
                "metrics": [
                    {
                        "metric_type": trend.metric_type,
                        "count": trend.count,
                        "corrected_count": trend.corrected_count,
                        "first_at": trend.first_at.isoformat() if trend.first_at else None,
                        "last_at": trend.last_at.isoformat() if trend.last_at else None,
                        "outlier_count": trend.outlier_count,
                    }
                    for trend, _points in series
                ],
                "measurements": sum(trend.count for trend, _ in series),
                "data_kind": REPORT_DATA_KIND[report.kind],
            }
            return data, mime, summary

        analyses, total = self._pose_repo.list_page(
            profile_id=report.profile_id,
            status=None,
            limit=500,
            offset=0,
        )
        if report.date_from is not None:
            analyses = [a for a in analyses if a.created_at >= report.date_from]
        if report.date_to is not None:
            analyses = [a for a in analyses if a.created_at <= report.date_to]
        data, mime = render_report(kind=report.kind, context=context, analyses=analyses)
        summary = {
            "pose_analyses": len(analyses),
            "pose_analyses_total_profile": total,
            "data_kind": REPORT_DATA_KIND[report.kind],
            "note": "Estimaciones visuales: no son mediciones y no se mezclan con ellas.",
        }
        return data, mime, summary

    def _requester(self, report: Report):
        """Actor para las lecturas internas del worker (acceso ya validado al encolar)."""
        return _Requester(
            id=report.requested_by_user_id,
            full_name=report.requested_by_snapshot,
        )

    # --- operaciones ---

    def mark_stale(self) -> int:
        stale_before = self._clock() - timedelta(
            seconds=self._settings.report_stale_processing_seconds
        )
        return self._reports.mark_stale_failed(
            stale_before, now=self._clock(), reason=STALE_REASON
        )

    def claim_next(self) -> Report | None:
        return self._reports.claim_next()

    def run_once(self) -> bool:
        """Procesa un reporte. True si trabajó, False si no había nada pendiente."""
        try:
            stale_count = self.mark_stale()
            if stale_count:
                logger.info("marcados como failed %d reportes stale", stale_count)
            self._tx.commit()
        except Exception:
            self._tx.rollback()
            logger.exception("Error en la pasada stale de reportes")

        try:
            report = self.claim_next()
        except Exception:
            self._tx.rollback()
            logger.exception("Error al reservar el siguiente reporte")
            return False
        if report is None:
            self._tx.commit()
            return False

        report.status = ReportStatus.PROCESSING.value
        report.started_at = self._clock()
        self._reports.save(report)

        try:
            data, mime, summary = self._build(report)
        except Exception as exc:  # noqa: BLE001 - cualquier fallo se registra como failed
            logger.exception("Error al generar el reporte %s", report.id)
            self._fail_and_commit(report, "generation_failed", f"Error de generación: {exc}")
            return True

        # El storage nunca sobrescribe: clave nueva por intento.
        storage_key = f"{uuid4()}.{REPORT_FORMAT[report.kind]}"
        try:
            self._storage.put(storage_key, data)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Error al escribir el reporte %s en storage", report.id)
            self._fail_and_commit(report, "storage_unavailable", f"No se pudo guardar: {exc}")
            return True

        now = self._clock()
        report.status = ReportStatus.GENERATED.value
        report.storage_key = storage_key
        report.checksum_sha256 = hashlib.sha256(data).hexdigest()
        report.size_bytes = len(data)
        report.mime_type = mime or CONTENT_TYPES[REPORT_FORMAT[report.kind]]
        report.summary_json = summary
        report.completed_at = now
        report.error_message = None
        if report.started_at is not None:
            report.duration_ms = self._duration_ms(report.started_at, now)
        self._reports.save(report)
        self._audit_record(
            AuditAction.REPORT_GENERATED,
            report,
            {
                "kind": report.kind,
                "format": report.format,
                "checksum_sha256": report.checksum_sha256,
                "size_bytes": report.size_bytes,
                **{k: v for k, v in summary.items() if k != "metrics"},
            },
        )
        self._tx.commit()
        return True

    def run_forever(self, poll_seconds: float | None = None) -> int:
        poll = poll_seconds if poll_seconds is not None else self._settings.report_poll_seconds
        logger.info(
            "worker de reportes iniciado (poll=%.1fs, staleness=%ds)",
            poll,
            self._settings.report_stale_processing_seconds,
        )
        try:
            while True:
                try:
                    self.run_once()
                except Exception:
                    logger.exception("Error inesperado en run_once (reportes)")
                time.sleep(poll)
        except KeyboardInterrupt:
            logger.info("worker de reportes detenido por el usuario")
            return 0


class _Requester:
    """Actor mínimo para reutilizar AccessGuard en las lecturas del worker."""

    def __init__(self, *, id, full_name: str) -> None:
        self.id = id
        self.full_name = full_name


def main(argv=None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Worker de generación de reportes (Fase 7)")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Procesa lo pendiente y termina (útil para depurar o para el Programador de tareas)",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s"
    )
    from app.core.config import get_settings
    from app.db.session import SessionLocal
    from app.db.transaction import SessionTransaction
    from app.domain.metrics import default_catalog
    from app.integrations.storage import LocalStorageBackend
    from app.repositories.sqlalchemy_access_repository import (
        SqlAlchemyProfileAccessRepository,
    )
    from app.repositories.sqlalchemy_analytics_repository import SqlAlchemyAnalyticsRepository
    from app.repositories.sqlalchemy_audit_repository import SqlAlchemyAuditRepository
    from app.repositories.sqlalchemy_pose_repository import SqlAlchemyPoseRepository
    from app.repositories.sqlalchemy_profile_repository import SqlAlchemyProfileRepository
    from app.repositories.sqlalchemy_report_repository import SqlAlchemyReportRepository
    from app.services.access_guard import AccessGuard
    from app.services.analytics_service import AnalyticsService

    settings = get_settings()
    storage = LocalStorageBackend(settings.upload_dir)
    session = SessionLocal()
    try:
        audit_repo = SqlAlchemyAuditRepository(session)
        audit = AuditRecorder(audit_repo)
        tx = SessionTransaction(session)
        guard = AccessGuard(
            SqlAlchemyProfileRepository(session),
            SqlAlchemyProfileAccessRepository(session),
            audit,
            tx,
        )
        analytics = AnalyticsService(
            guard,
            SqlAlchemyAnalyticsRepository(session),
            default_catalog(),
            audit,
            tx,
        )
        worker = ReportWorker(
            storage,
            settings,
            report_repo=SqlAlchemyReportRepository(session),
            analytics=analytics,
            pose_repo=SqlAlchemyPoseRepository(session),
            audit=audit,
            tx=tx,
        )
        if args.once:
            while worker.run_once():
                pass
            return 0
        return worker.run_forever()
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
