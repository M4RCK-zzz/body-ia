from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from app.models.report import Report


class ReportRepository(ABC):
    @abstractmethod
    def get(self, report_id: UUID) -> Report | None: ...

    @abstractmethod
    def add(self, report: Report) -> Report: ...

    @abstractmethod
    def save(self, report: Report) -> Report: ...

    @abstractmethod
    def list_page(
        self,
        *,
        profile_id: UUID,
        status: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Report], int]: ...

    @abstractmethod
    def list_page_for_user(
        self,
        *,
        requested_by_user_id: UUID,
        status: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Report], int]:
        """Reportes solicitados por el usuario (cualquier expediente con acceso vivo)."""

    @abstractmethod
    def find_active_for_profile(
        self, *, profile_id: UUID, kind: str, date_from: datetime | None, date_to: datetime | None
    ) -> Report | None:
        """Reporte idéntico en cola/proceso, para idempotencia."""

    @abstractmethod
    def claim_next(self) -> Report | None:
        """Reserva el siguiente reporte queued (FOR UPDATE SKIP LOCKED)."""

    @abstractmethod
    def mark_stale_failed(self, stale_before: datetime, *, now: datetime, reason: str) -> int:
        """Marca failed los processing con started_at <= stale_before. Devuelve el conteo."""

    @abstractmethod
    def expired_for_retention(self, cutoff: datetime) -> list[Report]:
        """Reportes generados/fallidos con `completed_at < cutoff` (Fase 9)."""
