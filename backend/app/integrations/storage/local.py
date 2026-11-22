"""Storage local privado para la Fase 4.

- Layout `{base}/{key[:2]}/{key}` (shard de 2 caracteres).
- Escritura atómica (tmp + rename), permisos 0600.
- Claves validadas contra `STORAGE_KEY_PATTERN` (nunca path de usuario).
- Nunca sobreescribe una clave existente.
"""
from __future__ import annotations

import contextlib
import os
import uuid
from pathlib import Path

from app.domain.media import STORAGE_KEY_PATTERN


class InvalidStorageKeyError(ValueError):
    """La clave no cumple el contrato de storage privado."""


def _resolve(base: Path, key: str) -> Path:
    if not STORAGE_KEY_PATTERN.fullmatch(key):
        raise InvalidStorageKeyError("Clave de storage inválida.")
    return base / key[:2] / key


class LocalStorageBackend:
    def __init__(self, base_dir: Path) -> None:
        self._base = Path(base_dir)

    def _path(self, key: str) -> Path:
        return _resolve(self._base, key)

    def put(self, key: str, data: bytes) -> None:
        path = self._path(key)
        if path.exists():
            raise RuntimeError("La clave ya existe: no se sobrescriben archivos.")
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.parent / f".{key}.{uuid.uuid4().hex}.tmp"
        try:
            with open(tmp, "wb") as fh:
                fh.write(data)
                fh.flush()
                os.fsync(fh.fileno())
            os.chmod(tmp, 0o600)
            os.replace(tmp, path)
        finally:
            with contextlib.suppress(OSError):
                tmp.unlink(missing_ok=True)

    def get(self, key: str) -> bytes:
        path = self._path(key)
        if not path.is_file():
            raise FileNotFoundError(key)
        return path.read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def delete(self, key: str) -> None:
        with contextlib.suppress(OSError):
            self._path(key).unlink(missing_ok=True)
