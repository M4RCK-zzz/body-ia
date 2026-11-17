import logging
from abc import ABC, abstractmethod
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class HealthRepository(ABC):
    @abstractmethod
    def ping(self) -> bool: ...

class SQLAlchemyHealthRepository(HealthRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def ping(self) -> bool:
        try:
            self._session.execute(text("SELECT 1"))
            return True
        except SQLAlchemyError as exc:
            logger.warning("Health check: base de datos no disponible (%s)", type(exc).__name__)
            return False