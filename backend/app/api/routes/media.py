from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile, status

from app.api.deps import get_media_service
from app.api.security import CurrentUser
from app.domain.media import MediaStatus
from app.schemas.common import Page
from app.schemas.media import MediaAssetRead
from app.services.media_service import MediaService

router = APIRouter(prefix="/profiles/{profile_id}/media", tags=["Captura"])
asset_router = APIRouter(prefix="/media", tags=["Captura"])


def _read(asset) -> MediaAssetRead:
    return MediaAssetRead.model_validate(asset)


@router.post("", response_model=MediaAssetRead, status_code=status.HTTP_201_CREATED)
def upload_media(
    profile_id: UUID,
    user: CurrentUser,
    file: Annotated[UploadFile, File(description="Imagen JPEG/PNG/WebP (máx. 50 MB)")],
    service: MediaService = Depends(get_media_service),  # noqa: B008 - patrón del repo
) -> MediaAssetRead:
    data = file.file.read(service.max_upload_bytes + 1)
    return _read(
        service.upload(
            user,
            profile_id,
            data=data,
            declared_mime=file.content_type,
        )
    )


@router.get("", response_model=Page[MediaAssetRead])
def list_media(
    profile_id: UUID,
    user: CurrentUser,
    status: MediaStatus | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    service: MediaService = Depends(get_media_service),  # noqa: B008
) -> Page[MediaAssetRead]:
    assets, total = service.list_assets(
        user, profile_id, status=status, limit=limit, offset=offset
    )
    return Page[MediaAssetRead](
        items=[_read(a) for a in assets], total=total, limit=limit, offset=offset
    )


@asset_router.get("/{asset_id}", response_model=MediaAssetRead)
def get_media(
    asset_id: UUID,
    user: CurrentUser,
    service: MediaService = Depends(get_media_service),  # noqa: B008
) -> MediaAssetRead:
    return _read(service.get(user, asset_id))


@asset_router.get("/{asset_id}/content")
def read_media_content(
    asset_id: UUID,
    user: CurrentUser,
    service: MediaService = Depends(get_media_service),  # noqa: B008
) -> Response:
    asset, data = service.content(user, asset_id)
    return Response(
        content=data,
        media_type=asset.mime_type or "application/octet-stream",
        headers={
            "Content-Length": str(len(data)),
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": "inline",
        },
    )


@asset_router.delete("/{asset_id}", response_model=MediaAssetRead)
def delete_media(
    asset_id: UUID,
    user: CurrentUser,
    service: MediaService = Depends(get_media_service),  # noqa: B008
) -> MediaAssetRead:
    return _read(service.delete(user, asset_id))
