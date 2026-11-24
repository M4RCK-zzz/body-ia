from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.models.simulation import Simulation, SimulationBaseline


class SimulationRepository(ABC):
    @abstractmethod
    def get(self, simulation_id: UUID) -> Simulation | None: ...

    @abstractmethod
    def add(self, simulation: Simulation) -> Simulation: ...

    @abstractmethod
    def save(self, simulation: Simulation) -> Simulation: ...

    @abstractmethod
    def add_baseline(self, row: SimulationBaseline) -> SimulationBaseline: ...

    @abstractmethod
    def baselines_for(self, simulation_id: UUID) -> list[SimulationBaseline]:
        """Filas de referencia base, ordenadas por métrica."""

    @abstractmethod
    def list_page(
        self,
        *,
        profile_id: UUID,
        status: str | None,
        include_archived: bool,
        limit: int,
        offset: int,
    ) -> tuple[list[Simulation], int]: ...

    @abstractmethod
    def list_page_for_user(
        self,
        *,
        created_by_user_id: UUID,
        status: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Simulation], int]:
        """Escenarios creados por el usuario en expedientes con acceso vigente."""

    @abstractmethod
    def count_active_for_profile(self, profile_id: UUID) -> int:
        """Escenarios en `draft`/`queued` del expediente (límite por expediente)."""

    @abstractmethod
    def claim_next(self) -> Simulation | None:
        """Reserva el siguiente `queued` (FOR UPDATE SKIP LOCKED)."""

    @abstractmethod
    def mark_stale_failed(self, stale_before, *, now, reason: str) -> int:
        """Marca `failed` los `queued`/`processing` abandonados. Devuelve el conteo."""
