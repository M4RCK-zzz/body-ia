from fastapi import APIRouter

from app.api.routes import (
    access,
    admin,
    analytics,
    auth,
    catalog,
    consents,
    dashboard,
    health,
    measurements,
    media,
    pose,
    profiles,
    reports,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(catalog.router)
api_router.include_router(profiles.router)
api_router.include_router(measurements.router)
api_router.include_router(auth.router)
api_router.include_router(admin.router)
api_router.include_router(access.router)
api_router.include_router(consents.router)
api_router.include_router(media.router)
api_router.include_router(media.asset_router)
api_router.include_router(pose.router)
api_router.include_router(pose.asset_router)
api_router.include_router(pose.profile_router)
api_router.include_router(analytics.router)
api_router.include_router(reports.router)
api_router.include_router(reports.asset_router)
api_router.include_router(dashboard.router)
