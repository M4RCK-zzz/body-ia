from fastapi import APIRouter, Depends, Response, status

from app.api.deps import get_health_service
from app.api.security import AdminUser
from app.schemas.health import HealthResponse, ReadinessResponse, WorkersResponse
from app.services.health_service import HealthService

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse, summary="Estado del servicio")
def read_health(service: HealthService = Depends(get_health_service)) -> HealthResponse:
    return service.check()


@router.get(
    "/health/live",
    response_model=HealthResponse,
    summary="Liveness: el proceso responde (no consulta la BD)",
)
def read_liveness(service: HealthService = Depends(get_health_service)) -> HealthResponse:
    return service.live()


@router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    summary="Readiness: BD, storage y migraciones al día (503 si algo falla)",
)
def read_readiness(
    response: Response, service: HealthService = Depends(get_health_service)
) -> ReadinessResponse:
    result = service.ready()
    if not result.ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return result


@router.get(
    "/health/workers",
    response_model=WorkersResponse,
    summary="Latidos de los workers (pose, reportes, simulación, retención) — solo admin",
)
def read_workers(
    _admin: AdminUser, service: HealthService = Depends(get_health_service)
) -> WorkersResponse:
    """Estado operativo interno: expone versiones, iteraciones y `last_error`.

    Queda detrás de `require_admin` (mismo criterio que `/api/admin/*`): a un
    anónimo o a un usuario normal no le sirve y filtraría detalles internos.
    """
    return service.workers()
