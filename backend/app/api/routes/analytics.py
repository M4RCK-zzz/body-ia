from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_analytics_service
from app.api.security import CurrentUser
from app.domain.measurements import MeasurementType
from app.domain.reports import DEFAULT_WINDOW_DAYS
from app.schemas.report import AnalyticsSummaryRead, MetricTrendRead
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/profiles/{profile_id}/analytics", tags=["Analítica"])


@router.get("", response_model=AnalyticsSummaryRead)
def get_analytics_summary(
    profile_id: UUID,
    user: CurrentUser,
    window_days: int = Query(default=DEFAULT_WINDOW_DAYS, description="Ventana: 7, 30 o 90 días"),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    metric: list[MeasurementType] | None = Query(default=None),
    service: AnalyticsService = Depends(get_analytics_service),  # noqa: B008
) -> AnalyticsSummaryRead:
    """Resumen **descriptivo** del expediente. Nunca interpola ni proyecta."""
    summary = service.summary(
        user,
        profile_id,
        window_days=window_days,
        date_from=date_from,
        date_to=date_to,
        metric_types=metric,
    )
    return AnalyticsSummaryRead(
        profile_id=summary.profile_id,
        window_days=summary.window_days,
        date_from=summary.date_from,
        date_to=summary.date_to,
        computed_at=summary.computed_at,
        total_measurements=summary.total_measurements,
        metrics_without_data=list(summary.metrics_without_data),
        trends=[MetricTrendRead.from_trend(trend) for trend in summary.trends],
    )
