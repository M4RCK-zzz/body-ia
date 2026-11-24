from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.measurements import MeasurementType
from app.models.measurement import Measurement
from app.repositories.analytics_repository import AnalyticsRepository


class _Superseded:
    """Subconsulta: ids de mediciones reemplazadas por una corrección."""

    def __init__(self) -> None:
        self.stmt = select(Measurement.supersedes_id).where(
            Measurement.supersedes_id.isnot(None)
        )


def _not_superseded(statement):
    return statement.where(Measurement.id.not_in(_Superseded().stmt))


class SqlAlchemyAnalyticsRepository(AnalyticsRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def current_measurements(
        self,
        *,
        profile_id: UUID,
        metric_type: MeasurementType,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> list[Measurement]:
        conditions = [
            Measurement.profile_id == profile_id,
            Measurement.metric_type == metric_type.value,
        ]
        if date_from is not None:
            conditions.append(Measurement.measured_at >= date_from)
        if date_to is not None:
            conditions.append(Measurement.measured_at <= date_to)
        stmt = _not_superseded(select(Measurement).where(*conditions)).order_by(
            Measurement.measured_at.asc(), Measurement.recorded_at.asc()
        )
        return list(self._session.execute(stmt).scalars().all())

    def corrected_count(
        self,
        *,
        profile_id: UUID,
        metric_type: MeasurementType,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> int:
        conditions = [
            Measurement.profile_id == profile_id,
            Measurement.metric_type == metric_type.value,
            Measurement.supersedes_id.isnot(None),
        ]
        if date_from is not None:
            conditions.append(Measurement.measured_at >= date_from)
        if date_to is not None:
            conditions.append(Measurement.measured_at <= date_to)
        stmt = _not_superseded(select(func.count()).select_from(Measurement).where(*conditions))
        return int(self._session.scalar(stmt) or 0)

    def measurement_count(self, profile_id: UUID) -> int:
        stmt = _not_superseded(
            select(func.count()).select_from(Measurement).where(
                Measurement.profile_id == profile_id
            )
        )
        return int(self._session.scalar(stmt) or 0)

    def latest_measurement_at(self, profile_id: UUID) -> datetime | None:
        stmt = _not_superseded(
            select(func.max(Measurement.measured_at)).where(
                Measurement.profile_id == profile_id
            )
        )
        return self._session.scalar(stmt)

    def measurement_count_by_profile(self, profile_ids: Iterable[UUID]) -> dict[UUID, int]:
        ids = list(profile_ids)
        if not ids:
            return {}
        stmt = _not_superseded(
            select(Measurement.profile_id, func.count())
            .where(Measurement.profile_id.in_(ids))
            .group_by(Measurement.profile_id)
        )
        return {profile_id: int(total) for profile_id, total in self._session.execute(stmt).all()}

    def latest_measurement_by_profile(
        self, profile_ids: Iterable[UUID]
    ) -> dict[UUID, datetime]:
        ids = list(profile_ids)
        if not ids:
            return {}
        stmt = _not_superseded(
            select(Measurement.profile_id, func.max(Measurement.measured_at))
            .where(Measurement.profile_id.in_(ids))
            .group_by(Measurement.profile_id)
        )
        return {
            profile_id: latest
            for profile_id, latest in self._session.execute(stmt).all()
            if latest is not None
        }
