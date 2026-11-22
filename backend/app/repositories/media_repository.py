from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.models.media import MediaAsset


class MediaRepository(ABC):
    @abstractmethod
    def get(self, asset_id: UUID) -> MediaAsset | None: ...

    @abstractmethod
    def add(self, asset: MediaAsset) -> MediaAsset: ...

    @abstractmethod
    def save(self, asset: MediaAsset) -> MediaAsset: ...

    @abstractmethod
    def list_page(
        self,
        *,
        profile_id: UUID,
        status: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[MediaAsset], int]: ...
