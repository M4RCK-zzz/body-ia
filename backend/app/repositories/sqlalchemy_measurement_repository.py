from collections.abc import Iterable
from datetime import datetime
from uuid import UUID
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased
from app.core.errors import ConflictError
from app.domain.measurements import MeasurementType
from app.models.measurement import Measurement
from app.repositories.measurement_repository import MeasurementRepository

class SqlAlchemyMeasurementRepository(MeasurementRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, measurement_id: UUID, profile_id: UUID) -> Measurement | None:
        return self._session.scalar(
            select(Measurement).where(
                Measurement.id == measurement_id, Measurement.profile_id == profile_id
            )
        )

    def add(self, measurement: Measurement) -> Measurement:
        self._session.add(measurement)
        try:
            self._session.flush()
        except IntegrityError as exc:
            raise ConflictError("La medición ya fue corregida por otra operación.") from exc
        return measurement

    def is_superseded(self, measurement_id: UUID) -> bool:
        found = self._session.scalar(
            select(Measurement.id).where(Measurement.supersedes_id == measurement_id).limit(1)
        )
        return found is not None

    def superseded_among(self, measurement_ids: Iterable[UUID]) -> set[UUID]:
        ids = list(measurement_ids)
        if not ids:
            return set()
        rows = self._session.scalars(
            select(Measurement.supersedes_id).where(Measurement.supersedes_id.in_(ids))
        )
        return {row for row in rows if row is not None}

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
        conditions = [Measurement.profile_id == profile_id]
        if metric_type is not None:
            conditions.append(Measurement.metric_type == metric_type.value)
        if only_current:
            newer = aliased(Measurement)
            conditions.append(~select(newer.id).where(newer.supersedes_id == Measurement.id).exists())
        if date_from is not None:
            conditions.append(Measurement.measured_at >= date_from)
        if date_to is not None:
            conditions.append(Measurement.measured_at <= date_to)

        total = self._session.scalar(
            select(func.count()).select_from(Measurement).where(*conditions)
        ) or 0
        order = (
            (Measurement.measured_at.asc(), Measurement.recorded_at.asc(), Measurement.id)
            if ascending
            else (Measurement.measured_at.desc(), Measurement.recorded_at.desc(), Measurement.id)
        )
        stmt = select(Measurement).where(*conditions).order_by(*order).limit(limit).offset(offset)
        return list(self._session.scalars(stmt)), total

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
            following = self._session.scalar(
                select(Measurement).where(Measurement.supersedes_id == chain[-1].id)
            )
            if following is None:
                break
            chain.append(following)
        return chain