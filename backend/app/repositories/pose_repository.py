from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.models.pose import PoseAnalysis


class PoseRepository(ABC):
    @abstractmethod
    def get(self, analysis_id: UUID) -> PoseAnalysis | None: ...

    @abstractmethod
    def add(self, analysis: PoseAnalysis) -> PoseAnalysis: ...

    @abstractmethod
    def save(self, analysis: PoseAnalysis) -> PoseAnalysis: ...

    @abstractmethod
    def find_active_for_asset(self, asset_id: UUID) -> PoseAnalysis | None:
        """Tarea activa (queued/processing) de un asset, si existe."""

    @abstractmethod
    def list_page(
        self,
        *,
        profile_id: UUID,
        status: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[PoseAnalysis], int]: ...

    @abstractmethod
    def list_page_by_asset(
        self,
        *,
        media_asset_id: UUID,
        status: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[PoseAnalysis], int]: ...

    @abstractmethod
    def claim_next(self) -> PoseAnalysis | None:
        """Reserva la siguiente tarea queued (FOR UPDATE SKIP LOCKED)."""

    @abstractmethod
    def mark_stale_failed(self, stale_before, *, now, reason: str) -> int:
        """Marca failed las tareas processing con started_at <= stale_before. Devuelve el conteo."""
