"""Validación y re-encoding de imágenes para la Fase 4.

- Verifica el formato real con Pillow (nunca confía en el Content-Type del cliente).
- Respeta `ImageOps.exif_transpose` antes de re-encodear para respetar la orientación.
- Re-encodea desde una copia fresca y sin metadatos: los EXIF/GPS/XMP del teléfono
  nunca llegan al disco ni a la API.
- No reescala: respeta las dimensiones del original (limitado a 8000 px por lado).
"""
from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass

from PIL import Image, ImageOps, PngImagePlugin

from app.core.errors import MediaRejectedError
from app.domain.media import MAX_SIDE_PIXELS, MediaMime

_FORMAT_TO_MIME: dict[str, str] = {
    "JPEG": MediaMime.JPEG.value,
    "PNG": MediaMime.PNG.value,
    "WEBP": MediaMime.WEBP.value,
}


@dataclass(frozen=True, slots=True)
class SanitizedMedia:
    """Imagen re-codificada, lista para guardar en storage privado."""

    mime: str
    data: bytes
    width: int
    height: int
    size_bytes: int
    checksum: str  # sha256 del archivo final


def _flatten_alpha(img: Image.Image) -> Image.Image:
    if img.mode in ("RGBA", "LA", "PA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background
    if img.mode != "RGB":
        return img.convert("RGB")
    return img


def sanitize_image(data: bytes, *, max_pixels: int) -> SanitizedMedia:
    if not isinstance(data, bytes | bytearray) or len(data) < 4:
        raise MediaRejectedError("El archivo está vacío.")

    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception as exc:
        raise MediaRejectedError("El archivo no se pudo decodificar como imagen.") from exc

    fmt = img.format
    mime = _FORMAT_TO_MIME.get(fmt or "")
    if mime is None:
        raise MediaRejectedError(
            f"Formato no soportado: {fmt or 'desconocido'}. Solo JPEG, PNG y WebP."
        )

    if getattr(img, "n_frames", 1) > 1:
        raise MediaRejectedError("Las imágenes animadas no están soportadas.")

    # Orientación EXIF ANTES de re-encodear (teléfonos: fotos en vertical).
    img = ImageOps.exif_transpose(img)
    width, height = img.size

    if width < 1 or height < 1:
        raise MediaRejectedError("El archivo no se pudo decodificar como imagen.")
    if width > MAX_SIDE_PIXELS or height > MAX_SIDE_PIXELS:
        raise MediaRejectedError(
            f"La imagen supera el tamaño máximo por lado ({MAX_SIDE_PIXELS} px)."
        )
    if width * height > max_pixels:
        raise MediaRejectedError(
            f"La imagen supera el tamaño máximo permitido ({max_pixels:,} píxeles)."
        )

    img = _flatten_alpha(img)

    buf = io.BytesIO()
    if mime == MediaMime.JPEG.value:
        img.save(buf, "JPEG", quality=85, optimize=True, progressive=True, exif=b"")
    elif mime == MediaMime.PNG.value:
        img.save(buf, "PNG", optimize=True, pnginfo=PngImagePlugin.PngInfo())
    else:  # WEBP
        img.save(buf, "WEBP", quality=85)
    raw = buf.getvalue()

    return SanitizedMedia(
        mime=mime,
        data=raw,
        width=width,
        height=height,
        size_bytes=len(raw),
        checksum=hashlib.sha256(raw).hexdigest(),
    )
