from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import get_profile_access_service
from app.api.security import CurrentUser
from app.schemas.access import AccessGrantRequest, AccessRead
from app.services.profile_access_service import ProfileAccessService

router = APIRouter(prefix="/profiles/{profile_id}/access", tags=["Acceso a expedientes"])

ServiceDep = Annotated[ProfileAccessService, Depends(get_profile_access_service)]


@router.get("", response_model=list[AccessRead])
def list_access(profile_id: UUID, user: CurrentUser, service: ServiceDep) -> list[AccessRead]:
    return [AccessRead.from_access(a) for a in service.list_access(user, profile_id)]


@router.post("", response_model=AccessRead, status_code=status.HTTP_201_CREATED)
def grant_access(
    profile_id: UUID, payload: AccessGrantRequest, user: CurrentUser, service: ServiceDep
) -> AccessRead:
    grant = service.grant(user, profile_id, str(payload.email), payload.level)
    return AccessRead.from_access(grant)


@router.delete("/{target_user_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_access(
    profile_id: UUID, target_user_id: UUID, user: CurrentUser, service: ServiceDep
) -> Response:
    service.revoke(user, profile_id, target_user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)