from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID
from app.core.clock import utcnow
from app.core.errors import BusinessRuleError, ConflictError, NotFoundError
from app.domain.measurements import (
    MeasurementCorrection,
    MeasurementMethod,
    MeasurementType,
    MeasurementUnit,
    NewMeasurement,
)
from app.domain.metrics import MetricCatalog, MetricSpec
from app.domain.profiles import ProfileStatus
from app.models.measurement import Measurement
from app.models.profile import Profile
from app.repositories.measurement_repository import MeasurementRepository
from app.repositories.profile_repository import ProfileRepository
from app.services.ports import Transaction

_FUTURE_TOLERANCE = timedelta(minutes=5)
_MIN_DATE = datetime(1900, 1, 1, tzinfo=UTC)
_CENTS = Decimal("0.01")

@dataclass(frozen=True, slots=True)
class MeasurementView:
    measurement: Measurement
    is_current: bool

@dataclass(frozen=True, slots=True)
class SeriesData:
    metric_type: MeasurementType
    unit: MeasurementUnit
    points: list[Measurement]

class MeasurementService:
    def __init__(
        self,
        profiles: ProfileRepository,
        measurements: MeasurementRepository,
        catalog: MetricCatalog,
        tx: Transaction,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        self._profiles = profiles
        self._measurements = measurements
        self._catalog = catalog
        self._tx = tx
        self._clock = clock

    def record(self, profile_id: UUID, data: NewMeasurement) -> MeasurementView:
        self._require_writable_profile(profile_id)
        spec = self._validate_value(data.metric_type, data.value, data.unit)
        self._validate_measured_at(data.measured_at)
        measurement = Measurement(
            profile_id=profile_id,
            metric_type=data.metric_type.value,
            value=data.value.quantize(_CENTS),
            unit=spec.unit.value,
            measured_at=data.measured_at,
            method=data.method.value,
            created_by=data.created_by,
            notes=data.notes,
        )
        self._measurements.add(measurement)
        self._tx.commit()
        return MeasurementView(measurement, True)

    def correct(
        self, profile_id: UUID, measurement_id: UUID, data: MeasurementCorrection
    ) -> MeasurementView:
        self._require_writable_profile(profile_id)
        original = self._measurements.get(measurement_id, profile_id)
        if original is None:
            raise NotFoundError("Medición no encontrada.")
        if self._measurements.is_superseded(original.id):
            raise ConflictError("Esta medición ya fue corregida; corrige la versión vigente.")

        metric_type = MeasurementType(original.metric_type)
        spec = self._validate_value(metric_type, data.value, MeasurementUnit(original.unit))
        if data.measured_at is not None:
            self._validate_measured_at(data.measured_at)

        corrected = Measurement(
            profile_id=profile_id,
            metric_type=original.metric_type,
            value=data.value.quantize(_CENTS),
            unit=spec.unit.value,
            measured_at=data.measured_at or original.measured_at,
            method=(data.method or MeasurementMethod(original.method)).value,
            created_by=data.created_by,
            notes=data.notes,
            supersedes_id=original.id,
            correction_reason=data.reason,
        )
        self._measurements.add(corrected)
        self._tx.commit()
        return MeasurementView(corrected, True)

    def get(self, profile_id: UUID, measurement_id: UUID) -> MeasurementView:
        self._require_profile(profile_id)
        measurement = self._measurements.get(measurement_id, profile_id)
        if measurement is None:
            raise NotFoundError("Medición no encontrada.")
        return MeasurementView(measurement, not self._measurements.is_superseded(measurement.id))

    def list_measurements(
        self,
        profile_id: UUID,
        *,
        metric_type: MeasurementType | None = None,
        include_superseded: bool = False,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[MeasurementView], int]:
        self._require_profile(profile_id)
        rows, total = self._measurements.list_page(
            profile_id=profile_id,
            metric_type=metric_type,
            only_current=not include_superseded,
            date_from=date_from,
            date_to=date_to,
            ascending=False,
            limit=limit,
            offset=offset,
        )
        if not include_superseded:
            return [MeasurementView(m, True) for m in rows], total
        replaced = self._measurements.superseded_among(m.id for m in rows)
        return [MeasurementView(m, m.id not in replaced) for m in rows], total

    def series(
        self, profile_id: UUID, metric_type: MeasurementType, *, max_points: int = 2000
    ) -> SeriesData:
        self._require_profile(profile_id)
        spec = self._catalog.get(metric_type)
        if spec is None:
            raise BusinessRuleError(f"La métrica '{metric_type.value}' no está habilitada.")
        rows, _ = self._measurements.list_page(
            profile_id=profile_id,
            metric_type=metric_type,
            only_current=True,
            date_from=None,
            date_to=None,
            ascending=True,
            limit=max_points,
            offset=0,
        )
        return SeriesData(metric_type=metric_type, unit=spec.unit, points=rows)

    def history(self, profile_id: UUID, measurement_id: UUID) -> list[MeasurementView]:
        self._require_profile(profile_id)
        chain = self._measurements.get_chain(measurement_id, profile_id)
        if not chain:
            raise NotFoundError("Medición no encontrada.")
        last_id = chain[-1].id
        return [MeasurementView(m, m.id == last_id) for m in chain]

    def _require_profile(self, profile_id: UUID) -> Profile:
        profile = self._profiles.get(profile_id)
        if profile is None:
            raise NotFoundError("Expediente no encontrado.")
        return profile

    def _require_writable_profile(self, profile_id: UUID) -> Profile:
        profile = self._require_profile(profile_id)
        if profile.status != ProfileStatus.ACTIVE.value:
            raise BusinessRuleError("El expediente no está activo: no admite cambios en mediciones.")
        return profile

    def _validate_value(
        self, metric_type: MeasurementType, value: Decimal, unit: MeasurementUnit
    ) -> MetricSpec:
        spec = self._catalog.get(metric_type)
        if spec is None:
            raise BusinessRuleError(f"La métrica '{metric_type.value}' no está habilitada.")
        if unit != spec.unit:
            raise BusinessRuleError(f"{spec.label}: la unidad debe ser {spec.unit.value}.")
        if not spec.contains(value):
            raise BusinessRuleError(
                f"{spec.label}: el valor debe estar entre {spec.min_value} y {spec.max_value} "
                f"{spec.unit.value} (rango técnico de plausibilidad)."
            )
        return spec

    def _validate_measured_at(self, measured_at: datetime) -> None:
        if measured_at > self._clock() + _FUTURE_TOLERANCE:
            raise BusinessRuleError("La fecha de medición no puede estar en el futuro.")
        if measured_at < _MIN_DATE:
            raise BusinessRuleError("La fecha de medición es demasiado antigua.")