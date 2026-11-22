from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError
from app.domain.profiles import ProfileStatus
from app.models.access import ProfileAccess
from app.models.profile import Profile
from app.repositories.profile_repository import ProfileRepository


class SqlAlchemyProfileRepository(ProfileRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, profile_id: UUID) -> Profile | None:
        return self._session.get(Profile, profile_id)

    def get_by_display_code(self, display_code: str) -> Profile | None:
        return self._session.scalar(select(Profile).where(Profile.display_code == display_code))

    def add(self, profile: Profile) -> Profile:
        self._session.add(profile)
        return self.save(profile)

    def save(self, profile: Profile) -> Profile:
        try:
            self._session.flush()
        except IntegrityError as exc:
            raise ConflictError("Ya existe un expediente con ese código.") from exc
        return profile

    def list_accessible(
        self, *, user_id: UUID, status: ProfileStatus | None, limit: int, offset: int
    ) -> tuple[list[tuple[Profile, str]], int]:
        conditions = [ProfileAccess.user_id == user_id, ProfileAccess.revoked_at.is_(None)]
        if status is not None:
            conditions.append(Profile.status == status.value)
        base = (
            select(Profile, ProfileAccess.level)
            .join(ProfileAccess, ProfileAccess.profile_id == Profile.id)
            .where(*conditions)
        )
        total = self._session.scalar(select(func.count()).select_from(base.subquery())) or 0
        rows = self._session.execute(
            base.order_by(Profile.created_at.desc(), Profile.id).limit(limit).offset(offset)
        ).all()
        return [(profile, level) for profile, level in rows], total