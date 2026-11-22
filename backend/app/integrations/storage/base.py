from typing import Protocol


class StorageBackend(Protocol):
    """Backend de bytes de medios. La API y los servicios nunca tocan archivos directo."""

    def put(self, key: str, data: bytes) -> None:
        """Escribe los bytes bajo `key` (clave aleatoria del dominio de medios)."""
        ...

    def get(self, key: str) -> bytes:
        """Devuelve los bytes bajo `key`. Levanta FileNotFoundError si no existe."""
        ...

    def exists(self, key: str) -> bool:
        """True si `key` existe."""
        ...

    def delete(self, key: str) -> None:
        """Borra `key`. Idempotente y best-effort."""
        ...
