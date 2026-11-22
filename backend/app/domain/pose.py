"""Dominio del análisis de pose (Fase 5): estados, límites y banderas.

No contiene lógica ni I/O: solo enums y constantes puras.
"""
from __future__ import annotations

from enum import StrEnum


class PoseAnalysisStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    NEEDS_REVIEW = "needs_review"


TERMINAL_STATUSES: frozenset[str] = frozenset(
    {
        PoseAnalysisStatus.COMPLETED.value,
        PoseAnalysisStatus.FAILED.value,
        PoseAnalysisStatus.NEEDS_REVIEW.value,
    }
)

NON_TERMINAL_STATUSES: frozenset[str] = frozenset(
    {
        PoseAnalysisStatus.QUEUED.value,
        PoseAnalysisStatus.PROCESSING.value,
    }
)

# Landmarks esperados (MediaPipe Pose Landmarker, full).
LANDMARK_COUNT = 33

# Visibilidad mínima para contar un landmark como "visible".
VISIBILITY_THRESHOLD = 0.5

# Fases de pose (etiquetas usadas en quality_flags_json).
POSE_COMPLETE_FLAG = "pose_complete"
POSE_PARTIAL_FLAG = "pose_partial"
LOW_VISIBILITY_FLAG = "low_visibility"

POSE_LABEL: dict[str, str] = {
    PoseAnalysisStatus.QUEUED.value: "En cola",
    PoseAnalysisStatus.PROCESSING.value: "Procesando",
    PoseAnalysisStatus.COMPLETED.value: "Completado",
    PoseAnalysisStatus.FAILED.value: "Fallido",
    PoseAnalysisStatus.NEEDS_REVIEW.value: "Requiere revisión",
}

POSE_FLAG_LABELS: dict[str, str] = {
    POSE_PARTIAL_FLAG: "Pose parcial (detectados pocos puntos)",
    POSE_COMPLETE_FLAG: "Pose completa",
    LOW_VISIBILITY_FLAG: "Visibilidad baja",
}
