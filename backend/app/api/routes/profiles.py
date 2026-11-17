from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from app.api.deps import get_profile_service
from app.domain.profiles import ProfileStatus
from app.schemas.common import Page
from app.schemas.profile import ProfileCreate, ProfileRead, ProfileUpdate
from app.services.profile_service import ProfileService

router = APIRouter(prefix="/profiles", tags=["Expedientes"])

@router.post("", response_model=ProfileRead, status_code=status.HTTP_201_CREATED)
def create_profile(
    payload: ProfileCreate, service: ProfileService = Depends(get_profile_service)
) -> ProfileRead:
    return ProfileRead.model_validate(service.create(payload.display_code))

@router.get("", response_model=Page[ProfileRead])
def list_profiles(
    status_filter: ProfileStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    service: ProfileService = Depends(get_profile_service),
) -> Page[ProfileRead]:
    rows, total = service.list_page(status=status_filter, limit=limit, offset=offset)
    return Page[ProfileRead](
        items=[ProfileRead.model_validate(p) for p in rows], total=total, limit=limit, offset=offset
    )

@router.get("/{profile_id}", response_model=ProfileRead)
def get_profile(
    profile_id: UUID, service: ProfileService = Depends(get_profile_service)
) -> ProfileRead:
    return ProfileRead.model_validate(service.get(profile_id))

@router.patch("/{profile_id}", response_model=ProfileRead)
def update_profile(
    profile_id: UUID,
    payload: ProfileUpdate,
    service: ProfileService = Depends(get_profile_service),
) -> ProfileRead:
    return ProfileRead.model_validate(service.rename(profile_id, payload.display_code))

@router.post("/{profile_id}/archive", response_model=ProfileRead)
def archive_profile(
    profile_id: UUID, service: ProfileService = Depends(get_profile_service)
) -> ProfileRead:
    return ProfileRead.model_validate(service.archive(profile_id))

@router.post("/{profile_id}/restore", response_model=ProfileRead)
def restore_profile(
    profile_id: UUID, service: ProfileService = Depends(get_profile_service)
) -> ProfileRead:
    return ProfileRead.model_validate(service.restore(profile_id))