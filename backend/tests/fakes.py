from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from app.core.clock import utcnow
from app.core.errors import ConflictError
from app.domain.access import AccessLevel, ConsentPurpose
from app.domain.measurements import MeasurementType
from app.domain.metrics import default_catalog
from app.domain.profiles import ProfileStatus
from app.models.access import Consent, ProfileAccess
from app.models.identity import User
from app.models.measurement import Measurement
from app.models.profile import Profile
from app.repositories.access_repository import ConsentRepository, ProfileAccessRepository
from app.repositories.measurement_repository import MeasurementRepository
from app.repositories.profile_repository import ProfileRepository
from app.services.access_guard import AccessGuard
from app.services.audit_service import AuditRecorder
from app.services.consent_service import ConsentService
from app.services.measurement_service import MeasurementService
from app.services.profile_access_service import ProfileAccessService
from app.services.profile_service import ProfileService
from tests.identity_fakes import FakeTransaction, InMemoryAuditRepository, InMemoryUserRepository

__all__ = ["FakeTransaction", "Services", "build_services"]


def _val(x):
    return getattr(x, "value", x)


class InMemoryProfileAccessRepository(ProfileAccessRepository):
    def __init__(self, users: InMemoryUserRepository | None = None) -> None:
        self.items: list[ProfileAccess] = []
        self._users = users

    def _attach(self, access: ProfileAccess) -> ProfileAccess:
        if self._users is not None:
            user = self._users.get(access.user_id)
            if user is not None:
                access.user = user
        return access

    def add(self, access: ProfileAccess) -> ProfileAccess:
        # Imita los índices únicos parciales de la migración 0004.
        if self.get_active(access.profile_id, access.user_id) is not None:
            raise ConflictError("El usuario ya tiene acceso a este expediente.")
        if _val(access.level) == "owner" and any(
            a.profile_id == access.profile_id
            and _val(a.level) == "owner"
            and a.revoked_at is None
            for a in self.items
        ):
            raise ConflictError("El expediente ya tiene propietario.")
        access.id = access.id or uuid4()
        access.granted_at = access.granted_at or utcnow()
        self.items.append(access)
        return self._attach(access)

    def save(self, access: ProfileAccess) -> ProfileAccess:
        return access

    def get_active(self, profile_id: UUID, user_id: UUID) -> ProfileAccess | None:
        found = next(
            (
                a
                for a in self.items
                if a.profile_id == profile_id and a.user_id == user_id and a.revoked_at is None
            ),
            None,
        )
        return self._attach(found) if found else None

    def list_active(self, profile_id: UUID) -> list[ProfileAccess]:
        rows = [a for a in self.items if a.profile_id == profile_id and a.revoked_at is None]
        return [self._attach(a) for a in rows]


class InMemoryConsentRepository(ConsentRepository):
    def __init__(self) -> None:
        self.items: list[Consent] = []

    def add(self, consent: Consent) -> Consent:
        if self.get_active(consent.profile_id, consent.purpose) is not None:
            raise ConflictError("Ya existe un consentimiento vigente.")
        consent.id = consent.id or uuid4()
        self.items.append(consent)
        return consent

    def save(self, consent: Consent) -> Consent:
        return consent

    def get_active(self, profile_id: UUID, purpose: str) -> Consent | None:
        return next(
            (
                c
                for c in self.items
                if c.profile_id == profile_id
                and _val(c.purpose) == _val(purpose)
                and c.revoked_at is None
            ),
            None,
        )


class InMemoryProfileRepository(ProfileRepository):
    def __init__(self, access: InMemoryProfileAccessRepository) -> None:
        self.items: dict[UUID, Profile] = {}
        self._access = access

    def get(self, profile_id: UUID) -> Profile | None:
        return self.items.get(profile_id)

    def get_by_display_code(self, display_code: str) -> Profile | None:
        return next((p for p in self.items.values() if p.display_code == display_code), None)

    def add(self, profile: Profile) -> Profile:
        now = utcnow()
        profile.id = profile.id or uuid4()
        profile.created_at = now
        profile.updated_at = now
        self.items[profile.id] = profile
        return profile

    def save(self, profile: Profile) -> Profile:
        return profile

    def list_accessible(
        self, *, user_id: UUID, status: ProfileStatus | None, limit: int, offset: int
    ) -> tuple[list[tuple[Profile, str]], int]:
        rows: list[tuple[Profile, str]] = []
        for a in self._access.items:
            if a.user_id != user_id or a.revoked_at is not None:
                continue
            p = self.items.get(a.profile_id)
            if p is None or (status is not None and p.status != status.value):
                continue
            rows.append((p, _val(a.level)))
        rows.sort(key=lambda r: r[0].created_at, reverse=True)
        return rows[offset : offset + limit], len(rows)


