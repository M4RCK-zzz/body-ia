from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID

from app.core.clock import utcnow
from app.core.errors import BusinessRuleError
from app.domain.access import AccessLevel
from app.domain.enums import DataKind
from app.domain.identity import AuditAction
from app.domain.measurements import MeasurementType
from app.domain.metrics import MetricCatalog
from app.domain.reports import (
    ALLOWED_WINDOWS,
    DEFAULT_WINDOW_DAYS,
    MetricTrend,
    SeriesObservation,
    summarize_series,
)
from app.models.identity import User
from app.models.profile import Profile
from app.repositories.analytics_repository import AnalyticsRepository
from app.services.access_guard import AccessGuard
from app.services.audit_service import AuditRecorder
from app.services.ports import Transaction

MAX_SERIES_POINTS = 2000


@dataclass(frozen=True, slots=True)
class AnalyticsSummary:
    profile_id: UUID
    window_days: int
    date_from: datetime
    date_to: datetime
    data_kind: str
    computed_at: datetime
    trends: tuple[MetricTrend, ...]
    # Métricas del catálogo sin ninguna medición en la ventana. Se nombran de forma
    # explícita: un conteo 0 nunca se representa como "valor 0".
    metrics_without_data: tuple[str, ...]

    @property
    def total_measurements(self) -> int:
        return sum(trend.count for trend in self.trends)


class AnalyticsService:
    """Analítica **solo descriptiva** del expediente (Fase 7).

    No interpola, no proyecta y no estima: si no hay datos, el resultado es
    `count=0` con valores nulos, nunca un 0 numérico.
    """

    def __init__(
        self,
        guard: AccessGuard,
        analytics: AnalyticsRepository,
        catalog: MetricCatalog,
        audit: AuditRecorder,
        tx: Transaction,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        self._guard = guard
        self._analytics = analytics
        self._catalog = catalog
        self._audit = audit
        self._tx = tx
        self._clock = clock

    # --- internas ---

    def _window(
        self,
        window_days: int,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> tuple[datetime, datetime]:
        if window_days not in ALLOWED_WINDOWS:
            allowed = ", ".join(str(days) for days in ALLOWED_WINDOWS)
            raise BusinessRuleError(f"La ventana debe ser una de: {allowed} días.")
        end = date_to or self._clock()
        start = date_from or (end - timedelta(days=window_days))
        if start > end:
            raise BusinessRuleError(
                "El rango de fechas es inválido: el inicio es posterior al fin."
            )
        return start, end

    def _metric_types(self, metric_types: list[MeasurementType] | None) -> list[MeasurementType]:
        if metric_types is None:
            return [spec.metric_type for spec in self._catalog.all()]
        enabled = {spec.metric_type for spec in self._catalog.all()}
        for metric_type in metric_types:
            if metric_type not in enabled:
                raise BusinessRuleError(
                    f"La métrica '{metric_type.value}' no está habilitada."
                )
        # Preserva el orden del catálogo y elimina duplicados.
        return [
            spec.metric_type for spec in self._catalog.all() if spec.metric_type in metric_types
        ]

    # --- lecturas ---

    def summary(
        self,
        actor: User,
        profile_id: UUID,
        *,
        window_days: int = DEFAULT_WINDOW_DAYS,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        metric_types: list[MeasurementType] | None = None,
        record_audit: bool = True,
    ) -> AnalyticsSummary:
        profile, _ = self._guard.require(profile_id, actor, AccessLevel.VIEWER)
        start, end = self._window(window_days, date_from, date_to)
        selected = self._metric_types(metric_types)

        trends: list[MetricTrend] = []
        without_data: list[str] = []
        for metric_type in selected:
            spec = self._catalog.get(metric_type)
            if spec is None:  # pragma: no cover - ya validado arriba
                continue
            rows = self._analytics.current_measurements(
                profile_id=profile_id,
                metric_type=metric_type,
                date_from=start,
                date_to=end,
            )
            corrected = self._analytics.corrected_count(
                profile_id=profile_id,
                metric_type=metric_type,
                date_from=start,
                date_to=end,
            )
            observations = [
                SeriesObservation(measured_at=row.measured_at, value=Decimal(row.value))
                for row in rows
            ]
            trend = summarize_series(
                metric_type=metric_type.value,
                label=spec.label,
                unit=spec.unit.value,
                observations=observations,
                corrected_count=corrected,
            )
            trends.append(trend)
            if not trend.has_data:
                without_data.append(spec.label)

        summary = AnalyticsSummary(
            profile_id=profile_id,
            window_days=window_days,
            date_from=start,
            date_to=end,
            data_kind=DataKind.OBSERVED.value,
            computed_at=self._clock(),
            trends=tuple(trends),
            metrics_without_data=tuple(without_data),
        )
        if record_audit:
            self._audit.record(
                AuditAction.ANALYTICS_VIEWED,
                actor_id=actor.id,
                resource_type="profile",
                resource_id=str(profile.id),
                profile_id=profile.id,
                detail={
                    "window_days": window_days,
                    "date_from": start.isoformat(),
                    "date_to": end.isoformat(),
                    "metrics": [trend.metric_type for trend in trends if trend.has_data],
                },
            )
            self._tx.commit()
        return summary

    def profile_for(self, actor: User, profile_id: UUID) -> Profile:
        profile, _ = self._guard.require(profile_id, actor, AccessLevel.VIEWER)
        return profile

    def series_rows(
        self,
        actor: User,
        profile_id: UUID,
        *,
        date_from: datetime | None,
        date_to: datetime | None,
        metric_types: list[MeasurementType] | None,
    ) -> list[tuple[MetricTrend, list[SeriesObservation]]]:
        """Puntos vigentes por métrica para la generación de reportes (sin auditar)."""
        self._guard.require(profile_id, actor, AccessLevel.VIEWER)
        selected = self._metric_types(metric_types)
        rows: list[tuple[MetricTrend, list[SeriesObservation]]] = []
        for metric_type in selected:
            spec = self._catalog.get(metric_type)
            if spec is None:  # pragma: no cover
                continue
            measurements = self._analytics.current_measurements(
                profile_id=profile_id,
                metric_type=metric_type,
                date_from=date_from,
                date_to=date_to,
            )
            corrected = self._analytics.corrected_count(
                profile_id=profile_id,
                metric_type=metric_type,
                date_from=date_from,
                date_to=date_to,
            )
            observations = [
                SeriesObservation(measured_at=row.measured_at, value=Decimal(row.value))
                for row in measurements
            ]
            trend = summarize_series(
                metric_type=metric_type.value,
                label=spec.label,
                unit=spec.unit.value,
                observations=observations,
                corrected_count=corrected,
            )
            rows.append((trend, observations))
        return rows
