from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import get_pose_service
from app.api.security import CurrentUser
from app.domain.pose import PoseAnalysisStatus
from app.schemas.common import Page
from app.schemas.pose import PoseAnalysisRead, PoseLandmark
from app.services.pose_service import PoseService

router = APIRouter(prefix="/media/{asset_id}/pose-analyses", tags=["Análisis de pose"])
asset_router = APIRouter(prefix="/pose-analyses", tags=["Análisis de pose"])
profile_router = APIRouter(
    prefix="/profiles/{profile_id}/pose-analyses", tags=["Análisis de pose"]
)


def _read(analysis) -> PoseAnalysisRead:
    """Serializa un análisis. Landmarks/flags solo en estados visualmente legibles."""
    data = PoseAnalysisRead.model_validate(analysis)
    if analysis.status in ("completed", "needs_review"):
        raw = (analysis.landmarks_json or {}).get("landmarks")
        if raw:
            data.landmarks = [PoseLandmark.model_validate(lm) for lm in raw]
        data.quality_flags = dict(analysis.quality_flags_json) if analysis.quality_flags_json else None
    else:
        data.landmarks = None
        data.quality_flags = None
    # Provenance (solo cuando el análisis llegó a un estado completo o de revisión).
    if analysis.status in ("completed", "needs_review"):
        data.model_name = analysis.model_name
        data.model_version = analysis.model_version
    return data


@router.post(
    "",
    response_model=PoseAnalysisRead,
    status_code=status.HTTP_201_CREATED,
    summary="Encola un análisis de pose para un archivo ready (idempotente)",
    description=(
        "Crea una tarea de análisis de pose para un archivo validado. "
        "Si ya existe una tarea queued/processing para el mismo archivo, "
        "responde 200 con esa misma tarea (idempotente)."
    ),
)
def enqueue_pose(
    asset_id: UUID,
    user: CurrentUser,
    response: Response,
    service: PoseService = Depends(get_pose_service),  # noqa: B008 - patrón del repo
) -> PoseAnalysisRead:
    analysis, created = service.enqueue(user, asset_id)
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return _read(analysis)


@router.get("", response_model=Page[PoseAnalysisRead])
def list_pose_for_asset(
    asset_id: UUID,
    user: CurrentUser,
    status: PoseAnalysisStatus | None = Query(default=None),  # noqa: B008 - patrón del repo
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    service: PoseService = Depends(get_pose_service),  # noqa: B008 - patrón del repo
) -> Page[PoseAnalysisRead]:
    analyses, total = service.list_for_asset(
        user, asset_id, status=status.value if status else None, limit=limit, offset=offset
    )
    return Page[PoseAnalysisRead](
        items=[_read(a) for a in analyses], total=total, limit=limit, offset=offset
    )


@profile_router.get("", response_model=Page[PoseAnalysisRead])
def list_pose_for_profile(
    profile_id: UUID,
    user: CurrentUser,
    status: PoseAnalysisStatus | None = Query(default=None),  # noqa: B008 - patrón del repo
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    service: PoseService = Depends(get_pose_service),  # noqa: B008 - patrón del repo
) -> Page[PoseAnalysisRead]:
    analyses, total = service.list_for_profile(
        user, profile_id, status=status.value if status else None, limit=limit, offset=offset
    )
    return Page[PoseAnalysisRead](
        items=[_read(a) for a in analyses], total=total, limit=limit, offset=offset
    )


@asset_router.get("/{analysis_id}", response_model=PoseAnalysisRead)
def get_pose(
    analysis_id: UUID,
    user: CurrentUser,
    service: PoseService = Depends(get_pose_service),  # noqa: B008 - patrón del repo
) -> PoseAnalysisRead:
    return _read(service.get(user, analysis_id))
