from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4
from app.core.clock import utcnow
from app.core.errors import ConflictError
from app.domain.measurements import MeasurementType
from app.domain.metrics import default_catalog
from app.domain.profiles import ProfileStatus
from app.models.measurement import Measurement
from app.models.profile import Profile
from app.repositories.measurement_repository import MeasurementRepository
from app.repositories.profile_repository import ProfileRepository
from app.services.measurement_service import MeasurementService
from app.services.profile_service import ProfileService

class FakeTransaction:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0
    def commit(self) -> None:
        self.commits += 1
    def rollback(self) -> None:
        self.rollbacks += 1

class InMemoryProfileRepository(ProfileRepository):
    def __init__(self) -> None:
        self.items: dict[UUID, Profile] = {}
    def get(self, profile_id: UUID) -> Profile | None:
        return self.items.get(profile_id)
    def get_by_display_code(self, display_code: str) -> Profile | None:
        return next((p for p in self.items.values() if p.display_code == display_code), None)
    def add(self, profile: Profile) -> Profile:
        now = utcnow()
        profile.id = profile.id or uuid4()
        profile.created_at = now
        profile.updated_at = now
        self.items[profile.id] = profile
        return profile
    def save(self, profile: Profile) -> Profile:
        return profile
    def list_page(
        self, *, status: ProfileStatus | None, limit: int, offset: int
    ) -> tuple[list[Profile], int]:
        rows = [p for p in self.items.values() if status is None or p.status == status.value]
        rows.sort(key=lambda p: p.created_at, reverse=True)
        return rows[offset : offset + limit], len(rows)

class InMemoryMeasurementRepository(MeasurementRepository):
    def __init__(self) -> None:
        self.items: list[Measurement] = []
    def get(self, measurement_id: UUID, profile_id: UUID) -> Measurement | None:
        return next(
            (m for m in self.items if m.id == measurement_id and m.profile_id == profile_id), None
        )
    def add(self, measurement: Measurement) -> Measurement:
        if measurement.supersedes_id is not None and self.is_superseded(measurement.supersedes_id):
            raise ConflictError("La medición ya fue corregida por otra operación.")
        measurement.id = uuid4()
        measurement.recorded_at = utcnow()
        self.items.append(measurement)
        return measurement
    def is_superseded(self, measurement_id: UUID) -> bool:
        return any(m.supersedes_id == measurement_id for m in self.items)
    def superseded_among(self, measurement_ids: Iterable[UUID]) -> set[UUID]:
        wanted = set(measurement_ids)
        return {m.supersedes_id for m in self.items if m.supersedes_id in wanted}
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
    ) -> tuple[list[Measurement], int]:
        rows = [m for m in self.items if m.profile_id == profile_id]
        if metric_type is not None:
            rows = [m for m in rows if m.metric_type == metric_type.value]
        if only_current:
            rows = [m for m in rows if not self.is_superseded(m.id)]
        if date_from is not None:
            rows = [m for m in rows if m.measured_at >= date_from]
        if date_to is not None:
            rows = [m for m in rows if m.measured_at <= date_to]
        rows.sort(key=lambda m: (m.measured_at, m.recorded_at), reverse=not ascending)
        return rows[offset : offset + limit], len(rows)
    def get_chain(self, measurement_id: UUID, profile_id: UUID) -> list[Measurement]:
        node = self.get(measurement_id, profile_id)
        if node is None:
            return []
        chain = [node]
        while chain[0].supersedes_id is not None:
            previous = self.get(chain[0].supersedes_id, profile_id)
            if previous is None:
                break
            chain.insert(0, previous)
        while True:
            following = next((m for m in self.items if m.supersedes_id == chain[-1].id), None)
            if following is None:
                break
            chain.append(following)
        return chain

@dataclass
class Services:
    profiles_repo: InMemoryProfileRepository
    measurements_repo: InMemoryMeasurementRepository
    tx: FakeTransaction
    profiles: ProfileService
    measurements: MeasurementService

def build_services(clock=utcnow) -> Services:
    profiles_repo = InMemoryProfileRepository()
    measurements_repo = InMemoryMeasurementRepository()
    tx = FakeTransaction()
    return Services(
        profiles_repo=profiles_repo,
        measurements_repo=measurements_repo,
        tx=tx,
        profiles=ProfileService(profiles_repo, tx, clock=clock),
        measurements=MeasurementService(
            profiles_repo, measurements_repo, default_catalog(), tx, clock=clock
        ),
    )