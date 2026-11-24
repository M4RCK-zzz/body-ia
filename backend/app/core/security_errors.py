"""Errores de identidad (401), permisos (403) y consentimiento (422).

Todos con el mismo formato de cuerpo: `{"error": {"code": ..., "message": ...}}`.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AuthenticationError(Exception):
    """No se pudo establecer la identidad del solicitante (HTTP 401)."""

    def __init__(
        self, message: str = "Autenticación requerida.", code: str = "unauthenticated"
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code


class PermissionDeniedError(Exception):
    """Identidad conocida, pero sin permiso para la acción (HTTP 403)."""

    def __init__(
        self,
        message: str = "No tienes permisos para realizar esta acción.",
        code: str = "forbidden",
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code


class ConsentRequiredError(Exception):
    """Falta consentimiento vigente para escribir datos (HTTP 422)."""

    def __init__(self) -> None:
        super().__init__("consent_required")
        self.code = "consent_required"
        self.message = (
            "Se requiere un consentimiento vigente de tratamiento de datos para registrar o "
            "corregir mediciones. El propietario del expediente debe aceptarlo."
        )


def register_security_handlers(app: FastAPI) -> None:
    @app.exception_handler(AuthenticationError)
    async def _authentication_error(_: Request, exc: AuthenticationError) -> JSONResponse:
        return JSONResponse(
            status_code=401,
            content={"error": {"code": exc.code, "message": exc.message}},
            headers={"WWW-Authenticate": "Bearer"},
        )

    @app.exception_handler(PermissionDeniedError)
    async def _permission_denied(_: Request, exc: PermissionDeniedError) -> JSONResponse:
        return JSONResponse(
            status_code=403,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(ConsentRequiredError)
    async def _consent_required(_: Request, exc: ConsentRequiredError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"error": {"code": exc.code, "message": exc.message}},
        )