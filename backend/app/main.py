import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import api_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import register_request_id_middleware
from app.core.rate_limit import SlidingWindowLimiter
from app.core.rate_limit_middleware import register_rate_limit
from app.core.security_errors import register_security_handlers
from app.core.security_headers import register_security_headers
from app.core.validation import register_validation_handler
from app.db.session import engine

logger = logging.getLogger(__name__)

# Métodos y cabeceras explícitos: nunca "*" con credenciales (Fase 9, D-CORS).
ALLOWED_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
ALLOWED_HEADERS = ["Authorization", "Content-Type", "X-Request-ID"]
EXPOSED_HEADERS = ["X-Request-ID", "Retry-After", "X-RateLimit-Limit", "X-RateLimit-Remaining"]


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level, json_output=settings.json_logs)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        logger.info(
            "%s v%s (%s)",
            settings.app_name,
            settings.app_version,
            settings.environment,
            extra={"environment": settings.environment},
        )
        logger.info("CORS permitido para: %s", settings.cors_origins_list)
        yield
        engine.dispose()

    docs_enabled = settings.docs_enabled
    app = FastAPI(
        title=f"{settings.app_name} API",
        version=settings.app_version,
        description=(
            "Registro de mediciones y análisis visual. **No emite diagnósticos médicos.** "
            "Toda salida de IA es una estimación visual; "
            "toda simulación es un escenario hipotético."
        ),
        docs_url="/api/docs" if docs_enabled else None,
        redoc_url="/api/redoc" if docs_enabled else None,
        openapi_url="/api/openapi.json" if docs_enabled else None,
        lifespan=lifespan,
    )

    # Orden de registro = orden inverso de ejecución: el último registrado es el
    # más externo. request-id debe ser el más externo para que todo lo demás
    # pueda correlacionarse; el rate limit, el primero que corta.
    register_rate_limit(app, settings, SlidingWindowLimiter())
    register_security_headers(app, settings)
    register_request_id_middleware(app)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=ALLOWED_METHODS,
        allow_headers=ALLOWED_HEADERS,
        expose_headers=EXPOSED_HEADERS,
    )
    register_exception_handlers(app)
    register_validation_handler(app)
    register_security_handlers(app)
    app.include_router(api_router, prefix="/api")
    return app


app = create_app()
