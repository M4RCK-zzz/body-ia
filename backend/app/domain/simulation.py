"""Simulación de escenarios hipotéticos (Fase 8) — dominio puro.

Reglas duras:
- Un escenario es `DataKind.SIMULATION`: nunca crea, modifica ni sustituye mediciones
  observadas. Este módulo no conoce base de datos ni framework.
- Aritmética **determinista** con `Decimal` (nunca `float`), cuantizada a 2 decimales.
- Sin ecuaciones fisiológicas inventadas: cada métrica se mueve sólo por su propio
  parámetro; no se deriva cintura desde peso ni nada equivalente. Los indicadores
  derivados son divisiones de valores ya presentes en la base.
- No hay predicción temporal, ni recomendaciones, ni interpretación clínica.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Any

from app.domain.enums import DataKind
from app.domain.measurements import MeasurementType, MeasurementUnit

ENGINE_NAME = "bodyvision.scenario"
ENGINE_VERSION = "1.0.0"

MIN_METRICS = 1
MAX_METRICS = 4
DEFAULT_MAX_DELTA_PERCENT = Decimal("30")
MIN_MAX_DELTA_PERCENT = Decimal("5")
MAX_MAX_DELTA_PERCENT = Decimal("50")

_CENTS = Decimal("0.01")
_PERCENT = Decimal("0.01")

# `height` no es un parámetro simulable: la estatura no cambia en un escenario de
# corto plazo y usarla como entrada invita a resultados absurdos. Sólo es referencia
# para los indicadores derivados.
SIMULABLE_METRICS: tuple[MeasurementType, ...] = (
    MeasurementType.WEIGHT,
    MeasurementType.WAIST,
    MeasurementType.HIP,
    MeasurementType.CHEST,
    MeasurementType.ARM,
    MeasurementType.THIGH,
)

SIMULATION_DISCLAIMER = (
    "Escenario hipotético calculado con aritmética determinista sobre una copia de "
    "mediciones ya registradas. No describe el cuerpo real, no es una predicción y no "
    "modifica ninguna medición observada. No constituye diagnóstico ni recomendación "
    "clínica, nutricional o de entrenamiento."
)

SCENARIO_WARNINGS: tuple[str, ...] = (
    "escenario_hipotetico",
    "sin_criterio_clinico",
    "no_modifica_mediciones",
)


class SimulationStatus(StrEnum):
    DRAFT = "draft"
    QUEUED = "queued"
    COMPLETED = "completed"
    FAILED = "failed"
    ARCHIVED = "archived"


TERMINAL_SIMULATION_STATUSES: frozenset[str] = frozenset(
    {SimulationStatus.COMPLETED.value, SimulationStatus.ARCHIVED.value}
)
ACTIVE_SIMULATION_STATUSES: frozenset[str] = frozenset(
    {SimulationStatus.DRAFT.value, SimulationStatus.QUEUED.value}
)


class ParameterMode(StrEnum):
    DELTA_ABSOLUTE = "delta_absolute"
    DELTA_PERCENT = "delta_percent"
    TARGET_VALUE = "target_value"


class SimulationError(ValueError):
    """Entrada de escenario inválida (se traduce a 422 en la API)."""


def quantize(value: Decimal) -> Decimal:
    return value.quantize(_CENTS, rounding=ROUND_HALF_UP)


# --- base inmutable ----------------------------------------------------------


@dataclass(frozen=True, slots=True)
class BaselinePoint:
    """Fotografía de una medición observada usada como base del escenario."""

    metric_type: str
    measurement_id: str
    value: Decimal
    unit: str
    measured_at: datetime


@dataclass(frozen=True, slots=True)
class Baseline:
    points: tuple[BaselinePoint, ...]
    hash: str

    def by_metric(self) -> dict[str, BaselinePoint]:
        return {point.metric_type: point for point in self.points}

    def value(self, metric_type: str | MeasurementType) -> Decimal | None:
        point = self.by_metric().get(str(getattr(metric_type, "value", metric_type)))
        return point.value if point is not None else None


def canonical_hash(payload: Mapping[str, Any] | Sequence[Any]) -> str:
    """SHA-256 del JSON canónico (claves ordenadas, sin espacios)."""
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def build_baseline(points: Sequence[BaselinePoint]) -> Baseline:
    """Construye la base y su hash canónico (orden por métrica, valores normalizados)."""
    ordered = tuple(sorted(points, key=lambda point: point.metric_type))
    payload = [
        {
            "metric_type": point.metric_type,
            "measurement_id": point.measurement_id,
            "value": str(quantize(point.value)),
            "unit": point.unit,
            "measured_at": point.measured_at.isoformat(),
        }
        for point in ordered
    ]
    return Baseline(points=ordered, hash=canonical_hash(payload))


# --- parámetros --------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MetricParameter:
    metric_type: str
    mode: str
    value: Decimal


@dataclass(frozen=True, slots=True)
class EngineLimits:
    """Límites efectivos persistidos en `engine_config` (trazabilidad del motor).

    `contract` mapea métrica → (min, max) del catálogo técnico. Se normaliza a
    `Decimal` en la construcción para que el resultado sea independiente de si la
    entrada venía como tupla, lista o dict serializado.
    """

    max_delta_percent: Decimal = DEFAULT_MAX_DELTA_PERCENT
    contract: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not (MIN_MAX_DELTA_PERCENT <= self.max_delta_percent <= MAX_MAX_DELTA_PERCENT):
            raise SimulationError(
                "El límite de cambio debe estar entre "
                f"{MIN_MAX_DELTA_PERCENT}% y {MAX_MAX_DELTA_PERCENT}%."
            )
        normalized: dict[str, tuple[Decimal, Decimal]] = {}
        for metric, bounds in self.contract.items():
            try:
                if isinstance(bounds, Mapping):
                    low, high = bounds["min"], bounds["max"]
                else:
                    low, high = bounds
                normalized[str(metric)] = (Decimal(str(low)), Decimal(str(high)))
            except (KeyError, TypeError, ValueError) as exc:
                raise SimulationError(
                    f"Rango del catálogo inválido para la métrica '{metric}'."
                ) from exc
        object.__setattr__(self, "contract", normalized)

    def as_config(self) -> dict[str, Any]:
        return {
            "max_delta_percent": str(self.max_delta_percent),
            "coupled_metrics": False,
            "rounding": "2_decimals_half_up",
            "modes": [mode.value for mode in ParameterMode],
            "min_metrics": MIN_METRICS,
            "max_metrics": MAX_METRICS,
            "simulable_metrics": [metric.value for metric in SIMULABLE_METRICS],
            "height_as_reference_only": True,
            "derived": ["waist_height", "waist_hip"],
            "contract": {
                metric: {"min": str(bounds[0]), "max": str(bounds[1])}
                for metric, bounds in sorted(self.contract.items())
            },
        }


def parse_parameters(
    parameters: Sequence[MetricParameter] | Sequence[Mapping[str, Any]],
) -> tuple[MetricParameter, ...]:
    """Normaliza y valida la entrada del usuario (sin tocar la base)."""
    items: list[MetricParameter] = []
    for raw in parameters:
        try:
            item = (
                raw
                if isinstance(raw, MetricParameter)
                else MetricParameter(
                    metric_type=str(raw["metric_type"]),
                    mode=str(raw["mode"]),
                    value=Decimal(str(raw["value"])),
                )
            )
        except (KeyError, TypeError, ArithmeticError) as exc:  # pragma: no cover - defensivo
            raise SimulationError("Parámetro de escenario inválido.") from exc
        if item.metric_type not in {metric.value for metric in SIMULABLE_METRICS}:
            raise SimulationError(
                f"La métrica '{item.metric_type}' no es simulable. "
                f"Simulables: {', '.join(metric.value for metric in SIMULABLE_METRICS)}."
            )
        if item.mode not in {mode.value for mode in ParameterMode}:
            raise SimulationError(f"Modo de parámetro no soportado: '{item.mode}'.")
        if item.mode == ParameterMode.TARGET_VALUE.value and item.value <= 0:
            raise SimulationError("El valor objetivo debe ser mayor que cero.")
        items.append(MetricParameter(item.metric_type, item.mode, item.value))

    if not (MIN_METRICS <= len(items) <= MAX_METRICS):
        raise SimulationError(
            f"Un escenario debe modificar entre {MIN_METRICS} y {MAX_METRICS} métricas."
        )
    seen: set[str] = set()
    for item in items:
        if item.metric_type in seen:
            raise SimulationError(f"La métrica '{item.metric_type}' está repetida.")
        seen.add(item.metric_type)
    if all(item.value == 0 for item in items):
        raise SimulationError("Un escenario con todos los cambios en cero no aporta información.")
    return tuple(sorted(items, key=lambda item: item.metric_type))


# --- motor -------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MetricResult:
    metric_type: str
    unit: str
    mode: str
    input_value: Decimal
    baseline: Decimal
    simulated: Decimal
    delta_absolute: Decimal
    delta_percent: Decimal | None
    clamped: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "baseline": str(self.baseline),
            "simulated": str(self.simulated),
            "unit": self.unit,
            "delta_absolute": str(self.delta_absolute),
            "delta_percent": None if self.delta_percent is None else str(self.delta_percent),
            "mode": self.mode,
            "input": str(self.input_value),
            "clamped": self.clamped,
        }


@dataclass(frozen=True, slots=True)
class ScenarioResult:
    baseline_hash: str
    metrics: tuple[MetricResult, ...]
    derived: dict[str, dict[str, str]]
    unchanged: tuple[str, ...]
    warnings: tuple[str, ...]
    engine_name: str = ENGINE_NAME
    engine_version: str = ENGINE_VERSION
    data_kind: str = DataKind.SIMULATION.value

    def as_dict(self) -> dict[str, Any]:
        return {
            "engine": {"name": self.engine_name, "version": self.engine_version},
            "data_kind": self.data_kind,
            "baseline_hash": self.baseline_hash,
            "metrics": {result.metric_type: result.as_dict() for result in self.metrics},
            "derived": self.derived,
            "unchanged": list(self.unchanged),
            "warnings": list(self.warnings),
        }

    def checksum(self) -> str:
        return canonical_hash(self.as_dict())


def _simulated_value(
    parameter: MetricParameter,
    base: Decimal,
    limits: EngineLimits,
    contract: tuple[Decimal, Decimal],
) -> tuple[Decimal, bool]:
    """Aplica el parámetro y acota al rango técnico del catálogo."""
    min_value, max_value = contract
    max_delta = quantize(base * limits.max_delta_percent * _PERCENT)

    if parameter.mode == ParameterMode.DELTA_ABSOLUTE.value:
        if abs(parameter.value) > max_delta:
            raise SimulationError(
                f"El cambio de {parameter.metric_type} supera el límite de "
                f"{limits.max_delta_percent}% (±{max_delta})."
            )
        raw = base + parameter.value
    elif parameter.mode == ParameterMode.DELTA_PERCENT.value:
        if abs(parameter.value) > limits.max_delta_percent:
            raise SimulationError(
                f"El cambio porcentual de {parameter.metric_type} supera "
                f"±{limits.max_delta_percent}%."
            )
        raw = base + quantize(base * parameter.value * _PERCENT)
    else:
        raw = parameter.value

    simulated = quantize(raw)
    if simulated <= 0:
        raise SimulationError(
            f"El escenario deja '{parameter.metric_type}' en un valor no positivo."
        )
    clamped = simulated < min_value or simulated > max_value
    if clamped:
        simulated = min(max(simulated, min_value), max_value)
    return simulated, clamped


def apply_scenario(
    baseline: Baseline,
    parameters: Sequence[MetricParameter],
    *,
    limits: EngineLimits | None = None,
) -> ScenarioResult:
    """Calcula el escenario. Puro, determinista y sin efectos secundarios."""
    limits = limits or EngineLimits()
    normalized = parse_parameters(parameters)
    by_metric = baseline.by_metric()

    missing = [item.metric_type for item in normalized if item.metric_type not in by_metric]
    if missing:
        raise SimulationError(
            "No hay medición vigente para: "
            + ", ".join(missing)
            + ". Registra una medición o excluye esas métricas del escenario."
        )

    results: list[MetricResult] = []
    for item in normalized:
        point = by_metric[item.metric_type]
        bounds = limits.contract.get(item.metric_type)
        if bounds is None:
            raise SimulationError(
                f"Falta el rango del catálogo para la métrica '{item.metric_type}'."
            )
        simulated, clamped = _simulated_value(item, point.value, limits, bounds)
        delta = quantize(simulated - point.value)
        percent = None if point.value == 0 else quantize(delta * 100 / point.value)
        results.append(
            MetricResult(
                metric_type=item.metric_type,
                unit=point.unit,
                mode=item.mode,
                input_value=quantize(item.value),
                baseline=quantize(point.value),
                simulated=simulated,
                delta_absolute=delta,
                delta_percent=percent,
                clamped=clamped,
            )
        )

    base_values = {metric: point.value for metric, point in by_metric.items()}
    # Las métricas no incluidas en el escenario conservan su valor de base: los
    # indicadores derivados comparan el escenario contra la misma fotografía.
    simulated_values = {**base_values}
    simulated_values.update({result.metric_type: result.simulated for result in results})
    derived = _derived_indicators(base_values, simulated_values)
    unchanged = tuple(
        metric
        for metric in sorted(base_values)
        if metric not in {result.metric_type for result in results}
    )

    return ScenarioResult(
        baseline_hash=baseline.hash,
        metrics=tuple(results),
        derived=derived,
        unchanged=unchanged,
        warnings=SCENARIO_WARNINGS,
    )


def _derived_indicators(
    base_values: Mapping[str, Decimal], simulated_values: Mapping[str, Decimal]
) -> dict[str, dict[str, str]]:
    """Indicadores **aritméticos** del escenario. Sin valores de referencia ni semáforos."""

    def ratio(
        numerator: str, denominator: str, values: Mapping[str, Decimal]
    ) -> Decimal | None:
        top = values.get(numerator)
        bottom = values.get(denominator)
        if top is None or bottom in (None, 0):
            return None
        return quantize(top / bottom)

    derived: dict[str, dict[str, str]] = {}
    for key, (numerator, denominator) in {
        "waist_height": (MeasurementType.WAIST.value, MeasurementType.HEIGHT.value),
        "waist_hip": (MeasurementType.WAIST.value, MeasurementType.HIP.value),
    }.items():
        if numerator not in base_values:
            continue
        base_ratio = ratio(numerator, denominator, base_values)
        simulated_ratio = ratio(numerator, denominator, simulated_values)
        if base_ratio is None and simulated_ratio is None:
            continue
        derived[key] = {
            "baseline": None if base_ratio is None else str(base_ratio),
            "simulated": None if simulated_ratio is None else str(simulated_ratio),
            "delta_absolute": (
                None
                if base_ratio is None or simulated_ratio is None
                else str(quantize(simulated_ratio - base_ratio))
            ),
            "components": f"{numerator}/{denominator}",
        }
    return derived


# --- metadatos de presentación ----------------------------------------------


SIMULATION_LABEL = "ESCENARIO HIPOTÉTICO"
SIMULATION_BANNER = (
    "ESCENARIO HIPOTÉTICO: no describe el cuerpo real, no es una predicción y no "
    "modifica tus mediciones observadas."
)

_PARAMETER_MODE_LABELS = {
    ParameterMode.DELTA_ABSOLUTE: "Cambio absoluto",
    ParameterMode.DELTA_PERCENT: "Cambio porcentual",
    ParameterMode.TARGET_VALUE: "Valor objetivo",
}


def mode_label(mode: str) -> str:
    return _PARAMETER_MODE_LABELS.get(ParameterMode(mode), mode)


def unit_for(metric_type: str) -> str:
    return MeasurementUnit.KG.value if metric_type == MeasurementType.WEIGHT.value else "cm"
