from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.core.errors import ConflictError
from app.core.tokens import JwtTokenService
from app.models.audit_event import AuditEvent
from app.models.identity import Role, User
from app.repositories.audit_repository import AuditRepository
from app.repositories.user_repository import UserRepository
from app.services.audit_service import AuditRecorder
from app.services.auth_service import AuthPolicy, AuthService
from app.services.user_admin_service import UserAdminService


class FakeTransaction:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class FastHasher:
    def hash(self, password: str) -> str:
        return f"h:{password}"

    def verify(self, password_hash: str, password: str) -> bool:
        return password_hash == f"h:{password}"

    def needs_rehash(self, password_hash: str) -> bool:
        return False

    def burn(self) -> None:
        return None


class FakeClock:
    def __init__(self) -> None:
        self.now = datetime(2025, 1, 1, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs: float) -> None:
        self.now += timedelta(**kwargs)


class InMemoryUserRepository(UserRepository):
    def __init__(self) -> None:
        self.items: dict[uuid.UUID, User] = {}

    def create(
        self, *, email: str, password_hash: str, full_name: str, role_names: Sequence[str]
    ) -> User:
        if any(u.email == email for u in self.items.values()):
            raise ConflictError("Ya existe una cuenta con ese correo.")
        user = User(
            id=uuid.uuid4(),
            email=email,
            password_hash=password_hash,
            full_name=full_name,
            is_active=True,
            failed_login_count=0,
            roles=[Role(name=n, description="") for n in sorted(set(role_names))],
        )
        user.created_at = datetime.now(UTC)
        self.items[user.id] = user
        return user

    def get(self, user_id: uuid.UUID) -> User | None:
        return self.items.get(user_id)

    def get_by_email(self, email: str) -> User | None:
        return next((u for u in self.items.values() if u.email == email), None)

    def get_many(self, user_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, User]:
        return {uid: self.items[uid] for uid in set(user_ids) if uid in self.items}

    def set_roles(self, user: User, role_names: Sequence[str]) -> None:
        user.roles = [Role(name=n, description="") for n in sorted(set(role_names))]

    def list_page(
        self,
        *,
        limit: int,
        offset: int,
        search: str | None = None,
        role: str | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[User], int]:
        rows = list(self.items.values())
        if search:
            needle = search.casefold()
            rows = [
                u
                for u in rows
                if needle in u.full_name.casefold() or needle in u.email.casefold()
            ]
        if role is not None:
            rows = [u for u in rows if role in u.role_names]
        if is_active is not None:
            rows = [u for u in rows if u.is_active is is_active]
        ordered = sorted(rows, key=lambda u: u.created_at, reverse=True)
        return ordered[offset : offset + limit], len(ordered)


class InMemoryAuditRepository(AuditRepository):
    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    def add(self, event: AuditEvent) -> None:
        self.events.append(event)

    def list_page(
        self,
        *,
        limit: int,
        offset: int,
        action: str | None = None,
        actor_user_id: uuid.UUID | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> tuple[list[AuditEvent], int]:
        items = [
            e
            for e in reversed(self.events)
            if (action is None or e.action == action)
            and (actor_user_id is None or e.actor_user_id == actor_user_id)
            and (since is None or e.occurred_at >= since)
            and (until is None or e.occurred_at <= until)
        ]
        return items[offset : offset + limit], len(items)

    def distinct_actions(self) -> list[str]:
        return sorted({e.action for e in self.events})

    def actions(self) -> list[str]:
        return [e.action for e in self.events]


@dataclass
class IdentityEnv:
    auth: AuthService
    admin: UserAdminService
    users: InMemoryUserRepository
    audit_repo: InMemoryAuditRepository
    tx: FakeTransaction
    clock: FakeClock
    hasher: FastHasher
    tokens: JwtTokenService


def build_identity_env(policy: AuthPolicy | None = None) -> IdentityEnv:
    users = InMemoryUserRepository()
    audit_repo = InMemoryAuditRepository()
    tx = FakeTransaction()
    clock = FakeClock()
    hasher = FastHasher()
    tokens = JwtTokenService(
        secret="s" * 40, algorithm="HS256", issuer="test", ttl=timedelta(minutes=30)
    )
    recorder = AuditRecorder(audit_repo, clock=clock)
    auth = AuthService(
        users=users,
        audit=recorder,
        tx=tx,
        hasher=hasher,
        tokens=tokens,
        policy=policy,
        clock=clock,
    )
    admin = UserAdminService(users=users, audit_repository=audit_repo, audit=recorder, tx=tx)
    return IdentityEnv(auth, admin, users, audit_repo, tx, clock, hasher, tokens)