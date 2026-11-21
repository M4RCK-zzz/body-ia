from fastapi import APIRouter

from app.api.routes import access, admin, auth, catalog, consents, health, measurements, profiles

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(catalog.router)
api_router.include_router(profiles.router)
api_router.include_router(measurements.router)
api_router.include_router(auth.router)
api_router.include_router(admin.router)
api_router.include_router(access.router)
api_router.include_router(consents.router)