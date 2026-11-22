from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utcnow
from app.db.base import Base
from app.domain.media import MediaStatus


class MediaAsset(Base):
    """Medios capturados: solo el servidor lee los bytes (storage privado).

    El lifecycle uploaded -> validating -> ready/rejected/deleted es mutable
    a propósito (nota: a diferencia de `measurements` no es append-only).
    """

    __tablename__ = "media_assets"
    __table_args__ = (
        CheckConstraint(
            "status IN ('uploaded', 'validating', 'ready', 'rejected', 'deleted')",
            name="ck_media_assets_status",
        ),
        CheckConstraint("size_bytes > 0", name="ck_media_assets_size_positive"),
        CheckConstraint(
            "status = 'rejected' OR (width > 0 AND height > 0)",
            name="ck_media_assets_dims_positive",
        ),
        CheckConstraint(
            "(status IN ('rejected', 'deleted') OR storage_key IS NOT NULL)",
            name="ck_media_assets_storage_key",
        ),
        Index("ix_media_assets_profile_id", "profile_id"),
        Index("ix_media_assets_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="RESTRICT")
    )
    storage_key: Mapped[str | None] = mapped_column(String(96), unique=True)
    mime_type: Mapped[str | None] = mapped_column(String(32))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    checksum: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(
        String(16),
        default=MediaStatus.UPLOADED.value,
        server_default=MediaStatus.UPLOADED.value,
    )
    rejection_reason: Mapped[str | None] = mapped_column(String(300))
    uploaded_by_snapshot: Mapped[str] = mapped_column(String(120))
    uploaded_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    retention_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    @property
    def uploaded_by(self) -> str:
        return self.uploaded_by_snapshot
