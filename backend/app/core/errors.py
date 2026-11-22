from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    status_code: int = 400
    code: str = "app_error"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        if code:
            self.code = code

class NotFoundError(AppError):
    status_code = 404
    code = "not_found"

class ConflictError(AppError):
    status_code = 409
    code = "conflict"

class BusinessRuleError(AppError):
    status_code = 422
    code = "business_rule_violation"

class MediaRejectedError(AppError):
    """Contenido de la imagen rechazado (422). No se persiste el archivo."""

    status_code = 422
    code = "media_rejected"

class FileTooLargeError(AppError):
    """El archivo crudo supera MAX_UPLOAD_MB antes de cualquier escritura (413)."""

    status_code = 413
    code = "file_too_large"

class UnsupportedMediaTypeError(AppError):
    """Tipo MIME no soportado (415)."""

    status_code = 415
    code = "unsupported_media_type"


def cors_headers_for_origin(origin: str | None, allowed_origins: list[str]) -> dict[str, str]:
    """Cabeceras CORS para respuestas que salen por ServerErrorMiddleware.

    El middleware CORS normal solo agrega cabeceras cuando la respuesta pasa por
    su `send`; una excepción no controlada (p. ej. un error de base de datos) la
    propaga hasta ServerErrorMiddleware y la respuesta NO conserva
    `Access-Control-Allow-Origin`. Esta función refleja la misma política
    (origen permitido + credenciales) para ese camino.
    """
    if not origin:
        return {}
    if origin in allowed_origins:
        return {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
            "Vary": "Origin",
        }
    return {}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(Exception)
    async def handle_unhandled_error(request: Request, exc: Exception) -> JSONResponse:
        # Cualquier excepción no controlada (p. ej. error de BD) produce 500.
        # Se reflejan las mismas reglas de CORS del middleware para que el
        # navegador muestre el error real en lugar de un bloque CORS opaco.
        from app.core.config import get_settings

        origin = request.headers.get("origin")
        response = JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "Error interno del servidor.",
                }
            },
        )
        for key, value in cors_headers_for_origin(origin, get_settings().cors_origins_list).items():
            response.headers[key] = value
        return response
