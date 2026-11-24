import logging
from abc import ABC, abstractmethod

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class HealthRepository(ABC):
    @abstractmethod
    def ping(self) -> bool: ...

    @abstractmethod
    def current_revision(self) -> str | None:
        """Revisión de Alembic aplicada (`alembic_version.version_num`)."""


class SQLAlchemyHealthRepository(HealthRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def current_revision(self) -> str | None:
        try:
            return self._session.execute(
                text("SELECT version_num FROM alembic_version LIMIT 1")
            ).scalar_one_or_none()
        except SQLAlchemyError as exc:
            logger.warning("Health check: sin revisión de Alembic (%s)", type(exc).__name__)
            return None

    def ping(self) -> bool:
        try:
            self._session.execute(text("SELECT 1"))
            return True
        except SQLAlchemyError as exc:
            logger.warning("Health check: base de datos no disponible (%s)", type(exc).__name__)
            return False