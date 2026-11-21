from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.core.errors import ConflictError
from app.core.security_errors import AuthenticationError, PermissionDeniedError
from app.core.tokens import IssuedToken, TokenError
from app.domain.identity import AuditAction, RoleName
from app.models.identity import User
from app.repositories.user_repository import UserRepository
from app.services.audit_service import AuditRecorder
from app.services.auth_ports import PasswordHasher, TokenService
from app.services.ports import Transaction

_GENERIC_LOGIN_ERROR = "Credenciales inválidas o cuenta bloqueada temporalmente."


def _utcnow() -> datetime:
    return datetime.now(UTC)


def normalize_email(email: str) -> str:
    return email.strip().lower()


@dataclass(frozen=True, slots=True)
class AuthPolicy:
    allow_registration: bool = True
    max_login_attempts: int = 5
    lock_duration: timedelta = timedelta(minutes=15)


@dataclass(frozen=True, slots=True)
class LoginResult:
    user: User
    token: IssuedToken


class AuthService:
    def __init__(
        self,
        *,
        users: UserRepository,
        audit: AuditRecorder,
        tx: Transaction,
        hasher: PasswordHasher,
        tokens: TokenService,
        policy: AuthPolicy | None = None,
        clock: Callable[[], datetime] = _utcnow,
    ) -> None:
        self._users = users
        self._audit = audit
        self._tx = tx
        self._hasher = hasher
        self._tokens = tokens
        self._policy = policy or AuthPolicy()
        self._clock = clock

    def register(self, *, email: str, password: str, full_name: str) -> User:
        if not self._policy.allow_registration:
            raise PermissionDeniedError(
                "El registro de cuentas está deshabilitado.", code="registration_disabled"
            )
        normalized = normalize_email(email)
        if self._users.get_by_email(normalized) is not None:
            raise ConflictError("Ya existe una cuenta con ese correo.")
        try:
            user = self._users.create(
                email=normalized,
                password_hash=self._hasher.hash(password),
                full_name=full_name.strip(),
                role_names=[RoleName.USER.value],
            )
        except ConflictError:
            self._tx.rollback()
            raise
        self._audit.record(
            AuditAction.REGISTERED,
            actor_id=user.id,
            resource_type="user",
            resource_id=str(user.id),
        )
        self._tx.commit()
        return user

    def login(self, *, email: str, password: str) -> LoginResult:
        now = self._clock()
        user = self._users.get_by_email(normalize_email(email))

        if user is None or not user.is_active:
            self._hasher.burn()
            raise AuthenticationError(_GENERIC_LOGIN_ERROR, code="invalid_credentials")
        if user.locked_until is not None and user.locked_until > now:
            self._hasher.burn()
            raise AuthenticationError(_GENERIC_LOGIN_ERROR, code="invalid_credentials")

        if not self._hasher.verify(user.password_hash, password):
            self._register_failure(user, now)
            raise AuthenticationError(_GENERIC_LOGIN_ERROR, code="invalid_credentials")

        user.failed_login_count = 0
        user.locked_until = None
        user.last_login_at = now
        if self._hasher.needs_rehash(user.password_hash):
            user.password_hash = self._hasher.hash(password)
        self._audit.record(
            AuditAction.LOGIN, actor_id=user.id, resource_type="user", resource_id=str(user.id)
        )
        self._tx.commit()
        return LoginResult(user=user, token=self._tokens.issue(user.id))

    def _register_failure(self, user: User, now: datetime) -> None:
        user.failed_login_count += 1
        self._audit.record(
            AuditAction.LOGIN_FAILED,
            actor_id=user.id,
            resource_type="user",
            resource_id=str(user.id),
            detail={"attempt": user.failed_login_count},
        )
        if user.failed_login_count >= self._policy.max_login_attempts:
            user.locked_until = now + self._policy.lock_duration
            user.failed_login_count = 0
            self._audit.record(
                AuditAction.ACCOUNT_LOCKED,
                actor_id=user.id,
                resource_type="user",
                resource_id=str(user.id),
                detail={"until": user.locked_until.isoformat()},
            )
        self._tx.commit()

    def authenticate(self, token: str) -> User:
        try:
            user_id: uuid.UUID = self._tokens.verify(token)
        except TokenError as exc:
            raise AuthenticationError(str(exc), code="invalid_token") from exc
        user = self._users.get(user_id)
        if user is None or not user.is_active:
            raise AuthenticationError("Cuenta no disponible.", code="invalid_token")
        return user