from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.core.clock import utcnow
from app.core.errors import BusinessRuleError, NotFoundError
from app.core.security_errors import PermissionDeniedError
from app.domain.access import AccessLevel
from app.domain.enums import DataKind
from app.domain.identity import AuditAction
from app.domain.measurements import MeasurementType
from app.domain.metrics import MetricCatalog
from app.domain.profiles import ProfileStatus
from app.domain.simulation import (
    ENGINE_NAME,
    ENGINE_VERSION,
    SIMULABLE_METRICS,
    SIMULATION_BANNER,
    SIMULATION_DISCLAIMER,
    Baseline,
    BaselinePoint,
    EngineLimits,
    ParameterMode,
    SimulationError,
    SimulationStatus,
    apply_scenario,
    build_baseline,
    parse_parameters,
)
from app.models.identity import User
from app.models.measurement import Measurement
from app.models.profile import Profile
from app.models.simulation import Simulation, SimulationBaseline
from app.repositories.measurement_repository import MeasurementRepository
from app.repositories.simulation_repository import SimulationRepository
from app.services.access_guard import AccessGuard
from app.services.audit_service import AuditRecorder
from app.services.consent_service import ConsentService
from app.services.ports import Transaction

logger = logging.getLogger(__name__)

MAX_ACTIVE_PER_PROFILE = 20
MAX_LABEL = 80
MAX_NOTES = 500


