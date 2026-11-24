"""Worker de retención y purga (Fase 9, decisión D14).

Hasta la Fase 8 `MEDIA_RETENTION_DAYS` solo se *guardaba* en `retention_until`:
nada lo aplicaba. Este worker cumple la promesa, con tres reglas duras:

1. **`DRY_RUN=true` por defecto.** Sin `RETENTION_DRY_RUN=false` solo informa de
   lo que borraría; no toca un byte. Es el estado seguro tras un despliegue.
2. **Nunca toca lo observado.** `measurements`, `pose_analyses`, `audit_events`,
   `reports` vigentes y `simulations` no archivadas quedan fuera del alcance por
   construcción (el worker no tiene repositorios de esas tablas).
3. **Todo borrado se audita** (`*.purged`) con el id del recurso y la política
   aplicada. La fila no se borra: el asset pasa a `deleted` y conserva su traza.

Alcance:

- `media_assets` en `ready`/`rejected` con `retention_until < now`.
- `reports` `generated`/`failed` con `completed_at` más antiguo que
  `REPORT_RETENTION_DAYS` → se borra el binario del storage y la fila se marca
  con `storage_key` vaciado… **no**: eso rompería el CHECK del modelo. En su
  lugar, el binario se elimina del storage y se mantiene la fila con el checksum
  para auditoría; el estado `generated` pasa a `failed` con `error_message`
  `retention_purged` (el CHECK lo permite) y se limpia `storage_key`/checksum.
- `simulations` en `archived` con `archived_at` más antiguo que
  `SIMULATION_RETENTION_DAYS` → sus `simulation_baselines` se conservan (son la
  traza); solo se limpia `result_json`, que es recalculable desde parámetros.
"""

from __future__ import annotations

import logging
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.core.config import Settings
from app.domain.identity import AuditAction
from app.integrations.storage import StorageBackend
from app.services.ports import Transaction
from app.workers.heartbeat import Heartbeat

logger = logging.getLogger(__name__)

RETENTION_REASON = "retention_purged"


@dataclass(frozen=True, slots=True)
class PurgeReport:
    """Resumen de una pasada. Se audita y se devuelve para el log."""

    media: int = 0
    reports: int = 0
    simulations: int = 0
    dry_run: bool = True

    @property
    def total(self) -> int:
        return self.media + self.reports + self.simulations


class RetentionWorker:
    def __init__(
        self,
        settings: Settings,
        *,
        media_repo,
        report_repo,
        simulation_repo,
        storage: StorageBackend,
        audit,
        tx: Transaction,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        heartbeat_repo=None,
    ) -> None:
        self._settings = settings
        self._media = media_repo
        self._reports = report_repo
        self._simulations = simulation_repo
        self._storage = storage
        self._audit = audit
        self._tx = tx
        self._clock = clock
        self._heartbeat = Heartbeat("retention", heartbeat_repo, tx, clock=clock)

    # --- pasada ---

    def run_once(self) -> PurgeReport:
        now = self._clock()
        dry_run = self._settings.retention_dry_run
        report = PurgeReport(
            media=self._purge_media(now, dry_run),
            reports=self._purge_reports(now, dry_run),
            simulations=self._purge_simulations(now, dry_run),
            dry_run=dry_run,
        )
        self._tx.commit()
        if report.total:
            logger.info(
                "retención%s: media=%d reportes=%d escenarios=%d",
                " (DRY RUN, sin cambios)" if dry_run else "",
                report.media,
                report.reports,
                report.simulations,
            )
        self._heartbeat.beat()
        return report

    # --- recursos ---

    def _purge_media(self, now: datetime, dry_run: bool) -> int:
        rows = self._media.expired_for_retention(now)
        for asset in rows:
            if dry_run:
                logger.info("DRY RUN: borraría media %s (retención vencida)", asset.id)
                continue
            if asset.storage_key:
                try:
                    self._storage.delete(asset.storage_key)
                except Exception:
                    logger.warning("No se pudo borrar el binario de %s", asset.id, exc_info=True)
            asset.status = "deleted"
            asset.deleted_at = now
            self._media.save(asset)
            self._audit.record(
                AuditAction.MEDIA_PURGED,
                actor_id=None,
                resource_type="media_asset",
                resource_id=str(asset.id),
                profile_id=asset.profile_id,
                detail={"policy": "media_retention_days", "size_bytes": asset.size_bytes},
            )
        return len(rows)

    def _purge_reports(self, now: datetime, dry_run: bool) -> int:
        cutoff = now - timedelta(days=self._settings.report_retention_days)
        rows = self._reports.expired_for_retention(cutoff)
        for report in rows:
            if dry_run:
                logger.info("DRY RUN: purgaría reporte %s (%s)", report.id, report.status)
                continue
            if report.storage_key:
                try:
                    self._storage.delete(report.storage_key)
                except Exception:
                    logger.warning("No se pudo borrar el PDF de %s", report.id, exc_info=True)
            report.status = "failed"
            report.storage_key = None
            report.checksum_sha256 = None
            report.error_message = RETENTION_REASON
            self._reports.save(report)
            self._audit.record(
                AuditAction.REPORT_PURGED,
                actor_id=None,
                resource_type="report",
                resource_id=str(report.id),
                profile_id=report.profile_id,
                detail={"policy": "report_retention_days", "kind": report.kind},
            )
        return len(rows)

    def _purge_simulations(self, now: datetime, dry_run: bool) -> int:
        cutoff = now - timedelta(days=self._settings.simulation_retention_days)
        rows = self._simulations.expired_for_retention(cutoff)
        for simulation in rows:
            if dry_run:
                logger.info("DRY RUN: limpiaría el resultado de %s", simulation.id)
                continue
            simulation.result_json = None
            self._simulations.save(simulation)
            self._audit.record(
                AuditAction.SIMULATION_PURGED,
                actor_id=None,
                resource_type="simulation",
                resource_id=str(simulation.id),
                profile_id=simulation.profile_id,
                detail={"policy": "simulation_retention_days"},
            )
        return len(rows)


