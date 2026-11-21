from datetime import timedelta
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.passwords import Argon2PasswordHasher
from app.core.tokens import JwtTokenService
from app.db.session import get_db
from app.db.transaction import SessionTransaction
from app.domain.metrics import MetricCatalog, default_catalog
from app.repositories.health import HealthRepository, SQLAlchemyHealthRepository
from app.repositories.sqlalchemy_access_repository import (
    SqlAlchemyConsentRepository,
    SqlAlchemyProfileAccessRepository,
)
from app.repositories.sqlalchemy_audit_repository import SqlAlchemyAuditRepository
from app.repositories.sqlalchemy_measurement_repository import SqlAlchemyMeasurementRepository
from app.repositories.sqlalchemy_profile_repository import SqlAlchemyProfileRepository
from app.repositories.sqlalchemy_user_repository import SqlAlchemyUserRepository
from app.services.access_guard import AccessGuard
from app.services.audit_service import AuditRecorder
from app.services.auth_service import AuthPolicy, AuthService
from app.services.consent_service import ConsentService
from app.services.health_service import HealthService
from app.services.measurement_service import MeasurementService
from app.services.profile_access_service import ProfileAccessService
from app.services.profile_service import ProfileService
from app.services.user_admin_service import UserAdminService


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


def _audit(db: Session) -> AuditRecorder:
    return AuditRecorder(SqlAlchemyAuditRepository(db))


def get_access_guard(db: Session = Depends(get_db)) -> AccessGuard:
    return AccessGuard(
        SqlAlchemyProfileRepository(db),
        SqlAlchemyProfileAccessRepository(db),
        _audit(db),
        SessionTransaction(db),
    )


def get_consent_service(db: Session = Depends(get_db)) -> ConsentService:
    return ConsentService(
        get_access_guard(db), SqlAlchemyConsentRepository(db), _audit(db), SessionTransaction(db)
    )


def get_profile_access_service(db: Session = Depends(get_db)) -> ProfileAccessService:
    return ProfileAccessService(
        get_access_guard(db),
        SqlAlchemyProfileAccessRepository(db),
        SqlAlchemyUserRepository(db),
        _audit(db),
        SessionTransaction(db),
    )


def get_profile_service(db: Session = Depends(get_db)) -> ProfileService:
    return ProfileService(
        SqlAlchemyProfileRepository(db),
        SqlAlchemyProfileAccessRepository(db),
        get_access_guard(db),
        _audit(db),
        SessionTransaction(db),
    )


def get_measurement_service(
    db: Session = Depends(get_db), catalog: MetricCatalog = Depends(get_metric_catalog)
) -> MeasurementService:
    return MeasurementService(
        get_access_guard(db),
        SqlAlchemyMeasurementRepository(db),
        catalog,
        get_consent_service(db),
        _audit(db),
        SessionTransaction(db),
    )


@lru_cache
def _password_hasher() -> Argon2PasswordHasher:
    return Argon2PasswordHasher()


@lru_cache
def _token_service() -> JwtTokenService:
    settings = get_settings()
    return JwtTokenService(
        secret=settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
        issuer=settings.jwt_issuer,
        ttl=timedelta(minutes=settings.access_token_minutes),
    )


def get_auth_service(db: Annotated[Session, Depends(get_db)]) -> AuthService:
    settings = get_settings()
    return AuthService(
        users=SqlAlchemyUserRepository(db),
        audit=AuditRecorder(SqlAlchemyAuditRepository(db)),
        tx=SessionTransaction(db),
        hasher=_password_hasher(),
        tokens=_token_service(),
        policy=AuthPolicy(
            allow_registration=settings.allow_registration,
            max_login_attempts=settings.login_max_attempts,
            lock_duration=timedelta(minutes=settings.login_lock_minutes),
        ),
    )


def get_user_admin_service(db: Annotated[Session, Depends(get_db)]) -> UserAdminService:
    audit_repository = SqlAlchemyAuditRepository(db)
    return UserAdminService(
        users=SqlAlchemyUserRepository(db),
        audit_repository=audit_repository,
        audit=AuditRecorder(audit_repository),
        tx=SessionTransaction(db),
    )