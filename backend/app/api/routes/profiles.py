from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_profile_service
from app.api.security import CurrentUser
from app.domain.access import AccessLevel
from app.domain.profiles import ProfileStatus
from app.schemas.access import ProfileDetailRead
from app.schemas.common import Page
from app.schemas.profile import ProfileCreate, ProfileRead, ProfileUpdate
from app.services.profile_service import ProfileService, ProfileView

router = APIRouter(prefix="/profiles", tags=["Expedientes"])


def _read(view: ProfileView) -> ProfileDetailRead:
    return ProfileDetailRead(
        **ProfileRead.model_validate(view.profile).model_dump(),
        my_access=AccessLevel(view.my_access),
    )


@router.post("", response_model=ProfileDetailRead, status_code=status.HTTP_201_CREATED)
def create_profile(
    user: CurrentUser,
    payload: ProfileCreate,
    service: ProfileService = Depends(get_profile_service),
) -> ProfileDetailRead:
    return _read(service.create(user, payload.display_code))


@router.get("", response_model=Page[ProfileDetailRead])
def list_profiles(
    user: CurrentUser,
    status_filter: ProfileStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    service: ProfileService = Depends(get_profile_service),
) -> Page[ProfileDetailRead]:
    views, total = service.list_page(user, status=status_filter, limit=limit, offset=offset)
    return Page[ProfileDetailRead](
        items=[_read(v) for v in views], total=total, limit=limit, offset=offset
    )


@router.get("/{profile_id}", response_model=ProfileDetailRead)
def get_profile(
    user: CurrentUser, profile_id: UUID, service: ProfileService = Depends(get_profile_service)
) -> ProfileDetailRead:
    return _read(service.get(user, profile_id))


@router.patch("/{profile_id}", response_model=ProfileDetailRead)
def update_profile(
    user: CurrentUser,
    profile_id: UUID,
    payload: ProfileUpdate,
    service: ProfileService = Depends(get_profile_service),
) -> ProfileDetailRead:
    return _read(service.rename(user, profile_id, payload.display_code))


@router.post("/{profile_id}/archive", response_model=ProfileDetailRead)
def archive_profile(
    user: CurrentUser, profile_id: UUID, service: ProfileService = Depends(get_profile_service)
) -> ProfileDetailRead:
    return _read(service.archive(user, profile_id))


@router.post("/{profile_id}/restore", response_model=ProfileDetailRead)
def restore_profile(
    user: CurrentUser, profile_id: UUID, service: ProfileService = Depends(get_profile_service)
) -> ProfileDetailRead:
    return _read(service.restore(user, profile_id))