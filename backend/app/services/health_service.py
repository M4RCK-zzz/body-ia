from datetime import UTC, datetime
from app.core.config import Settings
from app.repositories.health import HealthRepository
from app.schemas.health import HealthResponse

class HealthService:
    def __init__(self, repository: HealthRepository, settings: Settings) -> None:
        self._repository = repository
        self._settings = settings

    def check(self) -> HealthResponse:
        database_up = self._repository.ping()
        return HealthResponse(
            status="ok" if database_up else "degraded",
            service=self._settings.app_name,
            version=self._settings.app_version,
            environment=self._settings.environment,
            database="up" if database_up else "down",
            timestamp=datetime.now(UTC),
        )