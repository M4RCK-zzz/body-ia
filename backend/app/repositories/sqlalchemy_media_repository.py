from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.media import MediaAsset
from app.repositories.media_repository import MediaRepository


class SqlAlchemyMediaRepository(MediaRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, asset_id: UUID) -> MediaAsset | None:
        return self._session.get(MediaAsset, asset_id)

    def add(self, asset: MediaAsset) -> MediaAsset:
        self._session.add(asset)
        return self.save(asset)

    def save(self, asset: MediaAsset) -> MediaAsset:
        self._session.flush()
        return asset

    def list_page(
        self,
        *,
        profile_id: UUID,
        status: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[MediaAsset], int]:
        conditions = [MediaAsset.profile_id == profile_id]
        if status is not None:
            conditions.append(MediaAsset.status == status)
        else:
            conditions.append(MediaAsset.status != "deleted")
        base = (
            select(MediaAsset)
            .where(*conditions)
            .order_by(MediaAsset.uploaded_at.desc(), MediaAsset.id)
        )
        total = self._session.scalar(select(func.count()).select_from(base.subquery())) or 0
        rows = self._session.execute(base.limit(limit).offset(offset)).scalars().all()
        return list(rows), total
