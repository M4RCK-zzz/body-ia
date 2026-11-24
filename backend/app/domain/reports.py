"""Dominio de analítica descriptiva y reportes (Fase 7).

Solo estadística descriptiva: último valor, delta absoluto/porcentual, conteo,
corregidos y atípicos. **Nunca** se interpola, se estima ni se proyecta un valor
faltante, y nunca se emite un 0 cuando no hay datos.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

# Ventanas admitidas para el resumen (días).
ALLOWED_WINDOWS: tuple[int, ...] = (7, 30, 90)
DEFAULT_WINDOW_DAYS = 30

# Regla de atípico: |valor - mediana| > k * MAD (desviación absoluta mediana).
# k=3.5 es el umbral clásico de Iglewicz-Hoaglin para muestras pequeñas.
OUTLIER_MAD_K = 3.5
# MAD = 0 (valores repetidos) desactiva la detección: no hay dispersión que medir.
MIN_POINTS_FOR_OUTLIERS = 3


class ReportKind(StrEnum):
    """Tipo de reporte. Cada uno tiene su propia separación por DataKind."""

    MEASUREMENTS_CSV = "measurements_csv"
    MEASUREMENTS_PDF = "measurements_pdf"
    POSE_CSV = "pose_csv"
    POSE_PDF = "pose_pdf"


REPORT_FORMAT: dict[ReportKind, str] = {
    ReportKind.MEASUREMENTS_CSV: "csv",
    ReportKind.MEASUREMENTS_PDF: "pdf",
    ReportKind.POSE_CSV: "csv",
    ReportKind.POSE_PDF: "pdf",
}

REPORT_DATA_KIND: dict[ReportKind, str] = {
    ReportKind.MEASUREMENTS_CSV: "observed",
    ReportKind.MEASUREMENTS_PDF: "observed",
    ReportKind.POSE_CSV: "visual_estimate",
    ReportKind.POSE_PDF: "visual_estimate",
}

REPORT_LABEL: dict[ReportKind, str] = {
    ReportKind.MEASUREMENTS_CSV: "Mediciones observadas (CSV)",
    ReportKind.MEASUREMENTS_PDF: "Mediciones observadas (PDF)",
    ReportKind.POSE_CSV: "Estimaciones de pose (CSV)",
    ReportKind.POSE_PDF: "Estimaciones de pose (PDF)",
}

CONTENT_TYPES: dict[str, str] = {
    "csv": "text/csv; charset=utf-8",
    "pdf": "application/pdf",
}

DISCLAIMER = (
    "Documento generado por BODYVISION AI con fines de registro y visualización. "
    "No es un informe clínico ni emite diagnósticos. Las mediciones son observadas; "
    "las estimaciones de pose son inferencias visuales de IA y no equivalen a mediciones."
)


class ReportStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    GENERATED = "generated"
    FAILED = "failed"


TERMINAL_REPORT_STATUSES: frozenset[str] = frozenset(
    {ReportStatus.GENERATED.value, ReportStatus.FAILED.value}
)


def is_measurement_report(kind: str) -> bool:
    return kind in (ReportKind.MEASUREMENTS_CSV.value, ReportKind.MEASUREMENTS_PDF.value)


def is_pose_report(kind: str) -> bool:
    return kind in (ReportKind.POSE_CSV.value, ReportKind.POSE_PDF.value)


@dataclass(frozen=True, slots=True)
class SeriesObservation:
    """Punto já filtrado (solo mediciones vigentes) para el cálculo descriptivo."""

    measured_at: datetime
    value: Decimal


@dataclass(frozen=True, slots=True)
class MetricTrend:
    """Resumen descriptivo de una métrica. Todos los campos son observados."""

    metric_type: str
    label: str
    unit: str
    count: int
    corrected_count: int
    first_at: datetime | None = None
    last_at: datetime | None = None
    last_value: Decimal | None = None
    previous_value: Decimal | None = None
    delta_absolute: Decimal | None = None
    delta_percent: Decimal | None = None
    # Descriptivos de la ventana (útiles para leer dispersión sin inferir nada).
    min_value: Decimal | None = None
    max_value: Decimal | None = None
    mean_value: Decimal | None = None
    median_value: Decimal | None = None
    outlier_count: int = 0
    outlier_timestamps: tuple[datetime, ...] = field(default_factory=tuple)

    @property
    def has_data(self) -> bool:
        return self.count > 0


_CENT = Decimal("0.01")


def quantize(value: Decimal | None) -> Decimal | None:
    """Redondea a 2 decimales (el valor almacenado es Numeric(7,2)).

    Evita arrastrar el ruido binario de `Decimal(float)` a los reportes.
    """
    if value is None:
        return None
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)


def _median(values: list[Decimal]) -> Decimal | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return quantize(ordered[middle])
    return quantize((ordered[middle - 1] + ordered[middle]) / Decimal(2))


def detect_outliers(values: list[Decimal]) -> set[int]:
    """Índices atípicos por mediana ± k·MAD. Sin dispersión (MAD=0) no marca nada.

    Deliberadamente conservador: con menos de 3 puntos no se marca ningún atípico.
    """
    if len(values) < MIN_POINTS_FOR_OUTLIERS:
        return set()
    median = _median(values)
    if median is None:
        return set()
    deviations = sorted(abs(value - median) for value in values)
    mad = _median(deviations)
    if mad is None or mad == 0:
        return set()
    limit = Decimal(str(OUTLIER_MAD_K)) * mad
    return {index for index, value in enumerate(values) if abs(value - median) > limit}


def summarize_series(
    *,
    metric_type: str,
    label: str,
    unit: str,
    observations: list[SeriesObservation],
    corrected_count: int = 0,
) -> MetricTrend:
    """Calcula el resumen descriptivo de una serie ya ordenada ascendentemente.

    Reglas duras:
    - Sin observaciones: count=0 y todos los valores None (nunca 0).
    - delta_absolute requiere al menos 2 puntos; delta_percent requiere previo != 0.
    - No se rellena ningún hueco: eso lo comunica `count` y las fechas.
    """
    if not observations:
        return MetricTrend(
            metric_type=metric_type,
            label=label,
            unit=unit,
            count=0,
            corrected_count=corrected_count,
        )

    ordered = sorted(observations, key=lambda item: item.measured_at)
    values = [quantize(item.value) or item.value for item in ordered]
    last = ordered[-1]
    previous = ordered[-2] if len(ordered) > 1 else None

    delta_absolute: Decimal | None = None
    delta_percent: Decimal | None = None
    if previous is not None:
        delta_absolute = quantize(last.value - previous.value)
        if previous.value != 0:
            delta_percent = quantize((delta_absolute / previous.value) * Decimal(100))

    mean = quantize(sum(values) / Decimal(len(values)))
    outlier_indexes = detect_outliers(values)

    return MetricTrend(
        metric_type=metric_type,
        label=label,
        unit=unit,
        count=len(ordered),
        corrected_count=corrected_count,
        first_at=ordered[0].measured_at,
        last_at=last.measured_at,
        last_value=quantize(last.value),
        previous_value=quantize(previous.value) if previous is not None else None,
        delta_absolute=delta_absolute,
        delta_percent=delta_percent,
        min_value=quantize(min(values)),
        max_value=quantize(max(values)),
        mean_value=mean,
        median_value=_median(values),
        outlier_count=len(outlier_indexes),
        outlier_timestamps=tuple(ordered[i].measured_at for i in sorted(outlier_indexes)),
    )
