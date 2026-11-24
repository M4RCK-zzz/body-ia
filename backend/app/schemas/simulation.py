from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, field_validator, model_validator

from app.domain.simulation import (
    MAX_METRICS,
    MIN_METRICS,
    ParameterMode,
    SimulationStatus,
)

OutputValue = Annotated[Decimal, PlainSerializer(float, return_type=float, when_used="json")]


class MetricParameterIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric_type: str = Field(min_length=1, max_length=32)
    mode: ParameterMode
    value: Decimal = Field(ge=-1000, le=1000)


class SimulationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=80)
    notes: str | None = Field(default=None, max_length=500)
    run_now: bool = True
    metrics: list[MetricParameterIn] = Field(min_length=MIN_METRICS, max_length=MAX_METRICS)

    @field_validator("label")
    @classmethod
    def _strip_label(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("El nombre del escenario no puede estar vacío.")
        return cleaned

    @model_validator(mode="after")
    def _unique_metrics(self) -> SimulationCreateRequest:
        metric_types = [metric.metric_type for metric in self.metrics]
        if len(set(metric_types)) != len(metric_types):
            raise ValueError("Cada métrica puede aparecer una sola vez en el escenario.")
        if all(metric.value == 0 for metric in self.metrics):
            raise ValueError("Un escenario con todos los cambios en cero no aporta información.")
        return self


class SimulationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    profile_id: UUID
    label: str
    status: SimulationStatus
    data_kind: Literal["simulation"]
    engine_name: str
    engine_version: str
    parameters_json: dict[str, Any]
    baseline_hash: str
    result_json: dict[str, Any] | None = None
    result_checksum: str | None = None
    notes: str | None = None
    error_message: str | None = None
    created_by: str = ""
    created_at: datetime
    queued_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    archived_at: datetime | None = None
    duration_ms: int | None = None
    disclaimer: str = ""

    @model_validator(mode="before")
    @classmethod
    def _map_model(cls, value: Any) -> Any:
        # `created_by` se expone desde el snapshot congelado del modelo ORM.
        if hasattr(value, "created_by_snapshot"):
            return {
                **{
                    field: getattr(value, field)
                    for field in cls.model_fields
                    if field not in {"created_by", "disclaimer"} and hasattr(value, field)
                },
                "created_by": value.created_by_snapshot,
                "disclaimer": _disclaimer(),
            }
        return value

    @model_validator(mode="after")
    def _guard_kind(self) -> SimulationRead:
        # Defensa en profundidad: la API nunca devuelve un escenario como observado.
        if self.data_kind != "simulation":  # pragma: no cover - garantizado por el modelo
            raise ValueError("Un escenario debe declararse siempre como 'simulation'.")
        return self


def _disclaimer() -> str:
    from app.domain.simulation import SIMULATION_DISCLAIMER

    return SIMULATION_DISCLAIMER


class BaselineMetricRead(BaseModel):
    metric_type: str
    measurement_id: UUID
    value: float
    unit: str
    measured_at: datetime
    superseded_since: bool = False


class ScenarioMetricRead(BaseModel):
    metric_type: str
    value: float
    unit: str
    delta_absolute: float
    delta_percent: float | None = None
    clamped: bool = False


class SimulationComparisonRead(BaseModel):
    simulation_id: UUID
    profile_id: UUID
    label: str
    status: SimulationStatus
    data_kind: Literal["simulation"]
    engine: dict[str, str]
    baseline_hash: str
    created_at: datetime
    created_by: str
    result_checksum: str | None = None
    baseline: dict[str, Any]
    scenario: dict[str, Any]
    derived: dict[str, Any] = Field(default_factory=dict)
    unchanged: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    disclaimer: str
    banner: str


class SimulationLimitsRead(BaseModel):
    engine: dict[str, str]
    modes: list[str]
    max_delta_percent: float
    metrics: list[dict[str, Any]]
    height_as_reference_only: bool
    derived: list[str]
    disclaimer: str