class InMemoryMeasurementRepository(MeasurementRepository):
    def __init__(self) -> None:
        self.items: list[Measurement] = []

    def get(self, measurement_id: UUID, profile_id: UUID) -> Measurement | None:
        return next(
            (m for m in self.items if m.id == measurement_id and m.profile_id == profile_id), None
        )

    def add(self, measurement: Measurement) -> Measurement:
        if measurement.supersedes_id is not None and self.is_superseded(measurement.supersedes_id):
            raise ConflictError("La medición ya fue corregida por otra operación.")
        measurement.id = uuid4()
        measurement.recorded_at = utcnow()
        self.items.append(measurement)
        return measurement

    def is_superseded(self, measurement_id: UUID) -> bool:
        return any(m.supersedes_id == measurement_id for m in self.items)

    def superseded_among(self, measurement_ids: Iterable[UUID]) -> set[UUID]:
        wanted = set(measurement_ids)
        return {m.supersedes_id for m in self.items if m.supersedes_id in wanted}

    def list_page(
        self,
        *,
        profile_id: UUID,
        metric_type: MeasurementType | None,
        only_current: bool,
        date_from: datetime | None,
        date_to: datetime | None,
        ascending: bool,
        limit: int,
        offset: int,
    ) -> tuple[list[Measurement], int]:
        rows = [m for m in self.items if m.profile_id == profile_id]
        if metric_type is not None:
            rows = [m for m in rows if m.metric_type == metric_type.value]
        if only_current:
            rows = [m for m in rows if not self.is_superseded(m.id)]
        if date_from is not None:
            rows = [m for m in rows if m.measured_at >= date_from]
        if date_to is not None:
            rows = [m for m in rows if m.measured_at <= date_to]
        rows.sort(key=lambda m: (m.measured_at, m.recorded_at), reverse=not ascending)
        return rows[offset : offset + limit], len(rows)

    def get_chain(self, measurement_id: UUID, profile_id: UUID) -> list[Measurement]:
        node = self.get(measurement_id, profile_id)
        if node is None:
            return []
        chain = [node]
        while chain[0].supersedes_id is not None:
            previous = self.get(chain[0].supersedes_id, profile_id)
            if previous is None:
                break
            chain.insert(0, previous)
        while True:
            following = next((m for m in self.items if m.supersedes_id == chain[-1].id), None)
            if following is None:
                break
            chain.append(following)
        return chain


@dataclass
class Services:
    users: InMemoryUserRepository
    audit_repo: InMemoryAuditRepository
    access_repo: InMemoryProfileAccessRepository
    consents_repo: InMemoryConsentRepository
    profiles_repo: InMemoryProfileRepository
    measurements_repo: InMemoryMeasurementRepository
    tx: FakeTransaction
    clock: object
    guard: AccessGuard
    consent: ConsentService
    access_service: ProfileAccessService
    profiles: ProfileService
    measurements: MeasurementService

    # --- ayudas para los tests ---
    def new_user(self, name: str, role: str = "user") -> User:
        return self.users.create(
            email=f"{name}@example.com",
            password_hash="x",
            full_name=name.title(),
            role_names=[role],
        )

    def profile_for(self, owner: User, code: str = "BV-001") -> UUID:
        view = self.profiles.create(owner, code)
        return getattr(view, "profile", view).id

    def grant_direct(self, profile_id: UUID, user: User, level: AccessLevel | str) -> ProfileAccess:
        """Concede acceso saltando el servicio (para preparar escenarios)."""
        return self.access_repo.add(
            ProfileAccess(
                profile_id=profile_id,
                user_id=user.id,
                level=_val(level),
                granted_by=user.id,
                granted_at=utcnow(),
            )
        )

    def accept_consent(self, owner: User, profile_id: UUID) -> None:
        self.consent.accept(owner, profile_id, ConsentPurpose.DATA_PROCESSING)


def build_services(clock=utcnow) -> Services:
    users = InMemoryUserRepository()
    audit_repo = InMemoryAuditRepository()
    audit = AuditRecorder(audit_repo, clock=clock)
    tx = FakeTransaction()
    access_repo = InMemoryProfileAccessRepository(users)
    consents_repo = InMemoryConsentRepository()
    profiles_repo = InMemoryProfileRepository(access_repo)
    measurements_repo = InMemoryMeasurementRepository()
    guard = AccessGuard(profiles_repo, access_repo, audit, tx)
    consent = ConsentService(guard, consents_repo, audit, tx, clock=clock)
    return Services(
        users=users,
        audit_repo=audit_repo,
        access_repo=access_repo,
        consents_repo=consents_repo,
        profiles_repo=profiles_repo,
        measurements_repo=measurements_repo,
        tx=tx,
        clock=clock,
        guard=guard,
        consent=consent,
        access_service=ProfileAccessService(guard, access_repo, users, audit, tx, clock=clock),
        profiles=ProfileService(profiles_repo, access_repo, guard, audit, tx, clock=clock),
        measurements=MeasurementService(
            guard, measurements_repo, default_catalog(), consent, audit, tx, clock=clock
        ),
    )