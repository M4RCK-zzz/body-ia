from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.pose import PoseAnalysisStatus
from app.models.pose import PoseAnalysis
from app.repositories.pose_repository import PoseRepository

logger = logging.getLogger(__name__)


class SqlAlchemyPoseRepository(PoseRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, analysis_id: UUID) -> PoseAnalysis | None:
        return self._session.get(PoseAnalysis, analysis_id)

    def add(self, analysis: PoseAnalysis) -> PoseAnalysis:
        self._session.add(analysis)
        return self.save(analysis)

    def save(self, analysis: PoseAnalysis) -> PoseAnalysis:
        self._session.flush()
        return analysis

    def find_active_for_asset(self, asset_id: UUID) -> PoseAnalysis | None:
        return self._session.scalar(
            select(PoseAnalysis)
            .where(
                PoseAnalysis.media_asset_id == asset_id,
                PoseAnalysis.status.in_(
                    [PoseAnalysisStatus.QUEUED.value, PoseAnalysisStatus.PROCESSING.value]
                ),
            )
            .order_by(PoseAnalysis.created_at.desc())
            .limit(1)
        )

    def list_page(
        self,
        *,
        profile_id: UUID,
        status: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[PoseAnalysis], int]:
        conditions = [PoseAnalysis.profile_id == profile_id]
        if status is not None:
            conditions.append(PoseAnalysis.status == status)
        base = select(PoseAnalysis).where(*conditions).order_by(
            PoseAnalysis.created_at.desc(), PoseAnalysis.id
        )
        total = self._session.scalar(select(func.count()).select_from(base.subquery())) or 0
        rows = self._session.execute(base.limit(limit).offset(offset)).scalars().all()
        return list(rows), total

    def list_page_by_asset(
        self,
        *,
        media_asset_id: UUID,
        status: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[PoseAnalysis], int]:
        conditions = [PoseAnalysis.media_asset_id == media_asset_id]
        if status is not None:
            conditions.append(PoseAnalysis.status == status)
        base = select(PoseAnalysis).where(*conditions).order_by(
            PoseAnalysis.created_at.desc(), PoseAnalysis.id
        )
        total = self._session.scalar(select(func.count()).select_from(base.subquery())) or 0
        rows = self._session.execute(base.limit(limit).offset(offset)).scalars().all()
        return list(rows), total

    def count_by_profile_status(self, profile_ids: Iterable[UUID]) -> dict[str, int]:
        ids = list(profile_ids)
        if not ids:
            return {}
        stmt = (
            select(PoseAnalysis.status, func.count())
            .where(PoseAnalysis.profile_id.in_(ids))
            .group_by(PoseAnalysis.status)
        )
        return {status: total for status, total in self._session.execute(stmt).all()}

    def claim_next(self) -> PoseAnalysis | None:
        stmt = (
            select(PoseAnalysis)
            .where(PoseAnalysis.status == PoseAnalysisStatus.QUEUED.value)
            .order_by(PoseAnalysis.created_at.asc(), PoseAnalysis.id.asc())
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        return self._session.execute(stmt).scalars().first()

    def mark_stale_failed(self, stale_before: datetime, *, now: datetime, reason: str) -> int:
        rows = self._session.scalars(
            select(PoseAnalysis).where(
                PoseAnalysis.status == PoseAnalysisStatus.PROCESSING.value,
                PoseAnalysis.started_at.isnot(None),
                PoseAnalysis.started_at <= stale_before,
            )
        ).all()
        for row in rows:
            row.status = PoseAnalysisStatus.FAILED.value
            row.error_message = reason[:300]
            row.completed_at = now
            if row.started_at is not None:
                delta = now - row.started_at
                row.duration_ms = max(
                    delta.days * 86_400_000
                    + delta.seconds * 1000
                    + delta.microseconds // 1000,
                    0,
                )
            self._session.flush()
        return len(rows)
