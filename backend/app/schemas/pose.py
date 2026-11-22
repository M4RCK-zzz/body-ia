from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.domain.pose import PoseAnalysisStatus

# La etiqueta visible para TODAS las salidas de pose (NUNCA una observación).
VISUAL_ESTIMATE_BADGE = "ESTIMACIÓN VISUAL"


class PoseLandmark(BaseModel):
    """Coordenadas normalizadas del MediaPipe Pose Landmarker."""

    index: int
    x: float
    y: float
    z: float | None = None
    visibility: float | None = None


class PoseAnalysisRead(BaseModel):
    """Metadatos de un análisis de pose. Nunca contiene imágenes ni bytes."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    media_asset_id: UUID
    profile_id: UUID
    status: PoseAnalysisStatus
    created_by: str
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = None
    attempt_count: int = 1
    # Provenance (solo en completed/needs_review)
    model_name: str | None = None
    model_version: str | None = None
    quality_flags: dict[str, Any] | None = None
    # Nunca una observación
    landmarks: list[PoseLandmark] | None = None
    error_message: str | None = None
    data_kind: Literal["visual_estimate"] = "visual_estimate"
    visual_estimate_badge: Literal["ESTIMACIÓN VISUAL"] = "ESTIMACIÓN VISUAL"
