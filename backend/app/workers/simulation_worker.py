"""Worker de simulación (Fase 8): calcula escenarios `queued` con el motor versionado.

Mismo patrón que los workers de Fase 5 (pose) y Fase 7 (reportes), sin Redis ni Celery:

1. Marca `failed` los `queued` abandonados (`queued_at` anterior al umbral).
2. Reserva el siguiente `queued` con `SELECT ... FOR UPDATE SKIP LOCKED`.
3. Marca `started_at`, reconstruye la base desde `simulation_baselines` (fotografía,
   no mediciones vivas) y ejecuta `apply_scenario`.
4. Persiste `result_json` + `result_checksum` y audita `simulation.completed`.

El worker **nunca** escribe en `measurements`: sólo lee la tabla de base del escenario.
"""

from __future__ import annotations

import logging
import sys
import time
from collections.abc import Callable
from datetime import timedelta
from decimal import Decimal
from typing import Any

from app.core.clock import utcnow
from app.core.config import Settings
from app.domain.identity import AuditAction
from app.domain.simulation import (
    Baseline,
    BaselinePoint,
    EngineLimits,
    MetricParameter,
    SimulationError,
    SimulationStatus,
    apply_scenario,
    build_baseline,
)
from app.models.simulation import Simulation
from app.services.audit_service import AuditRecorder
from app.services.ports import Transaction

logger = logging.getLogger(__name__)

STALE_REASON = "queue_stale"


