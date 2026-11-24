from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.simulation import ACTIVE_SIMULATION_STATUSES, SimulationStatus
from app.models.access import ProfileAccess
from app.models.simulation import Simulation, SimulationBaseline
from app.repositories.simulation_repository import SimulationRepository

logger = logging.getLogger(__name__)

_QUEUEABLE = SimulationStatus.QUEUED.value
_ACTIVE = tuple(sorted(ACTIVE_SIMULATION_STATUSES))


class SqlAlchemySimulationRepository(SimulationRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, simulation_id: UUID) -> Simulation | None:
        return self._session.get(Simulation, simulation_id)

    def add(self, simulation: Simulation) -> Simulation:
        self._session.add(simulation)
        return self.save(simulation)

    def save(self, simulation: Simulation) -> Simulation:
        self._session.flush()
        return simulation

    def add_baseline(self, row: SimulationBaseline) -> SimulationBaseline:
        self._session.add(row)
        self._session.flush()
        return row

    def baselines_for(self, simulation_id: UUID) -> list[SimulationBaseline]:
        stmt = (
            select(SimulationBaseline)
            .where(SimulationBaseline.simulation_id == simulation_id)
            .order_by(SimulationBaseline.metric_type)
        )
        return list(self._session.scalars(stmt).all())

    def _access_filter(self, user_id: UUID):
        # El acceso al expediente debe seguir vigente (revocado = oculto),
        # mismo criterio que reportes y expedientes.
        return (
            select(ProfileAccess.id)
            .where(
                ProfileAccess.profile_id == Simulation.profile_id,
                ProfileAccess.user_id == user_id,
                ProfileAccess.revoked_at.is_(None),
            )
            .exists()
        )

    def list_page(
        self,
        *,
        profile_id: UUID,
        status: str | None,
        include_archived: bool,
        limit: int,
        offset: int,
    ) -> tuple[list[Simulation], int]:
        conditions = [Simulation.profile_id == profile_id]
        if status is not None:
            conditions.append(Simulation.status == status)
        elif not include_archived:
            conditions.append(Simulation.status != SimulationStatus.ARCHIVED.value)
        base = select(Simulation).where(*conditions).order_by(
            Simulation.created_at.desc(), Simulation.id
        )
        total = self._session.scalar(select(func.count()).select_from(base.subquery())) or 0
        rows = self._session.execute(base.limit(limit).offset(offset)).scalars().all()
        return list(rows), total

    def list_page_for_user(
        self,
        *,
        created_by_user_id: UUID,
        status: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Simulation], int]:
        conditions = [
            Simulation.created_by_user_id == created_by_user_id,
            self._access_filter(created_by_user_id),
        ]
        if status is not None:
            conditions.append(Simulation.status == status)
        base = select(Simulation).where(*conditions).order_by(
            Simulation.created_at.desc(), Simulation.id
        )
        total = self._session.scalar(select(func.count()).select_from(base.subquery())) or 0
        rows = self._session.execute(base.limit(limit).offset(offset)).scalars().all()
        return list(rows), total

    def count_active_for_profile(self, profile_id: UUID) -> int:
        stmt = select(func.count()).select_from(Simulation).where(
            Simulation.profile_id == profile_id, Simulation.status.in_(_ACTIVE)
        )
        return int(self._session.scalar(stmt) or 0)

    def claim_next(self) -> Simulation | None:
        stmt = (
            select(Simulation)
            .where(Simulation.status == _QUEUEABLE)
            .order_by(Simulation.queued_at.asc(), Simulation.id.asc())
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        return self._session.execute(stmt).scalars().first()

    def mark_stale_failed(self, stale_before: datetime, *, now: datetime, reason: str) -> int:
        rows: Iterable[Simulation] = self._session.scalars(
            select(Simulation).where(
                Simulation.status == _QUEUEABLE, Simulation.queued_at <= stale_before
            )
        ).all()
        count = 0
        for row in rows:
            row.status = SimulationStatus.FAILED.value
            row.error_message = reason[:300]
            row.completed_at = now
            if row.queued_at is not None:
                delta = now - row.queued_at
                row.duration_ms = max(
                    delta.days * 86_400_000 + delta.seconds * 1000 + delta.microseconds // 1000,
                    0,
                )
            count += 1
        return count

    def expired_for_retention(self, cutoff: datetime) -> list[Simulation]:
        rows = self._session.scalars(
            select(Simulation).where(
                Simulation.status == SimulationStatus.ARCHIVED.value,
                Simulation.archived_at.isnot(None),
                Simulation.archived_at < cutoff,
                Simulation.result_json.isnot(None),
            )
        ).all()
        return list(rows)
