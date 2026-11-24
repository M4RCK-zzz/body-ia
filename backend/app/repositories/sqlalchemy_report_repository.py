from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.reports import ReportStatus
from app.models.access import ProfileAccess
from app.models.report import Report
from app.repositories.report_repository import ReportRepository

logger = logging.getLogger(__name__)


class SqlAlchemyReportRepository(ReportRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, report_id: UUID) -> Report | None:
        return self._session.get(Report, report_id)

    def add(self, report: Report) -> Report:
        self._session.add(report)
        return self.save(report)

    def save(self, report: Report) -> Report:
        self._session.flush()
        return report

    def list_page(
        self,
        *,
        profile_id: UUID,
        status: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Report], int]:
        conditions = [Report.profile_id == profile_id]
        if status is not None:
            conditions.append(Report.status == status)
        base = (
            select(Report).where(*conditions).order_by(Report.created_at.desc(), Report.id)
        )
        total = self._session.scalar(select(func.count()).select_from(base.subquery())) or 0
        rows = self._session.execute(base.limit(limit).offset(offset)).scalars().all()
        return list(rows), total

    def list_page_for_user(
        self,
        *,
        requested_by_user_id: UUID,
        status: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Report], int]:
        # Solo reportes de expedientes donde el acceso sigue vigente: revocar el
        # acceso oculta el historial de reportes en la misma consulta.
        conditions = [
            Report.requested_by_user_id == requested_by_user_id,
            ProfileAccess.user_id == requested_by_user_id,
            ProfileAccess.revoked_at.is_(None),
        ]
        if status is not None:
            conditions.append(Report.status == status)
        base = (
            select(Report)
            .join(ProfileAccess, ProfileAccess.profile_id == Report.profile_id)
            .where(*conditions)
            .order_by(Report.created_at.desc(), Report.id)
        )
        total = self._session.scalar(select(func.count()).select_from(base.subquery())) or 0
        rows = self._session.execute(base.limit(limit).offset(offset)).scalars().all()
        return list(rows), total

    def find_active_for_profile(
        self, *, profile_id: UUID, kind: str, date_from: datetime | None, date_to: datetime | None
    ) -> Report | None:
        conditions = [
            Report.profile_id == profile_id,
            Report.kind == kind,
            Report.status.in_([ReportStatus.QUEUED.value, ReportStatus.PROCESSING.value]),
            Report.date_from.is_(None) if date_from is None else Report.date_from == date_from,
            Report.date_to.is_(None) if date_to is None else Report.date_to == date_to,
        ]
        return self._session.scalar(
            select(Report).where(*conditions).order_by(Report.created_at.desc()).limit(1)
        )

    def claim_next(self) -> Report | None:
        stmt = (
            select(Report)
            .where(Report.status == ReportStatus.QUEUED.value)
            .order_by(Report.created_at.asc(), Report.id.asc())
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        return self._session.execute(stmt).scalars().first()

    def mark_stale_failed(self, stale_before: datetime, *, now: datetime, reason: str) -> int:
        rows = self._session.scalars(
            select(Report).where(
                Report.status == ReportStatus.PROCESSING.value,
                Report.started_at.isnot(None),
                Report.started_at <= stale_before,
            )
        ).all()
        for row in rows:
            row.status = ReportStatus.FAILED.value
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
