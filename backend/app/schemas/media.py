from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.domain.media import MediaStatus


class MediaAssetRead(BaseModel):
    """Metadatos de un medio capturado. Nunca contiene bytes ni el nombre original."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    profile_id: UUID
    status: MediaStatus
    mime_type: str | None
    size_bytes: int
    width: int | None
    height: int | None
    checksum: str | None
    rejection_reason: str | None
    uploaded_by: str
    uploaded_at: datetime
    ready_at: datetime | None
    rejected_at: datetime | None
    deleted_at: datetime | None
    retention_until: datetime
