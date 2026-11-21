from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError
from app.models.access import Consent, ProfileAccess
from app.repositories.access_repository import ConsentRepository, ProfileAccessRepository


class SqlAlchemyProfileAccessRepository(ProfileAccessRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, access: ProfileAccess) -> ProfileAccess:
        self._session.add(access)
        return self.save(access)

    def save(self, access: ProfileAccess) -> ProfileAccess:
        try:
            self._session.flush()
        except IntegrityError as exc:
            raise ConflictError("El usuario ya tiene un acceso vigente a este expediente.") from exc
        return access

    def get_active(self, profile_id: UUID, user_id: UUID) -> ProfileAccess | None:
        return self._session.scalar(
            select(ProfileAccess).where(
                ProfileAccess.profile_id == profile_id,
                ProfileAccess.user_id == user_id,
                ProfileAccess.revoked_at.is_(None),
            )
        )

    def list_active(self, profile_id: UUID) -> list[ProfileAccess]:
        stmt = (
            select(ProfileAccess)
            .where(ProfileAccess.profile_id == profile_id, ProfileAccess.revoked_at.is_(None))
            .order_by(ProfileAccess.granted_at, ProfileAccess.id)
        )
        return list(self._session.scalars(stmt))


class SqlAlchemyConsentRepository(ConsentRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, consent: Consent) -> Consent:
        self._session.add(consent)
        return self.save(consent)

    def save(self, consent: Consent) -> Consent:
        try:
            self._session.flush()
        except IntegrityError as exc:
            raise ConflictError("Ya existe un consentimiento vigente para este propósito.") from exc
        return consent

    def get_active(self, profile_id: UUID, purpose: str) -> Consent | None:
        return self._session.scalar(
            select(Consent).where(
                Consent.profile_id == profile_id,
                Consent.purpose == purpose,
                Consent.revoked_at.is_(None),
            )
        )