from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from datetime import datetime
from uuid import UUID

from app.domain.measurements import MeasurementType
from app.models.measurement import Measurement


class AnalyticsRepository(ABC):
    """Lecturas agregadas para analítica descriptiva y dashboard (Fase 7).

    Solo devuelve conteos y filas ya filtradas: el cálculo estadístico vive en
    `app.domain.reports` para poder probarlo sin base de datos.
    """

    @abstractmethod
    def current_measurements(
        self,
        *,
        profile_id: UUID,
        metric_type: MeasurementType,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> list[Measurement]:
        """Mediciones vigentes (no reemplazadas) de una métrica, ascendentes."""

    @abstractmethod
    def corrected_count(
        self,
        *,
        profile_id: UUID,
        metric_type: MeasurementType,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> int:
        """Correcciones vigentes (mediciones que reemplazan a otra)."""

    @abstractmethod
    def measurement_count(self, profile_id: UUID) -> int:
        """Total de mediciones vigentes del expediente (todas las métricas)."""

    @abstractmethod
    def latest_measurement_at(self, profile_id: UUID) -> datetime | None:
        """Fecha de la medición vigente más reciente (None si no hay)."""

    @abstractmethod
    def measurement_count_by_profile(self, profile_ids: Iterable[UUID]) -> dict[UUID, int]:
        """Conteo de mediciones vigentes por expediente (para el dashboard)."""

    @abstractmethod
    def latest_measurement_by_profile(
        self, profile_ids: Iterable[UUID]
    ) -> dict[UUID, datetime]:
        """Última fecha de medición vigente por expediente."""
