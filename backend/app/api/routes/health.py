from fastapi import APIRouter, Depends
from app.api.deps import get_health_service
from app.schemas.health import HealthResponse
from app.services.health_service import HealthService

router = APIRouter(tags=["system"])

@router.get("/health", response_model=HealthResponse, summary="Estado del servicio")
def read_health(service: HealthService = Depends(get_health_service)) -> HealthResponse:
    return service.check()