class SimulationWorker:
    def __init__(
        self,
        settings: Settings,
        *,
        simulation_repo,
        audit: AuditRecorder,
        tx: Transaction,
        clock: Callable = utcnow,
    ) -> None:
        self._settings = settings
        self._simulations = simulation_repo
        self._audit = audit
        self._tx = tx
        self._clock = clock

    # --- internas ---

    @staticmethod
    def _duration_ms(started, finished) -> int:
        delta = finished - started
        return max(
            delta.days * 86_400_000 + delta.seconds * 1000 + delta.microseconds // 1000, 0
        )

    def _audit_record(self, action: str, simulation: Simulation, detail: dict[str, Any]) -> None:
        self._audit.record(
            action,
            actor_id=simulation.created_by_user_id,
            resource_type="simulation",
            resource_id=str(simulation.id),
            profile_id=simulation.profile_id,
            detail=detail,
        )

    def _fail_and_commit(
        self, simulation: Simulation, code: str, message: str, started_at
    ) -> None:
        now = self._clock()
        simulation.status = SimulationStatus.FAILED.value
        simulation.error_message = message[:300]
        simulation.completed_at = now
        if started_at is not None:
            simulation.duration_ms = self._duration_ms(started_at, now)
        self._simulations.save(simulation)
        self._audit_record(AuditAction.SIMULATION_FAILED, simulation, {"reason": code})
        self._tx.commit()

    @staticmethod
    def _rebuild_baseline(rows) -> Baseline:
        return build_baseline(
            [
                BaselinePoint(
                    metric_type=row.metric_type,
                    measurement_id=str(row.measurement_id),
                    value=Decimal(row.value_snapshot),
                    unit=row.unit,
                    measured_at=row.measured_at,
                )
                for row in rows
            ]
        )

    @staticmethod
    def _parameters(simulation: Simulation) -> list[MetricParameter]:
        raw = (simulation.parameters_json or {}).get("metrics") or []
        return [
            MetricParameter(
                metric_type=str(item["metric_type"]),
                mode=str(item["mode"]),
                value=Decimal(str(item["value"])),
            )
            for item in raw
        ]

    def _limits(self, simulation: Simulation) -> EngineLimits:
        config = simulation.engine_config or {}
        return EngineLimits(
            max_delta_percent=Decimal(str(config.get("max_delta_percent", "30"))),
            contract=config.get("contract") or {},
        )

    # --- operaciones ---

    def mark_stale(self) -> int:
        stale_before = self._clock() - timedelta(
            seconds=self._settings.simulation_stale_processing_seconds
        )
        return self._simulations.mark_stale_failed(
            stale_before, now=self._clock(), reason=STALE_REASON
        )

    def run_once(self) -> bool:
        try:
            stale = self.mark_stale()
            if stale:
                logger.info("marcados como failed %d escenarios en cola obsoletos", stale)
            self._tx.commit()
        except Exception:
            self._tx.rollback()
            logger.exception("Error en la pasada stale de simulación")

        try:
            simulation = self._simulations.claim_next()
        except Exception:
            self._tx.rollback()
            logger.exception("Error al reservar el siguiente escenario")
            return False
        if simulation is None:
            self._tx.commit()
            return False

        # Sin estado `processing` en el modelo aprobado: la fila sigue `queued`
        # mientras se calcula y se escribe una sola vez al final. El instante de
        # inicio se conserva en memoria para `duration_ms`.
        started_at = self._clock()
        simulation.attempt_count = (simulation.attempt_count or 0) + 1

        try:
            rows = self._simulations.baselines_for(simulation.id)
            if not rows:
                raise SimulationError("El escenario no tiene referencia base registrada.")
            baseline = self._rebuild_baseline(rows)
            if baseline.hash != simulation.baseline_hash:
                # La base guardada no coincide con su hash: no se calcula nada.
                raise SimulationError("La referencia base no supera la verificación de integridad.")
            result = apply_scenario(
                baseline, self._parameters(simulation), limits=self._limits(simulation)
            )
        except SimulationError as exc:
            logger.warning("escenario %s inválido: %s", simulation.id, exc)
            self._fail_and_commit(simulation, "invalid_scenario", str(exc), started_at)
            return True
        except Exception as exc:  # noqa: BLE001 - cualquier fallo se registra como failed
            logger.exception("Error al calcular el escenario %s", simulation.id)
            self._fail_and_commit(
                simulation, "engine_error", f"Error del motor: {exc}", started_at
            )
            return True

        now = self._clock()
        simulation.status = SimulationStatus.COMPLETED.value
        simulation.started_at = started_at
        simulation.result_json = result.as_dict()
        simulation.result_checksum = result.checksum()
        simulation.completed_at = now
        simulation.error_message = None
        simulation.duration_ms = self._duration_ms(started_at, now)
        self._simulations.save(simulation)
        self._audit_record(
            AuditAction.SIMULATION_COMPLETED,
            simulation,
            {
                "engine_version": simulation.engine_version,
                "baseline_hash": simulation.baseline_hash,
                "result_checksum": simulation.result_checksum,
                "metrics": sorted(result.as_dict()["metrics"]),
            },
        )
        self._tx.commit()
        return True

    def run_forever(self, poll_seconds: float | None = None) -> int:
        poll = (
            poll_seconds
            if poll_seconds is not None
            else self._settings.simulation_poll_seconds
        )
        logger.info("worker de simulación iniciado (poll=%.1fs)", poll)
        try:
            while True:
                try:
                    self.run_once()
                except Exception:  # noqa: BLE001 - el worker no debe caerse
                    logger.exception("Error inesperado en run_once (simulación)")
                time.sleep(poll)
        except KeyboardInterrupt:
            logger.info("worker de simulación detenido por el usuario")
            return 0


def main(argv=None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Worker de simulación (Fase 8)")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Procesa los escenarios pendientes y termina (útil para depurar o por lotes)",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s"
    )
    from app.core.config import get_settings
    from app.db.session import SessionLocal
    from app.db.transaction import SessionTransaction
    from app.repositories.sqlalchemy_audit_repository import SqlAlchemyAuditRepository
    from app.repositories.sqlalchemy_simulation_repository import (
        SqlAlchemySimulationRepository,
    )

    settings = get_settings()
    session = SessionLocal()
    try:
        audit = AuditRecorder(SqlAlchemyAuditRepository(session))
        worker = SimulationWorker(
            settings,
            simulation_repo=SqlAlchemySimulationRepository(session),
            audit=audit,
            tx=SessionTransaction(session),
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