def run_forever(worker: RetentionWorker, poll_seconds: float) -> int:
    logger.info("worker de retención iniciado (poll=%.1fs)", poll_seconds)
    try:
        while True:
            try:
                worker.run_once()
            except Exception:
                logger.exception("Error inesperado en la pasada de retención")
            time.sleep(poll_seconds)
    except KeyboardInterrupt:
        logger.info("worker de retención detenido por el usuario")
        return 0


def main(argv=None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Worker de retención y purga (Fase 9)")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Ejecuta una pasada y termina (recomendado con el Programador de tareas)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Fuerza RETENTION_DRY_RUN=false en esta ejecución (borra de verdad)",
    )
    args = parser.parse_args(argv)

    from app.core.config import get_settings
    from app.core.logging import configure_logging
    from app.db.session import SessionLocal
    from app.db.transaction import SessionTransaction
    from app.integrations.storage import LocalStorageBackend
    from app.repositories.sqlalchemy_audit_repository import SqlAlchemyAuditRepository
    from app.repositories.sqlalchemy_media_repository import SqlAlchemyMediaRepository
    from app.repositories.sqlalchemy_report_repository import SqlAlchemyReportRepository
    from app.repositories.sqlalchemy_simulation_repository import (
        SqlAlchemySimulationRepository,
    )
    from app.repositories.worker_heartbeat_repository import (
        SqlAlchemyWorkerHeartbeatRepository,
    )
    from app.services.audit_service import AuditRecorder

    settings = get_settings()
    if args.apply:
        settings = settings.model_copy(update={"retention_dry_run": False})
    configure_logging(settings.log_level, json_output=settings.json_logs)
    if settings.retention_dry_run:
        logger.warning(
            "RETENTION_DRY_RUN=true: la pasada solo informa, no borra nada "
            "(usa --apply o RETENTION_DRY_RUN=false para purgar de verdad)"
        )

    session = SessionLocal()
    try:
        worker = RetentionWorker(
            settings,
            media_repo=SqlAlchemyMediaRepository(session),
            report_repo=SqlAlchemyReportRepository(session),
            simulation_repo=SqlAlchemySimulationRepository(session),
            storage=LocalStorageBackend(settings.upload_dir),
            audit=AuditRecorder(SqlAlchemyAuditRepository(session)),
            tx=SessionTransaction(session),
            heartbeat_repo=SqlAlchemyWorkerHeartbeatRepository(session),
        )
        if args.once:
            worker.run_once()
            return 0
        return run_forever(worker, settings.retention_poll_seconds)
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
