from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_dashboard_service
from app.api.security import CurrentUser
from app.schemas.report import DashboardProfileRead, DashboardSummaryRead
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary", response_model=DashboardSummaryRead)
def get_dashboard_summary(
    user: CurrentUser,
    service: DashboardService = Depends(get_dashboard_service),  # noqa: B008
) -> DashboardSummaryRead:
    """KPIs reales del usuario: solo expedientes con acceso vigente."""
    summary = service.summary(user)
    return DashboardSummaryRead(
        computed_at=summary.computed_at,
        profiles_total=summary.profiles_total,
        profiles_active=summary.profiles_active,
        measurements_total=summary.measurements_total,
        profiles_without_measurements=summary.profiles_without_measurements,
        pose_analyses_total=summary.pose_analyses_total,
        pose_by_status=summary.pose_by_status,
        recent_profiles=[
            DashboardProfileRead(
                profile_id=profile.profile_id,
                display_code=profile.display_code,
                status=profile.status,
                my_access=profile.my_access,
                measurement_count=profile.measurement_count,
                last_measurement_at=profile.last_measurement_at,
            )
            for profile in summary.recent_profiles
        ],
    )
