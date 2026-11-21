"""Emisión y verificación de JWT de acceso. El token solo identifica (claim `sub`)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt


class TokenError(Exception):
    """Token ausente, malformado, firmado con otra clave o expirado."""


@dataclass(frozen=True, slots=True)
class IssuedToken:
    value: str
    expires_in: int


class JwtTokenService:
    def __init__(self, *, secret: str, algorithm: str, issuer: str, ttl: timedelta) -> None:
        self._secret = secret
        self._algorithm = algorithm
        self._issuer = issuer
        self._ttl = ttl

    def issue(self, user_id: uuid.UUID) -> IssuedToken:
        now = datetime.now(UTC)
        payload = {
            "sub": str(user_id),
            "iss": self._issuer,
            "iat": now,
            "exp": now + self._ttl,
            "jti": uuid.uuid4().hex,
        }
        token = jwt.encode(payload, self._secret, algorithm=self._algorithm)
        return IssuedToken(value=token, expires_in=int(self._ttl.total_seconds()))

    def verify(self, token: str) -> uuid.UUID:
        try:
            claims = jwt.decode(
                token,
                self._secret,
                algorithms=[self._algorithm],
                issuer=self._issuer,
                leeway=5,
                options={"require": ["exp", "iat", "sub", "iss"]},
            )
            return uuid.UUID(claims["sub"])
        except (jwt.PyJWTError, ValueError, KeyError) as exc:
            raise TokenError("Token inválido o expirado.") from exc