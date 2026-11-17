from fastapi import APIRouter
from app.api.routes import health, catalog, measurements, profiles

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(catalog.router)
api_router.include_router(profiles.router)
api_router.include_router(measurements.router)