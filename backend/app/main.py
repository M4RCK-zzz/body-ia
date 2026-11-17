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
from app.core.validation import register_validation_handler
from app.db.session import engine

logger = logging.getLogger(__name__)

def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        logger.info("%s v%s (%s)", settings.app_name, settings.app_version, settings.environment)
        logger.info("CORS permitido para: %s", settings.cors_origins_list)
        yield
        engine.dispose()

    app = FastAPI(
        title=f"{settings.app_name} API",
        version=settings.app_version,
        description=(
            "Registro de mediciones y análisis visual. **No emite diagnósticos médicos.** "
            "Toda salida de IA es una estimación visual; toda simulación es un escenario hipotético."
        ),
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    register_request_id_middleware(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
    register_exception_handlers(app)
    register_validation_handler(app)
    app.include_router(api_router, prefix="/api")
    return app

app = create_app()