from __future__ import annotations

import io

import pytest
from PIL import Image

from app.core.errors import MediaRejectedError
from app.services.media_validation import sanitize_image


def _jpeg_with_exif(width: int = 32, height: int = 32, *, make_exif: bool = True) -> bytes:
    img = Image.new("RGB", (width, height), (200, 30, 30))
    out = io.BytesIO()
    if make_exif:
        exif = Image.Exif()
        exif[0x010F] = "PhoneCam"          # Make
        exif[0x0110] = "SX-1"              # Model
        exif[0x0132] = "2026:11:22 10:00:00"  # DateTime
        img.save(out, "JPEG", exif=exif)
    else:
        img.save(out, "JPEG")
    return out.getvalue()


def _png() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (32, 16), (10, 20, 30)).save(out, "PNG")
    return out.getvalue()


def _webp() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (24, 24), (0, 200, 100)).save(out, "WEBP")
    return out.getvalue()


def test_rejects_garbage_bytes():
    with pytest.raises(MediaRejectedError):
        sanitize_image(b"not an image", max_pixels=1000)


def test_rejects_empty_bytes():
    with pytest.raises(MediaRejectedError):
        sanitize_image(b"", max_pixels=1000)


def test_rejects_non_supported_format():
    out = io.BytesIO()
    Image.new("RGB", (16, 16), (1, 2, 3)).save(out, "BMP")
    with pytest.raises(MediaRejectedError, match="Formato no soportado"):
        sanitize_image(out.getvalue(), max_pixels=1000)


def test_rejects_gif_even_single_frame():
    out = io.BytesIO()
    Image.new("RGB", (16, 16), (1, 2, 3)).save(out, "GIF")
    with pytest.raises(MediaRejectedError, match="Formato no soportado"):
        sanitize_image(out.getvalue(), max_pixels=1000)


def test_rejects_too_many_pixels():
    data = _jpeg_with_exif(width=100, height=100)
    with pytest.raises(MediaRejectedError, match="tamaño máximo"):
        sanitize_image(data, max_pixels=9_000)  # 10000 > 9000


def test_rejects_animated_gif_by_format_gate():
    # Las animadas son rechazadas por el gate de formato (GIF no está en el allowlist).
    img = Image.new("P", (16, 16))
    out = io.BytesIO()
    img.save(out, "GIF", save_all=True, append_images=[img.copy()], duration=100, loop=0)
    with pytest.raises(MediaRejectedError, match="Formato no soportado"):
        sanitize_image(out.getvalue(), max_pixels=100_000)


def test_jpeg_re_encode_strips_exif():
    raw_with_exif = _jpeg_with_exif()
    assert b"\xff\xe1" in raw_with_exif  # origen trae EXIF
    result = sanitize_image(raw_with_exif, max_pixels=1_000_000)
    assert b"\xff\xe1" not in result.data  # final: sin EXIF
    assert b"PhoneCam" not in result.data
    assert b"SX-1" not in result.data
    assert result.mime == "image/jpeg"
    assert result.width == 32 and result.height == 32
    assert result.checksum == __import__("hashlib").sha256(result.data).hexdigest()


def test_png_re_encode_strips_text_metadata():
    from PIL import PngImagePlugin

    info = PngImagePlugin.PngInfo()
    info.add_text("Comment", "secret-metadata-do-not-leak")
    src = Image.new("RGB", (16, 16), (1, 2, 3))
    buf = io.BytesIO()
    src.save(buf, "PNG", pnginfo=info)
    result = sanitize_image(buf.getvalue(), max_pixels=1_000_000)
    assert b"secret-metadata-do-not-leak" not in result.data
    assert result.mime == "image/png"


def test_webp_re_encode_has_no_exif():
    out = io.BytesIO()
    img = Image.new("RGB", (16, 16), (1, 2, 3))
    exif = Image.Exif()
    exif[0x010F] = "PhoneCam"
    img.save(out, "WEBP", exif=exif)
    result = sanitize_image(out.getvalue(), max_pixels=1_000_000)
    assert b"PhoneCam" not in result.data
    assert result.mime == "image/webp"


def test_exif_orientation_is_applied_before_re_encode():
    # Foto vertical desde un celular: banda EXIF 6 = rotación 90° CW
    img = Image.new("RGB", (120, 80), (50, 100, 200))  # 120x80 (ancho x alto)
    exif = Image.Exif()
    exif[0x0112] = 6  # Orientation
    out = io.BytesIO()
    img.save(out, "JPEG", exif=exif)
    result = sanitize_image(out.getvalue(), max_pixels=1_000_000)
    # Después de rotar a orientacion vertical: 80 x 120
    assert (result.width, result.height) == (80, 120)


def test_flatten_alpha_onto_white_background():
    img = Image.new("RGBA", (8, 8), (255, 0, 0, 0))  # totalmente transparente
    buf = io.BytesIO()
    img.save(buf, "PNG")
    result = sanitize_image(buf.getvalue(), max_pixels=1_000_000)
    # Composición sobre blanco: el rojo opaco transparente → blanco
    check = Image.open(io.BytesIO(result.data))
    assert check.mode == "RGB"
    # Pixel central debe ser blanco (fondo)
    assert check.getpixel((4, 4)) == (255, 255, 255)
