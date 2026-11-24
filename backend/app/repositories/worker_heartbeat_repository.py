"""Latidos de workers: puerto + implementación SQLAlchemy (Fase 9)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.worker_heartbeat import WorkerHeartbeat


class WorkerHeartbeatRepository(ABC):
    @abstractmethod
    def beat(self, name: str, *, version: str, now: datetime) -> WorkerHeartbeat: ...

    @abstractmethod
    def record_error(self, name: str, *, message: str, now: datetime) -> None: ...

    @abstractmethod
    def list_all(self) -> list[WorkerHeartbeat]: ...


class SqlAlchemyWorkerHeartbeatRepository(WorkerHeartbeatRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def beat(self, name: str, *, version: str, now: datetime) -> WorkerHeartbeat:
        row = self._session.get(WorkerHeartbeat, name)
        if row is None:
            row = WorkerHeartbeat(
                name=name,
                worker_version=version,
                started_at=now,
                last_seen_at=now,
                iterations=1,
            )
            self._session.add(row)
        else:
            row.worker_version = version
            row.last_seen_at = now
            row.iterations += 1
        self._session.flush()
        return row

    def record_error(self, name: str, *, message: str, now: datetime) -> None:
        row = self._session.get(WorkerHeartbeat, name)
        if row is None:
            return
        row.last_error_at = now
        row.last_error = message[:300]

    def list_all(self) -> list[WorkerHeartbeat]:
        return list(self._session.scalars(select(WorkerHeartbeat).order_by(WorkerHeartbeat.name)))
