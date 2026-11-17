from functools import lru_cache
from fastapi import Depends
from sqlalchemy.orm import Session
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.db.transaction import SessionTransaction
from app.domain.metrics import MetricCatalog, default_catalog
from app.repositories.health import HealthRepository, SQLAlchemyHealthRepository
from app.repositories.sqlalchemy_measurement_repository import SqlAlchemyMeasurementRepository
from app.repositories.sqlalchemy_profile_repository import SqlAlchemyProfileRepository
from app.services.health_service import HealthService
from app.services.measurement_service import MeasurementService
from app.services.profile_service import ProfileService

def get_health_repository(db: Session = Depends(get_db)) -> HealthRepository:
    return SQLAlchemyHealthRepository(db)

def get_health_service(
    repository: HealthRepository = Depends(get_health_repository),
    settings: Settings = Depends(get_settings),
) -> HealthService:
    return HealthService(repository, settings)

@lru_cache
def _metric_catalog() -> MetricCatalog:
    return default_catalog()

def get_metric_catalog() -> MetricCatalog:
    return _metric_catalog()

def get_profile_service(db: Session = Depends(get_db)) -> ProfileService:
    return ProfileService(SqlAlchemyProfileRepository(db), SessionTransaction(db))

def get_measurement_service(
    db: Session = Depends(get_db), catalog: MetricCatalog = Depends(get_metric_catalog)
) -> MeasurementService:
    return MeasurementService(
        SqlAlchemyProfileRepository(db),
        SqlAlchemyMeasurementRepository(db),
        catalog,
        SessionTransaction(db),
    )