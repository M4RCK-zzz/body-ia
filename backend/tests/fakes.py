from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from app.core.clock import utcnow
from app.core.errors import ConflictError
from app.domain.access import AccessLevel, ConsentPurpose
from app.domain.measurements import MeasurementType
from app.domain.media import MediaStatus
from app.domain.metrics import default_catalog
from app.domain.pose import PoseAnalysisStatus
from app.domain.profiles import ProfileStatus
from app.models.access import Consent, ProfileAccess
from app.models.identity import User
from app.models.measurement import Measurement
from app.models.media import MediaAsset
from app.models.pose import PoseAnalysis
from app.models.profile import Profile
from app.repositories.access_repository import ConsentRepository, ProfileAccessRepository
from app.repositories.measurement_repository import MeasurementRepository
from app.repositories.media_repository import MediaRepository
from app.repositories.pose_repository import PoseRepository
from app.repositories.profile_repository import ProfileRepository
from app.services.access_guard import AccessGuard
from app.services.audit_service import AuditRecorder
from app.services.consent_service import ConsentService
from app.services.measurement_service import MeasurementService
from app.services.media_service import MediaService
from app.services.pose_service import PoseService
from app.services.profile_access_service import ProfileAccessService
from app.services.profile_service import ProfileService
from tests.identity_fakes import FakeTransaction, InMemoryAuditRepository, InMemoryUserRepository

__all__ = [
    "FakeTransaction",
    "FakeStorageBackend",
    "InMemoryMediaRepository",
    "InMemoryPoseRepository",
    "Services",
    "build_services",
]


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


class FakeStorageBackend:
    """Storage en memoria para tests: convenciones idénticas a LocalStorageBackend."""

    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}
        self.calls: list[tuple[str, str]] = []

    def put(self, key: str, data: bytes) -> None:
        self.calls.append(("put", key))
        if key in self.files:
            raise RuntimeError("la clave ya existe")
        self.files[key] = bytes(data)

    def get(self, key: str) -> bytes:
        self.calls.append(("get", key))
        data = self.files.get(key)
        if data is None:
            raise FileNotFoundError(key)
        return data

    def exists(self, key: str) -> bool:
        self.calls.append(("exists", key))
        return key in self.files

    def delete(self, key: str) -> None:
        self.calls.append(("delete", key))
        self.files.pop(key, None)


class InMemoryMediaRepository(MediaRepository):
    def __init__(self) -> None:
        self.items: list[MediaAsset] = []

    def get(self, asset_id: UUID) -> MediaAsset | None:
        return next((a for a in self.items if a.id == asset_id), None)

    def add(self, asset: MediaAsset) -> MediaAsset:
        asset.id = asset.id or uuid4()
        asset.uploaded_at = asset.uploaded_at or utcnow()
        self.items.append(asset)
        return asset

    def save(self, asset: MediaAsset) -> MediaAsset:
        return asset

    def list_page(
        self,
        *,
        profile_id: UUID,
        status: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[MediaAsset], int]:
        rows = [a for a in self.items if a.profile_id == profile_id]
        if status is not None:
            rows = [a for a in rows if a.status == status]
        else:
            rows = [a for a in rows if a.status != MediaStatus.DELETED.value]
        rows.sort(key=lambda a: (a.uploaded_at, a.id), reverse=True)
        return rows[offset : offset + limit], len(rows)


class InMemoryPoseRepository(PoseRepository):
    def __init__(self) -> None:
        self.items: list[PoseAnalysis] = []

    def get(self, analysis_id: UUID) -> PoseAnalysis | None:
        return next((a for a in self.items if a.id == analysis_id), None)

    def add(self, analysis: PoseAnalysis) -> PoseAnalysis:
        analysis.id = analysis.id or uuid4()
        analysis.created_at = analysis.created_at or utcnow()
        self.items.append(analysis)
        return analysis

    def save(self, analysis: PoseAnalysis) -> PoseAnalysis:
        return analysis

    def find_active_for_asset(self, asset_id: UUID) -> PoseAnalysis | None:
        return next(
            (
                a
                for a in self.items
                if a.media_asset_id == asset_id
                and a.status in (
                    PoseAnalysisStatus.QUEUED.value,
                    PoseAnalysisStatus.PROCESSING.value,
                )
            ),
            None,
        )

    def list_page(
        self,
        *,
        profile_id: UUID,
        status: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[PoseAnalysis], int]:
        rows = [a for a in self.items if a.profile_id == profile_id]
        if status is not None:
            rows = [a for a in rows if a.status == status]
        rows.sort(key=lambda a: (a.created_at, a.id), reverse=True)
        return rows[offset : offset + limit], len(rows)

    def list_page_by_asset(
        self,
        *,
        media_asset_id: UUID,
        status: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[PoseAnalysis], int]:
        rows = [a for a in self.items if a.media_asset_id == media_asset_id]
        if status is not None:
            rows = [a for a in rows if a.status == status]
        rows.sort(key=lambda a: (a.created_at, a.id), reverse=True)
        return rows[offset : offset + limit], len(rows)

    def claim_next(self) -> PoseAnalysis | None:
        rows = [
            a
            for a in self.items
            if a.status == PoseAnalysisStatus.QUEUED.value
        ]
        rows.sort(key=lambda a: (a.created_at, a.id))
        return rows[0] if rows else None

    def mark_stale_failed(self, stale_before, *, now, reason: str) -> int:
        count = 0
        for a in self.items:
            if (
                a.status == PoseAnalysisStatus.PROCESSING.value
                and a.started_at is not None
                and a.started_at <= stale_before
            ):
                a.status = PoseAnalysisStatus.FAILED.value
                a.error_message = reason[:300]
                a.completed_at = now
                count += 1
        return count


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
    media_repo: InMemoryMediaRepository
    pose_repo: InMemoryPoseRepository
    storage: FakeStorageBackend
    tx: FakeTransaction
    clock: object
    guard: AccessGuard
    consent: ConsentService
    access_service: ProfileAccessService
    profiles: ProfileService
    measurements: MeasurementService
    media: MediaService
    pose: PoseService

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
    media_repo = InMemoryMediaRepository()
    pose_repo = InMemoryPoseRepository()
    storage = FakeStorageBackend()
    guard = AccessGuard(profiles_repo, access_repo, audit, tx)
    consent = ConsentService(guard, consents_repo, audit, tx, clock=clock)
    return Services(
        users=users,
        audit_repo=audit_repo,
        access_repo=access_repo,
        consents_repo=consents_repo,
        profiles_repo=profiles_repo,
        measurements_repo=measurements_repo,
        media_repo=media_repo,
        pose_repo=pose_repo,
        storage=storage,
        tx=tx,
        clock=clock,
        guard=guard,
        consent=consent,
        access_service=ProfileAccessService(guard, access_repo, users, audit, tx, clock=clock),
        profiles=ProfileService(profiles_repo, access_repo, guard, audit, tx, clock=clock),
        measurements=MeasurementService(
            guard, measurements_repo, default_catalog(), consent, audit, tx, clock=clock
        ),
        pose=PoseService(
            guard,
            media_repo,
            pose_repo,
            consent,
            audit,
            tx,
            clock=clock,
        ),
        media=MediaService(
            guard,
            media_repo,
            storage,
            consent,
            audit,
            tx,
            clock=clock,
            max_upload_bytes=10 * 1024 * 1024,
            max_pixels=25_000_000,
            retention_days=365,
        ),
    )