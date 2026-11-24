from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from app.core.clock import utcnow
from app.domain.enums import DataKind
from app.domain.identity import AuditAction
from app.domain.pose import PoseAnalysisStatus
from app.domain.profiles import ProfileStatus
from app.models.identity import User
from app.repositories.analytics_repository import AnalyticsRepository
from app.repositories.pose_repository import PoseRepository
from app.repositories.profile_repository import ProfileRepository
from app.services.audit_service import AuditRecorder
from app.services.ports import Transaction

RECENT_PROFILES_LIMIT = 5


@dataclass(frozen=True, slots=True)
class DashboardProfile:
    profile_id: UUID
    display_code: str
    status: str
    my_access: str
    measurement_count: int
    last_measurement_at: datetime | None


@dataclass(frozen=True, slots=True)
class DashboardSummary:
    computed_at: datetime
    profiles_total: int
    profiles_active: int
    measurements_total: int
    profiles_without_measurements: int
    pose_analyses_total: int
    pose_by_status: dict[str, int] = field(default_factory=dict)
    recent_profiles: tuple[DashboardProfile, ...] = ()
    data_kind: str = DataKind.OBSERVED.value


class DashboardService:
    """KPIs del panel con **datos reales** (Fase 7).

    Solo agrega expedientes donde el usuario tiene acceso vigente: no existe una
    vista global del sistema para roles no administrativos. Las mediciones
    (observadas) y las estimaciones de pose se cuentan por separado y nunca se
    suman entre sí.
    """

    def __init__(
        self,
        profiles: ProfileRepository,
        analytics: AnalyticsRepository,
        pose: PoseRepository,
        audit: AuditRecorder,
        tx: Transaction,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        self._profiles = profiles
        self._analytics = analytics
        self._pose = pose
        self._audit = audit
        self._tx = tx
        self._clock = clock

    def summary(
        self,
        actor: User,
        *,
        profile_limit: int = 200,
        record_audit: bool = True,
    ) -> DashboardSummary:
        rows, total = self._profiles.list_accessible(
            user_id=actor.id, status=None, limit=profile_limit, offset=0
        )
        profile_ids = [profile.id for profile, _level in rows]
        active = sum(1 for profile, _level in rows if profile.status == ProfileStatus.ACTIVE.value)

        counts = self._analytics.measurement_count_by_profile(profile_ids)
        latest = self._analytics.latest_measurement_by_profile(profile_ids)

        measurements_total = sum(counts.values())
        without_measurements = sum(1 for pid in profile_ids if counts.get(pid, 0) == 0)

        counts_pose = self._pose.count_by_profile_status(profile_ids)
        # Solo estados con contenido: un 0 se representa como ausencia de clave,
        # no como un valor que pueda leerse como "análisis con resultado 0".
        pose_by_status = {
            status.value: counts_pose[status.value]
            for status in PoseAnalysisStatus
            if counts_pose.get(status.value)
        }
        pose_total = sum(pose_by_status.values())

        recent = tuple(
            DashboardProfile(
                profile_id=profile.id,
                display_code=profile.display_code,
                status=profile.status,
                my_access=str(level),
                measurement_count=counts.get(profile.id, 0),
                last_measurement_at=latest.get(profile.id),
            )
            for profile, level in rows[:RECENT_PROFILES_LIMIT]
        )

        summary = DashboardSummary(
            computed_at=self._clock(),
            profiles_total=total,
            profiles_active=active,
            measurements_total=measurements_total,
            profiles_without_measurements=without_measurements,
            pose_analyses_total=pose_total,
            pose_by_status=pose_by_status,
            recent_profiles=recent,
        )

        if record_audit:
            self._audit.record(
                AuditAction.DASHBOARD_VIEWED,
                actor_id=actor.id,
                resource_type="dashboard",
                resource_id=str(actor.id),
                detail={
                    "profiles": total,
                    "measurements": measurements_total,
                    "pose_analyses": pose_total,
                },
            )
            self._tx.commit()
        return summary
