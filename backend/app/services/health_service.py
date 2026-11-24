"""Salud del servicio (Fase 9).

Cuatro niveles, con propósitos distintos:

- `live`: el proceso responde. No toca la BD (liveness).
- `health`: compatibilidad con la Fase 1 (estado de la BD).
- `ready`: BD + storage + migración al día. Si algo falla → 503 (readiness).
- `workers`: latidos de los workers frente a `WORKER_STALE_SECONDS`.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.core.config import Settings
from app.integrations.storage import StorageBackend
from app.repositories.health import HealthRepository
from app.repositories.worker_heartbeat_repository import WorkerHeartbeatRepository
from app.schemas.health import (
    ComponentStatus,
    HealthResponse,
    ReadinessResponse,
    WorkerHealth,
    WorkersResponse,
)

# Contrato del storage: se escribe y se borra una clave de prueba efímera.
_PROBE_KEY = "00000000000000000000000000000000"

# Workers que corren en bucle: su latido debe ser reciente para el estado global.
# `retention` es one-shot (se ejecuta con `--once` desde cron o a mano), así que
# su último latido se muestra como información y nunca degrada el servicio.
CONTINUOUS_WORKERS: frozenset[str] = frozenset({"pose", "report", "simulation"})


class HealthService:
    def __init__(
        self,
        repository: HealthRepository,
        settings: Settings,
        *,
        storage: StorageBackend | None = None,
        heartbeats: WorkerHeartbeatRepository | None = None,
    ) -> None:
        self._repository = repository
        self._settings = settings
        self._storage = storage
        self._heartbeats = heartbeats

    def check(self) -> HealthResponse:
        database_up = self._repository.ping()
        return HealthResponse(
            status="ok" if database_up else "degraded",
            service=self._settings.app_name,
            version=self._settings.app_version,
            environment=self._settings.environment,
            database="up" if database_up else "down",
            timestamp=datetime.now(UTC),
        )

    def live(self) -> HealthResponse:
        return HealthResponse(
            status="ok",
            service=self._settings.app_name,
            version=self._settings.app_version,
            environment=self._settings.environment,
            database="up",
            timestamp=datetime.now(UTC),
        )

    def ready(self) -> ReadinessResponse:
        components: list[ComponentStatus] = []

        database_up = self._repository.ping()
        components.append(ComponentStatus(name="database", ok=database_up))

        storage_ok = self._storage_roundtrip()
        components.append(ComponentStatus(name="storage", ok=storage_ok))

        migration_ok, current = self._migration_status()
        components.append(
            ComponentStatus(name="migrations", ok=migration_ok, detail=current)
        )

        return ReadinessResponse(
            status="ok" if all(c.ok for c in components) else "unavailable",
            ready=all(c.ok for c in components),
            service=self._settings.app_name,
            version=self._settings.app_version,
            environment=self._settings.environment,
            components=components,
            timestamp=datetime.now(UTC),
        )

    def workers(self) -> WorkersResponse:
        now = datetime.now(UTC)
        stale_after = self._settings.worker_stale_seconds
        rows = self._heartbeats.list_all() if self._heartbeats is not None else []
        workers = []
        for row in rows:
            last_seen = row.last_seen_at
            if last_seen.tzinfo is None:  # defensa: BD sin tz
                last_seen = last_seen.replace(tzinfo=UTC)
            age = int((now - last_seen).total_seconds())
            continuous = row.name in CONTINUOUS_WORKERS
            workers.append(
                WorkerHealth(
                    name=row.name,
                    version=row.worker_version,
                    continuous=continuous,
                    # Un worker one-shot no puede estar "caído": no hay proceso
                    # esperando. Se informa su última pasada sin evaluar el umbral.
                    alive=(age <= stale_after) if continuous else True,
                    last_seen_at=last_seen,
                    age_seconds=age,
                    iterations=row.iterations,
                    last_error=row.last_error,
                )
            )
        monitored = [w for w in workers if w.continuous]
        return WorkersResponse(
            status="ok"
            if monitored and all(w.alive for w in monitored)
            else ("degraded" if monitored else "unknown"),
            stale_after_seconds=stale_after,
            workers=workers,
            timestamp=now,
        )

    # --- internas ---

    def _storage_roundtrip(self) -> bool:
        """Escritura + lectura + borrado de una clave efímera.

        Detecta volumen de solo lectura, disco lleno o permisos mal puestos, que
        son los fallos que dejan la app viva pero incapaz de guardar capturas.
        """
        if self._storage is None:
            return True
        try:
            payload = b"ready-probe"
            self._storage.put(_PROBE_KEY, payload)
            try:
                return self._storage.get(_PROBE_KEY) == payload
            finally:
                self._storage.delete(_PROBE_KEY)
        except Exception:
            return False

    def _migration_status(self) -> tuple[bool, str | None]:
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        try:
            current = self._repository.current_revision()
        except Exception:
            return False, None
        config = Config("alembic.ini")
        script = ScriptDirectory.from_config(config)
        head = script.get_current_head()
        return current == head, current
