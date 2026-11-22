from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utcnow
from app.db.base import Base
from app.domain.pose import PoseAnalysisStatus


class PoseAnalysis(Base):
    """Resultado IA de pose de un MediaAsset `ready` (Fase 5).

    Reglas de negocio:
    - Estado `queued`: sin landmarks, sin completed_at.
    - Estado `processing`: sin landmarks, con started_at, sin completed_at.
    - Estados terminales (`completed`/`needs_review`/`failed`): started_at +
      completed_at presentes; `completed`/`needs_review` llevan landmarks_json.
    """

    __tablename__ = "pose_analyses"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'processing', 'completed', 'failed', 'needs_review')",
            name="ck_pose_analyses_status",
        ),
        CheckConstraint(
            "(status IN ('completed', 'needs_review') AND landmarks_json IS NOT NULL) "
            "OR (status NOT IN ('completed', 'needs_review') AND landmarks_json IS NULL)",
            name="ck_pose_analyses_landmarks",
        ),
        CheckConstraint(
            "(status = 'queued' AND started_at IS NULL AND completed_at IS NULL) "
            "OR (status = 'processing' AND started_at IS NOT NULL AND completed_at IS NULL) "
            "OR (status IN ('completed', 'needs_review', 'failed') "
            "AND started_at IS NOT NULL AND completed_at IS NOT NULL)",
            name="ck_pose_analyses_lifecycle",
        ),
        Index("ix_pose_analyses_media_asset_id", "media_asset_id"),
        Index("ix_pose_analyses_profile_created_at", "profile_id", "created_at"),
        Index("ix_pose_analyses_status_created_at", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    media_asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("media_assets.id", ondelete="RESTRICT")
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="RESTRICT")
    )
    status: Mapped[str] = mapped_column(
        String(16),
        default=PoseAnalysisStatus.QUEUED.value,
        server_default=PoseAnalysisStatus.QUEUED.value,
    )
    model_name: Mapped[str | None] = mapped_column(String(64))
    model_version: Mapped[str | None] = mapped_column(String(96))
    model_config: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    landmarks_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    quality_flags_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error_message: Mapped[str | None] = mapped_column(String(300))
    created_by_snapshot: Mapped[str] = mapped_column(String(120))
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    attempt_count: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )

    @property
    def created_by(self) -> str:
        return self.created_by_snapshot
