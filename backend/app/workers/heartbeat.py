"""Latido de worker (Fase 9).

Cada pasada del bucle registra que el worker sigue vivo. Se hace en su propia
transacción y **nunca** puede tumbar al worker: un fallo al escribir el latido se
registra y se continúa (el trabajo real es más importante que la telemetría).

`/api/health/workers` compara `last_seen_at` con `WORKER_STALE_SECONDS`.
"""

from __future__ import annotations

import contextlib
import logging
from datetime import UTC, datetime

from app.repositories.worker_heartbeat_repository import WorkerHeartbeatRepository
from app.services.ports import Transaction

logger = logging.getLogger(__name__)

WORKER_VERSION = "0.1.0"


class Heartbeat:
    """Envoltorio tolerante a fallos alrededor del repositorio de latidos."""

    def __init__(
        self,
        name: str,
        repository: WorkerHeartbeatRepository | None,
        tx: Transaction,
        clock=lambda: datetime.now(UTC),
    ) -> None:
        self.name = name
        self._repository = repository
        self._tx = tx
        self._clock = clock

    def beat(self) -> None:
        if self._repository is None:
            return
        try:
            self._repository.beat(self.name, version=WORKER_VERSION, now=self._clock())
            self._tx.commit()
        except Exception:
            logger.warning("no se pudo registrar el latido de %s", self.name, exc_info=True)
            with contextlib.suppress(Exception):
                self._tx.rollback()

    def record_error(self, message: str) -> None:
        if self._repository is None:
            return
        try:
            self._repository.record_error(self.name, message=message, now=self._clock())
            self._tx.commit()
        except Exception:
            logger.warning("no se pudo registrar el error de %s", self.name, exc_info=True)