class SimulationService:
    """Escenarios hipotéticos (Fase 8).

    Nunca escribe mediciones: sólo lee la medición **vigente** de cada métrica,
    copia su snapshot a `simulation_baselines` y calcula el resultado con el motor
    puro de `app.domain.simulation`.
    """

    def __init__(
        self,
        guard: AccessGuard,
        simulations: SimulationRepository,
        measurements: MeasurementRepository,
        consents: ConsentService,
        catalog: MetricCatalog,
        audit: AuditRecorder,
        tx: Transaction,
        clock: Callable[[], datetime] = utcnow,
        *,
        max_delta_percent: Decimal = Decimal("30"),
        max_active_per_profile: int = MAX_ACTIVE_PER_PROFILE,
    ) -> None:
        self._guard = guard
        self._simulations = simulations
        self._measurements = measurements
        self._consents = consents
        self._catalog = catalog
        self._audit = audit
        self._tx = tx
        self._clock = clock
        self._max_delta_percent = max_delta_percent
        self._max_active_per_profile = max_active_per_profile

    # --- configuración del motor ---

    def _limits(self) -> EngineLimits:
        contract: dict[str, tuple[str, str]] = {}
        for metric in SIMULABLE_METRICS + (MeasurementType.HEIGHT,):
            spec = self._catalog.get(metric)
            if spec is None:  # pragma: no cover - el catálogo siempre los incluye
                continue
            contract[metric.value] = (str(spec.min_value), str(spec.max_value))
        return EngineLimits(max_delta_percent=self._max_delta_percent, contract=contract)

    def limits_contract(self) -> dict[str, dict[str, Any]]:
        """Contrato expuesto a la UI: modos, límites y rangos técnicos."""
        spec_rows = []
        for metric in SIMULABLE_METRICS:
            spec = self._catalog.get(metric)
            if spec is None:  # pragma: no cover
                continue
            spec_rows.append(
                {
                    "metric_type": metric.value,
                    "label": spec.label,
                    "unit": spec.unit.value,
                    "min_value": float(spec.min_value),
                    "max_value": float(spec.max_value),
                }
            )
        return {
            "engine": {"name": ENGINE_NAME, "version": ENGINE_VERSION},
            "modes": [mode.value for mode in ParameterMode],
            "max_delta_percent": float(self._max_delta_percent),
            "metrics": spec_rows,
            "height_as_reference_only": True,
            "derived": ["waist_height", "waist_hip"],
            "disclaimer": SIMULATION_DISCLAIMER,
        }

    # --- permisos ---

    def _read_access(self, actor: User, profile_id: UUID) -> Profile:
        profile, _ = self._guard.require(profile_id, actor, AccessLevel.VIEWER)
        return profile

    def _write_access(self, actor: User, profile_id: UUID) -> Profile:
        profile, _ = self._guard.require(profile_id, actor, AccessLevel.EDITOR)
        if profile.status != ProfileStatus.ACTIVE.value:
            raise BusinessRuleError("El expediente no está activo: no admite escenarios.")
        self._consents.ensure_valid(profile_id)
        return profile

    # --- base ---

    def _baseline_rows(self, profile: Profile, metric_types: Sequence[str]) -> list[Measurement]:
        wanted = [MeasurementType(metric) for metric in metric_types]
        latest = self._measurements.latest_current_by_metric(profile.id, wanted)
        missing = [metric for metric in metric_types if metric not in latest]
        if missing:
            raise BusinessRuleError(
                "No hay medición vigente para: " + ", ".join(sorted(missing))
                + ". Registra una medición o excluye esas métricas del escenario."
            )
        return [latest[metric] for metric in metric_types]

    @staticmethod
    def _baseline_metrics(simulated: Sequence[str]) -> list[str]:
        needed = set(simulated)
        if MeasurementType.WAIST.value in needed:
            needed |= {MeasurementType.HEIGHT.value, MeasurementType.HIP.value}
        return sorted(needed)

    @staticmethod
    def _baseline_from_rows(rows: Sequence[Measurement]) -> Baseline:
        return build_baseline(
            [
                BaselinePoint(
                    metric_type=row.metric_type,
                    measurement_id=str(row.id),
                    value=Decimal(row.value),
                    unit=row.unit,
                    measured_at=row.measured_at,
                )
                for row in rows
            ]
        )

    # --- creación ---

    def create(
        self,
        actor: User,
        profile_id: UUID,
        *,
        label: str,
        parameters: Sequence[dict[str, Any]],
        notes: str | None = None,
        run_now: bool = True,
    ) -> tuple[Simulation, bool]:
        """Crea el escenario (y lo encola si `run_now`). Nunca modifica mediciones."""
        profile = self._write_access(actor, profile_id)

        clean_label = (label or "").strip()
        if not 1 <= len(clean_label) <= MAX_LABEL:
            raise BusinessRuleError(
                f"El nombre del escenario debe tener entre 1 y {MAX_LABEL} caracteres."
            )
        if notes is not None and len(notes) > MAX_NOTES:
            raise BusinessRuleError(f"La nota no puede superar {MAX_NOTES} caracteres.")

        try:
            parsed = parse_parameters(parameters)
        except SimulationError as exc:
            raise BusinessRuleError(str(exc)) from exc

        active = self._simulations.count_active_for_profile(profile_id)
        if active >= self._max_active_per_profile:
            raise BusinessRuleError(
                "Has alcanzado el límite de escenarios activos de este expediente "
                f"({self._max_active_per_profile}). Archiva uno antes de crear otro."
            )

        # La base incluye las métricas simuladas **y** los componentes de los
        # indicadores derivados (estatura y cadera cuando se simula cintura), para
        # que el comparador sea autocontenido y no dependa de leer datos vivos.
        needed = self._baseline_metrics([item.metric_type for item in parsed])
        rows = self._baseline_rows(profile, needed)
        baseline = self._baseline_from_rows(rows)
        limits = self._limits()
        now = self._clock()

        # Validación previa del motor: no dejamos escenarios imposibles en cola.
        try:
            apply_scenario(baseline, parsed, limits=limits)
        except SimulationError as exc:
            raise BusinessRuleError(str(exc)) from exc

        status = SimulationStatus.QUEUED if run_now else SimulationStatus.DRAFT
        simulation = Simulation(
            profile_id=profile.id,
            label=clean_label,
            status=status.value,
            data_kind=DataKind.SIMULATION.value,
            engine_name=ENGINE_NAME,
            engine_version=ENGINE_VERSION,
            engine_config=limits.as_config(),
            parameters_json={
                "metrics": [
                    {
                        "metric_type": item.metric_type,
                        "mode": item.mode,
                        "value": str(item.value),
                    }
                    for item in parsed
                ]
            },
            baseline_hash=baseline.hash,
            notes=notes,
            created_by_user_id=actor.id,
            created_by_snapshot=actor.full_name,
            created_at=now,
            queued_at=now if run_now else None,
            attempt_count=0,
        )
        self._simulations.add(simulation)
        for row in rows:
            self._simulations.add_baseline(
                SimulationBaseline(
                    simulation_id=simulation.id,
                    metric_type=row.metric_type,
                    measurement_id=row.id,
                    value_snapshot=Decimal(row.value),
                    unit=row.unit,
                    measured_at=row.measured_at,
                )
            )

        self._record(
            AuditAction.SIMULATION_CREATED,
            actor.id,
            simulation,
            {
                "engine_version": ENGINE_VERSION,
                "baseline_hash": baseline.hash,
                "metrics": [item.metric_type for item in parsed],
                "status": simulation.status,
            },
        )
        if run_now:
            self._record(AuditAction.SIMULATION_QUEUED, actor.id, simulation, {"queued": True})
        self._tx.commit()
        return simulation, True

    # --- ejecución ---

    def run(self, actor: User, simulation_id: UUID) -> Simulation:
        """Encuela un escenario en `draft` (el worker lo calcula)."""
        simulation = self._get_for_write(actor, simulation_id)
        if simulation.status != SimulationStatus.DRAFT.value:
            raise BusinessRuleError("Sólo se puede ejecutar un escenario en borrador.")
        simulation.status = SimulationStatus.QUEUED.value
        simulation.queued_at = self._clock()
        self._simulations.save(simulation)
        self._record(AuditAction.SIMULATION_QUEUED, actor.id, simulation, {"queued": True})
        self._tx.commit()
        return simulation

    # --- lectura ---

    def _get(self, simulation_id: UUID) -> Simulation:
        simulation = self._simulations.get(simulation_id)
        if simulation is None:
            raise NotFoundError("Escenario no encontrado.")
        return simulation

    def _get_for_write(self, actor: User, simulation_id: UUID) -> Simulation:
        simulation = self._get(simulation_id)
        self._write_access(actor, simulation.profile_id)
        return simulation

    def get(self, actor: User, simulation_id: UUID) -> Simulation:
        simulation = self._get(simulation_id)
        self._read_access(actor, simulation.profile_id)
        return simulation

    def list_for_profile(
        self,
        actor: User,
        profile_id: UUID,
        *,
        status: str | None = None,
        include_archived: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Simulation], int]:
        self._read_access(actor, profile_id)
        return self._simulations.list_page(
            profile_id=profile_id,
            status=status,
            include_archived=include_archived,
            limit=min(max(limit, 1), 200),
            offset=max(offset, 0),
        )

    def list_mine(
        self,
        actor: User,
        *,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Simulation], int]:
        return self._simulations.list_page_for_user(
            created_by_user_id=actor.id,
            status=status,
            limit=min(max(limit, 1), 200),
            offset=max(offset, 0),
        )

    def comparison(self, actor: User, simulation_id: UUID) -> dict[str, Any]:
        """Base guardada vs resultado del escenario. No recalcula ni lee series observadas."""
        simulation = self.get(actor, simulation_id)
        baselines = self._simulations.baselines_for(simulation.id)

        # Sólo para detectar correcciones posteriores a la base; nunca se recalcula.
        current = self._measurements.latest_current_by_metric(
            simulation.profile_id, [MeasurementType(row.metric_type) for row in baselines]
        )

        baseline_rows = []
        for row in baselines:
            live = current.get(row.metric_type)
            baseline_rows.append(
                {
                    "metric_type": row.metric_type,
                    "measurement_id": str(row.measurement_id),
                    "value": float(row.value_snapshot),
                    "unit": row.unit,
                    "measured_at": row.measured_at.isoformat(),
                    "superseded_since": live is not None
                    and str(live.id) != str(row.measurement_id),
                }
            )

        result = simulation.result_json or {}
        scenario_metrics = []
        for metric, payload in sorted((result.get("metrics") or {}).items()):
            scenario_metrics.append(
                {
                    "metric_type": metric,
                    "value": float(payload["simulated"]),
                    "unit": payload.get("unit"),
                    "delta_absolute": float(payload["delta_absolute"]),
                    "delta_percent": None
                    if payload.get("delta_percent") is None
                    else float(payload["delta_percent"]),
                    "clamped": bool(payload.get("clamped")),
                }
            )

        self._record(
            AuditAction.SIMULATION_VIEWED,
            actor.id,
            simulation,
            {"comparison": True, "engine_version": simulation.engine_version},
        )
        self._tx.commit()

        return {
            "simulation_id": str(simulation.id),
            "profile_id": str(simulation.profile_id),
            "label": simulation.label,
            "status": simulation.status,
            "data_kind": simulation.data_kind,
            "engine": {"name": simulation.engine_name, "version": simulation.engine_version},
            "baseline_hash": simulation.baseline_hash,
            "created_at": simulation.created_at.isoformat(),
            "created_by": simulation.created_by_snapshot,
            "result_checksum": simulation.result_checksum,
            "baseline": {"captured_from": "measurements_vigentes", "metrics": baseline_rows},
            "scenario": {"metrics": scenario_metrics},
            "derived": result.get("derived") or {},
            "unchanged": result.get("unchanged") or [],
            "warnings": result.get("warnings") or [],
            "disclaimer": SIMULATION_DISCLAIMER,
            "banner": SIMULATION_BANNER,
        }

    # --- archivado ---

    def archive(self, actor: User, simulation_id: UUID) -> Simulation:
        simulation = self._get(simulation_id)
        profile, grant = self._guard.require(simulation.profile_id, actor, AccessLevel.EDITOR)
        is_author = simulation.created_by_user_id == actor.id
        if not is_author and grant.level != AccessLevel.OWNER.value:
            raise PermissionDeniedError(
                "Sólo el autor del escenario o el propietario del expediente pueden archivarlo.",
                code="insufficient_access",
            )
        if profile.status == ProfileStatus.RESTRICTED.value:
            raise BusinessRuleError("El expediente está restringido: no admite cambios.")
        if simulation.status not in (
            SimulationStatus.COMPLETED.value,
            SimulationStatus.DRAFT.value,
            SimulationStatus.FAILED.value,
        ):
            raise BusinessRuleError(
                "Sólo se archiva un escenario completado, fallido o en borrador."
            )

        # Sólo se marca el cierre: si el escenario nunca se ejecutó no se inventa
        # un resultado ni una fecha de finalización.
        simulation.status = SimulationStatus.ARCHIVED.value
        simulation.archived_at = self._clock()
        self._simulations.save(simulation)
        self._record(AuditAction.SIMULATION_ARCHIVED, actor.id, simulation, {"archived": True})
        self._tx.commit()
        return simulation

    # --- auditoría ---

    def _record(
        self, action: AuditAction, actor_id: UUID, simulation: Simulation, detail: dict[str, Any]
    ) -> None:
        self._audit.record(
            action,
            actor_id=actor_id,
            resource_type="simulation",
            resource_id=str(simulation.id),
            profile_id=simulation.profile_id,
            detail=detail,
        )
