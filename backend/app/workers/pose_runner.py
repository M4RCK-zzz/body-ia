"""Ejecutor de MediaPipe Pose Landmarker (lazy import, Fase 5).

El binario `mediapipe` no se importa al importar este módulo: solo se carga
cuando se crea un runner y se llama a `analyze()` o `ensure_ready()`. Así los
tests unitarios y de API corren sin depender del binario.
"""
from __future__ import annotations

import hashlib
import io
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

VISIBILITY_THRESHOLD = 0.5


@dataclass
class PoseResult:
    landmarks: list[dict[str, Any]]
    visible_count: int
    total_count: int
    quality: str  # "good" | "partial" | "low"
    flags: list[str]
    pose_count: int
    model_name: str
    model_version: str  # sha256[:16] del archivo .task
    model_sha256: str
    mediapipe_version: str
    image_width: int
    image_height: int


class PoseModelError(RuntimeError):
    """El ejecutor no puede arrancar o procesar (modelo/binario no disponible)."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class PoseModelRunner:
    """Wrapper lazy del PoseLandmarker. No sabe nada de la base de datos."""

    def __init__(
        self,
        model_path: Path,
        *,
        min_detection_confidence: float = 0.5,
        full_model_name: str = "pose_landmarker_full",
    ) -> None:
        self._model_path = Path(model_path)
        self._min_detection_confidence = float(min_detection_confidence)
        self._full_model_name = full_model_name
        self._landmarker = None
        self._mediapipe_version: str | None = None
        self._model_sha256: str | None = None

    # --- atributos ---

    @property
    def model_path(self) -> Path:
        return self._model_path

    @property
    def model_version(self) -> str | None:
        """sha256[:16] del archivo .task. None si el archivo no existe."""
        return self._model_sha256[:16] if self._model_sha256 else None

    def ensure_ready(self) -> None:
        """Carga el modelo y el binario. Lanza PoseModelError si no es posible."""
        self._ensure_landmarker()

    def _ensure_landmarker(self) -> None:
        if self._landmarker is not None:
            return
        if not self._model_path.is_file():
            raise PoseModelError(
                f"Modelo de pose no encontrado: {self._model_path}. "
                "Descarga pose_landmarker_full.task en backend/models/ (ver README)."
            )
        try:
            import mediapipe as mp
            from mediapipe.tasks.python.core.base_options import BaseOptions
            from mediapipe.tasks.python.vision import (
                PoseLandmarker,
                PoseLandmarkerOptions,
                RunningMode,
            )
        except ImportError as exc:  # pragma: no cover - depende del binario
            raise PoseModelError(
                "mediapipe no está instalado en el worker. "
                "Instálalo con: pip install mediapipe==1.2.3 (ver README)."
            ) from exc

        self._mediapipe_version = getattr(mp, "__version__", "unknown")
        self._model_sha256 = _sha256_file(self._model_path)
        options = PoseLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(self._model_path)),
            running_mode=RunningMode.IMAGE,
            num_poses=1,
            min_pose_detection_confidence=self._min_detection_confidence,
        )
        self._landmarker = PoseLandmarker.create_from_options(options)

    # --- análisis ---

    def analyze(
        self,
        image_bytes: bytes,
        *,
        visibility_threshold: float = VISIBILITY_THRESHOLD,
        complete_threshold: int = 25,
        review_threshold: int = 10,
    ) -> PoseResult:
        """Detecta la pose en una imagen bytes (JPEG/PNG/WebP)."""
        self._ensure_landmarker()
        try:
            import numpy as np
            from mediapipe.tasks.python.vision.core.image import Image as MpImage
            from mediapipe.tasks.python.vision.core.image import ImageFormat as MpImageFormat
            from PIL import Image
        except ImportError as exc:  # pragma: no cover - depende del binario
            raise PoseModelError(
                "Dependencias de análisis no instaladas: numpy y mediapipe."
            ) from exc

        with Image.open(io.BytesIO(image_bytes)) as src:
            img = src.convert("RGB")
            width, height = img.size
            arr = np.array(img)
        mp_image = MpImage(image_format=MpImageFormat.SRGB, data=arr)
        result = self._landmarker.detect(mp_image)

        poses = result.pose_landmarks or []
        pose_count = len(poses)
        landmarks: list[dict[str, Any]] = []
        if pose_count:
            for index, lm in enumerate(poses[0]):
                landmarks.append(
                    {
                        "index": index,
                        "x": round(float(lm.x), 6) if lm.x is not None else None,
                        "y": round(float(lm.y), 6) if lm.y is not None else None,
                        "z": round(float(lm.z), 6) if lm.z is not None else None,
                        "visibility": (
                            round(float(lm.visibility), 6)
                            if lm.visibility is not None
                            else None
                        ),
                    }
                )
        visible_count = sum(
            1
            for lm in landmarks
            if lm["visibility"] is not None and lm["visibility"] >= visibility_threshold
        )
        if visible_count >= complete_threshold:
            quality = "good"
            flags = ["pose_complete"]
        elif visible_count >= review_threshold:
            quality = "partial"
            flags = ["pose_partial"]
        else:
            quality = "low"
            flags = ["low_visibility"]
        return PoseResult(
            landmarks=landmarks,
            visible_count=visible_count,
            total_count=len(landmarks),
            quality=quality,
            flags=flags,
            pose_count=pose_count,
            model_name=self._full_model_name,
            model_version=self.model_version or "unknown",
            model_sha256=self._model_sha256 or "unknown",
            mediapipe_version=self._mediapipe_version or "unknown",
            image_width=width,
            image_height=height,
        )
