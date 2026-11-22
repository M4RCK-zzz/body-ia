"""Captura segura (Fase 4): estados, MIME canónicos y claves privadas."""
from __future__ import annotations

import re
from enum import StrEnum
from uuid import uuid4


class MediaStatus(StrEnum):
    UPLOADED = "uploaded"
    VALIDATING = "validating"
    READY = "ready"
    REJECTED = "rejected"
    DELETED = "deleted"


class MediaMime(StrEnum):
    JPEG = "image/jpeg"
    PNG = "image/png"
    WEBP = "image/webp"


MIME_TO_EXTENSION: dict[str, str] = {
    MediaMime.JPEG.value: ".jpg",
    MediaMime.PNG.value: ".png",
    MediaMime.WEBP.value: ".webp",
}

STORAGE_KEY_PATTERN = re.compile(r"^[0-9a-f-]{36}\.(jpg|png|webp)$")

MAX_STORAGE_KEY_LENGTH = 96
MAX_SIDE_PIXELS = 8000


def allowed_mime_types() -> tuple[str, ...]:
    return tuple(MIME_TO_EXTENSION)


def canonical_extension(mime: str) -> str | None:
    return MIME_TO_EXTENSION.get(mime)


def new_storage_key(mime: str) -> str:
    """Clave aleatoria del archivo. Nunca derivada del nombre original."""
    extension = canonical_extension(mime)
    if extension is None:
        raise ValueError(f"MIME no soportado: {mime}")
    return f"{uuid4()}{extension}"


def is_valid_storage_key(key: str) -> bool:
    return STORAGE_KEY_PATTERN.fullmatch(key) is not None
