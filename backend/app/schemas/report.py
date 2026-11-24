from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, PlainSerializer, model_validator

from app.domain.enums import DataKind
from app.domain.measurements import MeasurementType
from app.domain.reports import (
    ALLOWED_WINDOWS,
    DEFAULT_WINDOW_DAYS,
    MetricTrend,
    ReportKind,
    ReportStatus,
)

OutputValue = Annotated[Decimal, PlainSerializer(float, return_type=float, when_used="json")]


# --- Analítica ---------------------------------------------------------------


class MetricTrendRead(BaseModel):
    metric_type: MeasurementType
    label: str
    unit: str
    count: int
    corrected_count: int
    first_at: datetime | None = None
    last_at: datetime | None = None
    last_value: OutputValue | None = None
    previous_value: OutputValue | None = None
    delta_absolute: OutputValue | None = None
    delta_percent: OutputValue | None = None
    min_value: OutputValue | None = None
    max_value: OutputValue | None = None
    mean_value: OutputValue | None = None
    median_value: OutputValue | None = None
    outlier_count: int = 0
    outlier_timestamps: list[datetime] = Field(default_factory=list)

    @classmethod
    def from_trend(cls, trend: MetricTrend) -> MetricTrendRead:
        return cls(
            metric_type=MeasurementType(trend.metric_type),
            label=trend.label,
            unit=trend.unit,
            count=trend.count,
            corrected_count=trend.corrected_count,
            first_at=trend.first_at,
            last_at=trend.last_at,
            last_value=trend.last_value,
            previous_value=trend.previous_value,
            delta_absolute=trend.delta_absolute,
            delta_percent=trend.delta_percent,
            min_value=trend.min_value,
            max_value=trend.max_value,
            mean_value=trend.mean_value,
            median_value=trend.median_value,
            outlier_count=trend.outlier_count,
            outlier_timestamps=list(trend.outlier_timestamps),
        )


class AnalyticsSummaryRead(BaseModel):
    profile_id: UUID
    window_days: int
    date_from: datetime
    date_to: datetime
    data_kind: DataKind = DataKind.OBSERVED
    computed_at: datetime
    total_measurements: int
    metrics_without_data: list[str] = Field(default_factory=list)
    trends: list[MetricTrendRead] = Field(default_factory=list)
    disclaimer: str = (
        "Estadística descriptiva sobre mediciones observadas: no hay proyecciones "
        "ni interpretación clínica. Las métricas sin datos se listan explícitamente, "
        "no se rellenan ni se interpolan."
    )


class DashboardProfileRead(BaseModel):
    profile_id: UUID
    display_code: str
    status: str
    my_access: str
    measurement_count: int
    last_measurement_at: datetime | None = None


class DashboardSummaryRead(BaseModel):
    data_kind: DataKind = DataKind.OBSERVED
    computed_at: datetime
    profiles_total: int
    profiles_active: int
    measurements_total: int
    profiles_without_measurements: int
    pose_analyses_total: int
    pose_by_status: dict[str, int] = Field(default_factory=dict)
    recent_profiles: list[DashboardProfileRead] = Field(default_factory=list)
    note: str = (
        "Solo se agregan expedientes con acceso vigente del usuario. "
        "Los análisis de pose son estimaciones visuales y se cuentan aparte: "
        "nunca se suman a las mediciones observadas."
    )


# --- Reportes ----------------------------------------------------------------


class ReportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: ReportKind
    date_from: AwareDatetime | None = None
    date_to: AwareDatetime | None = None
    metrics: list[MeasurementType] | None = Field(default=None, max_length=7)

    @model_validator(mode="after")
    def _validate(self) -> ReportRequest:
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("El rango de fechas es inválido: el inicio es posterior al fin.")
        if self.metrics is not None and self.kind not in (
            ReportKind.MEASUREMENTS_CSV,
            ReportKind.MEASUREMENTS_PDF,
        ):
            raise ValueError(
                "Las métricas solo aplican a reportes de mediciones; los reportes de pose "
                "no se mezclan con mediciones."
            )
        return self


class ReportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    profile_id: UUID
    kind: ReportKind
    format: str
    data_kind: DataKind
    status: ReportStatus
    date_from: datetime | None = None
    date_to: datetime | None = None
    metrics_json: list[str] | None = None
    summary_json: dict | None = None
    checksum_sha256: str | None = None
    size_bytes: int | None = None
    error_message: str | None = None
    requested_by_snapshot: str
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = None
    requested_by: str | None = None
    download_url: str | None = None


class AnalyticsWindowMeta(BaseModel):
    allowed_windows: list[int] = Field(default_factory=lambda: list(ALLOWED_WINDOWS))
    default_window: int = DEFAULT_WINDOW_DAYS
