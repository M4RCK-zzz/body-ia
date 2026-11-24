from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_simulation_service
from app.api.security import CurrentUser
from app.domain.simulation import SimulationStatus
from app.schemas.common import Page
from app.schemas.simulation import (
    SimulationComparisonRead,
    SimulationCreateRequest,
    SimulationLimitsRead,
    SimulationRead,
)
from app.services.simulation_service import SimulationService

router = APIRouter(tags=["Simulación"])


@router.get(
    "/simulations/limits",
    response_model=SimulationLimitsRead,
    summary="Contrato del motor de simulación (modos, rangos y tope de cambio)",
)
def get_limits(
    user: CurrentUser,
    service: SimulationService = Depends(get_simulation_service),  # noqa: B008
) -> SimulationLimitsRead:
    return SimulationLimitsRead(**service.limits_contract())


@router.post(
    "/profiles/{profile_id}/simulations",
    response_model=SimulationRead,
    status_code=status.HTTP_201_CREATED,
    summary="Crea un escenario hipotético (draft o en cola) sobre la base observada",
    description=(
        "El escenario se calcula sobre una **copia** de las mediciones vigentes. "
        "Nunca crea, modifica ni sustituye mediciones: `data_kind=simulation` y la "
        "auditoría registra `simulation.created` (y `simulation.queued` si se ejecuta)."
    ),
)
def create_simulation(
    profile_id: UUID,
    payload: SimulationCreateRequest,
    user: CurrentUser,
    service: SimulationService = Depends(get_simulation_service),  # noqa: B008
) -> SimulationRead:
    simulation, _created = service.create(
        user,
        profile_id,
        label=payload.label,
        parameters=[metric.model_dump() for metric in payload.metrics],
        notes=payload.notes,
        run_now=payload.run_now,
    )
    return SimulationRead.model_validate(simulation)


@router.get("/profiles/{profile_id}/simulations", response_model=Page[SimulationRead])
def list_simulations_for_profile(
    profile_id: UUID,
    user: CurrentUser,
    status_filter: SimulationStatus | None = Query(default=None, alias="status"),
    include_archived: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    service: SimulationService = Depends(get_simulation_service),  # noqa: B008
) -> Page[SimulationRead]:
    rows, total = service.list_for_profile(
        user,
        profile_id,
        status=status_filter.value if status_filter else None,
        include_archived=include_archived,
        limit=limit,
        offset=offset,
    )
    return Page[SimulationRead](
        items=[SimulationRead.model_validate(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/simulations", response_model=Page[SimulationRead])
def list_my_simulations(
    user: CurrentUser,
    status_filter: SimulationStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    service: SimulationService = Depends(get_simulation_service),  # noqa: B008
) -> Page[SimulationRead]:
    """Escenarios creados por el usuario en expedientes donde su acceso sigue vigente."""
    rows, total = service.list_mine(
        user,
        status=status_filter.value if status_filter else None,
        limit=limit,
        offset=offset,
    )
    return Page[SimulationRead](
        items=[SimulationRead.model_validate(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/simulations/{simulation_id}", response_model=SimulationRead)
def get_simulation(
    simulation_id: UUID,
    user: CurrentUser,
    service: SimulationService = Depends(get_simulation_service),  # noqa: B008
) -> SimulationRead:
    return SimulationRead.model_validate(service.get(user, simulation_id))


@router.get(
    "/simulations/{simulation_id}/comparison",
    response_model=SimulationComparisonRead,
    summary="Comparador base observada vs escenario hipotético",
)
def get_comparison(
    simulation_id: UUID,
    user: CurrentUser,
    service: SimulationService = Depends(get_simulation_service),  # noqa: B008
) -> SimulationComparisonRead:
    return SimulationComparisonRead(**service.comparison(user, simulation_id))


@router.post("/simulations/{simulation_id}/run", response_model=SimulationRead)
def run_simulation(
    simulation_id: UUID,
    user: CurrentUser,
    service: SimulationService = Depends(get_simulation_service),  # noqa: B008
) -> SimulationRead:
    """Ejecuta un escenario en borrador (pasa a `queued`; el worker lo calcula)."""
    return SimulationRead.model_validate(service.run(user, simulation_id))


@router.post("/simulations/{simulation_id}/archive", response_model=SimulationRead)
def archive_simulation(
    simulation_id: UUID,
    user: CurrentUser,
    service: SimulationService = Depends(get_simulation_service),  # noqa: B008
) -> SimulationRead:
    """Archiva el escenario (no se borra: la traza se conserva)."""
    return SimulationRead.model_validate(service.archive(user, simulation_id))
