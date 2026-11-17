from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from pydantic import AwareDatetime
from app.api.deps import get_measurement_service
from app.domain.measurements import MeasurementCorrection, MeasurementType, NewMeasurement
from app.schemas.common import Page
from app.schemas.measurement import (
    MeasurementCorrect, MeasurementCreate, MeasurementRead, MeasurementSeriesRead, SeriesPoint,
)
from app.services.measurement_service import MeasurementService, MeasurementView

router = APIRouter(prefix="/profiles/{profile_id}/measurements", tags=["Mediciones"])

def _to_read(view: MeasurementView) -> MeasurementRead:
    return MeasurementRead.model_validate(view.measurement).model_copy(
        update={"is_current": view.is_current}
    )

@router.post("", response_model=MeasurementRead, status_code=status.HTTP_201_CREATED)
def record_measurement(
    profile_id: UUID,
    payload: MeasurementCreate,
    service: MeasurementService = Depends(get_measurement_service),
) -> MeasurementRead:
    return _to_read(service.record(profile_id, NewMeasurement(**payload.model_dump())))

@router.get("", response_model=Page[MeasurementRead])
def list_measurements(
    profile_id: UUID,
    metric_type: MeasurementType | None = None,
    include_superseded: bool = False,
    date_from: AwareDatetime | None = None,
    date_to: AwareDatetime | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: MeasurementService = Depends(get_measurement_service),
) -> Page[MeasurementRead]:
    views, total = service.list_measurements(
        profile_id,
        metric_type=metric_type,
        include_superseded=include_superseded,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    return Page[MeasurementRead](
        items=[_to_read(v) for v in views], total=total, limit=limit, offset=offset
    )

@router.get("/series", response_model=MeasurementSeriesRead)
def get_series(
    profile_id: UUID,
    metric_type: MeasurementType = Query(...),
    service: MeasurementService = Depends(get_measurement_service),
) -> MeasurementSeriesRead:
    data = service.series(profile_id, metric_type)
    return MeasurementSeriesRead(
        metric_type=data.metric_type,
        unit=data.unit,
        points=[
            SeriesPoint(
                id=m.id,
                measured_at=m.measured_at,
                value=m.value,
                method=m.method,
                corrected=m.supersedes_id is not None,
            )
            for m in data.points
        ],
    )

@router.get("/{measurement_id}", response_model=MeasurementRead)
def get_measurement(
    profile_id: UUID,
    measurement_id: UUID,
    service: MeasurementService = Depends(get_measurement_service),
) -> MeasurementRead:
    return _to_read(service.get(profile_id, measurement_id))

@router.get("/{measurement_id}/history", response_model=list[MeasurementRead])
def get_measurement_history(
    profile_id: UUID,
    measurement_id: UUID,
    service: MeasurementService = Depends(get_measurement_service),
) -> list[MeasurementRead]:
    return [_to_read(v) for v in service.history(profile_id, measurement_id)]

@router.post(
    "/{measurement_id}/corrections",
    response_model=MeasurementRead,
    status_code=status.HTTP_201_CREATED,
)
def correct_measurement(
    profile_id: UUID,
    measurement_id: UUID,
    payload: MeasurementCorrect,
    service: MeasurementService = Depends(get_measurement_service),
) -> MeasurementRead:
    correction = MeasurementCorrection(**payload.model_dump())
    return _to_read(service.correct(profile_id, measurement_id, correction))