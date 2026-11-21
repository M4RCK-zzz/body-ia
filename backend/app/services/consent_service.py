from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.core.clock import utcnow
from app.core.errors import BusinessRuleError, NotFoundError
from app.core.security_errors import ConsentRequiredError
from app.domain.access import CONSENT_DOCUMENTS, AccessLevel, ConsentPurpose
from app.domain.identity import AuditAction
from app.domain.profiles import ProfileStatus
from app.models.access import Consent
from app.models.identity import User
from app.repositories.access_repository import ConsentRepository
from app.services.access_guard import AccessGuard
from app.services.audit_service import AuditRecorder
from app.services.ports import Transaction


@dataclass(frozen=True, slots=True)
class ConsentStatus:
    purpose: ConsentPurpose
    required_version: str
    valid: bool
    current: Consent | None


class ConsentService:
    def __init__(
        self,
        guard: AccessGuard,
        consents: ConsentRepository,
        audit: AuditRecorder,
        tx: Transaction,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        self._guard = guard
        self._consents = consents
        self._audit = audit
        self._tx = tx
        self._clock = clock

    def _status(self, profile_id: UUID, purpose: ConsentPurpose) -> ConsentStatus:
        required = CONSENT_DOCUMENTS[purpose].version
        current = self._consents.get_active(profile_id, purpose.value)
        return ConsentStatus(
            purpose, required, current is not None and current.version == required, current
        )

    def statuses(self, actor: User, profile_id: UUID) -> list[ConsentStatus]:
        self._guard.require(profile_id, actor, AccessLevel.VIEWER)
        return [self._status(profile_id, p) for p in ConsentPurpose]

    def ensure_valid(
        self, profile_id: UUID, purpose: ConsentPurpose = ConsentPurpose.DATA_PROCESSING
    ) -> None:
        if not self._status(profile_id, purpose).valid:
            raise ConsentRequiredError()

    def accept(self, actor: User, profile_id: UUID, purpose: ConsentPurpose) -> Consent:
        profile, _ = self._guard.require(profile_id, actor, AccessLevel.OWNER)
        if profile.status == ProfileStatus.ARCHIVED.value:
            raise BusinessRuleError("Restaura el expediente antes de gestionar su consentimiento.")
        document = CONSENT_DOCUMENTS[purpose]
        now = self._clock()
        current = self._consents.get_active(profile_id, purpose.value)
        if current is not None and current.version == document.version:
            return current
        replaced = None
        if current is not None:
            current.revoked_at, current.revoked_by = now, actor.id
            self._consents.save(current)
            replaced = current.version
        consent = Consent(
            profile_id=profile_id,
            purpose=purpose.value,
            version=document.version,
            accepted_by=actor.id,
            accepted_at=now,
        )
        self._consents.add(consent)
        self._audit.record(
            AuditAction.CONSENT_ACCEPTED,
            actor_id=actor.id,
            resource_type="consent",
            resource_id=str(consent.id),
            profile_id=profile_id,
            detail={
                "purpose": purpose.value,
                "version": document.version,
                "replaced_version": replaced,
            },
        )
        self._tx.commit()
        return consent

    def revoke(self, actor: User, profile_id: UUID, purpose: ConsentPurpose) -> Consent:
        self._guard.require(profile_id, actor, AccessLevel.OWNER)
        current = self._consents.get_active(profile_id, purpose.value)
        if current is None:
            raise NotFoundError("No hay un consentimiento vigente para este propósito.")
        current.revoked_at, current.revoked_by = self._clock(), actor.id
        self._consents.save(current)
        self._audit.record(
            AuditAction.CONSENT_REVOKED,
            actor_id=actor.id,
            resource_type="consent",
            resource_id=str(current.id),
            profile_id=profile_id,
            detail={"purpose": purpose.value, "version": current.version},
        )
        self._tx.commit()
        return current