from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
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

    @abstractmethod
    def expired_for_retention(self, now: datetime) -> list[MediaAsset]:
        """Assets con `retention_until < now` que aún conservan binario (Fase 9)."""
