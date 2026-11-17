from abc import ABC, abstractmethod
from collections.abc import Iterable
from datetime import datetime
from uuid import UUID
from app.domain.measurements import MeasurementType
from app.models.measurement import Measurement

class MeasurementRepository(ABC):
    @abstractmethod
    def get(self, measurement_id: UUID, profile_id: UUID) -> Measurement | None: ...
    @abstractmethod
    def add(self, measurement: Measurement) -> Measurement: ...
    @abstractmethod
    def is_superseded(self, measurement_id: UUID) -> bool: ...
    @abstractmethod
    def superseded_among(self, measurement_ids: Iterable[UUID]) -> set[UUID]: ...
    @abstractmethod
    def list_page(
        self,
        *,
        profile_id: UUID,
        metric_type: MeasurementType | None,
        only_current: bool,
        date_from: datetime | None,
        date_to: datetime | None,
        ascending: bool,
        limit: int,
        offset: int,
    ) -> tuple[list[Measurement], int]: ...
    @abstractmethod
    def get_chain(self, measurement_id: UUID, profile_id: UUID) -> list[Measurement]: ...