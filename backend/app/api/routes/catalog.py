from fastapi import APIRouter, Depends

from app.api.deps import get_metric_catalog
from app.domain.metrics import METHOD_LABELS, MetricCatalog
from app.schemas.measurement import MeasurementCatalogRead, MethodRead, MetricSpecRead

router = APIRouter(prefix="/catalog", tags=["Catálogo"])

@router.get("/measurements", response_model=MeasurementCatalogRead)
def get_measurement_catalog(
    catalog: MetricCatalog = Depends(get_metric_catalog),
) -> MeasurementCatalogRead:
    return MeasurementCatalogRead(
        metrics=[
            MetricSpecRead(
                metric_type=s.metric_type,
                label=s.label,
                unit=s.unit,
                min_value=float(s.min_value),
                max_value=float(s.max_value),
            )
            for s in catalog.all()
        ],
        methods=[MethodRead(value=m, label=label) for m, label in METHOD_LABELS.items()],
    )