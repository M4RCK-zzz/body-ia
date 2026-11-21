"""Hash de contraseñas con Argon2id."""

from __future__ import annotations

from argon2 import PasswordHasher as _Argon2
from argon2.exceptions import InvalidHashError, VerificationError


class Argon2PasswordHasher:
    def __init__(self) -> None:
        self._argon2 = _Argon2()
        self._decoy = self._argon2.hash("decoy-password-that-is-never-valid")

    def hash(self, password: str) -> str:
        return self._argon2.hash(password)

    def verify(self, password_hash: str, password: str) -> bool:
        try:
            return self._argon2.verify(password_hash, password)
        except (VerificationError, InvalidHashError):
            return False

    def needs_rehash(self, password_hash: str) -> bool:
        return self._argon2.check_needs_rehash(password_hash)

    def burn(self) -> None:
        """Consume un tiempo similar al de una verificación real."""
        self.verify(self._decoy, "wrong-password")