from __future__ import annotations

from datetime import timedelta

import pytest

from app.core.errors import BusinessRuleError, ConflictError
from app.core.security_errors import AuthenticationError, PermissionDeniedError
from app.domain.identity import AuditAction, RoleName
from app.services.auth_service import AuthPolicy
from tests.identity_fakes import IdentityEnv, build_identity_env

PASSWORD = "Correcta-12345"


@pytest.fixture
def env() -> IdentityEnv:
    return build_identity_env(
        AuthPolicy(max_login_attempts=3, lock_duration=timedelta(minutes=15))
    )


def _register(env: IdentityEnv, email: str = "ana@example.com"):
    return env.auth.register(email=email, password=PASSWORD, full_name="Ana Pérez")


def test_register_creates_user_with_user_role(env):
    user = _register(env)
    assert user.role_names == ["user"]
    assert user.password_hash != PASSWORD
    assert env.tx.commits == 1


def test_register_normalizes_email(env):
    user = _register(env, "  Ana@Example.COM ")
    assert user.email == "ana@example.com"


def test_register_duplicate_email_conflicts(env):
    _register(env)
    with pytest.raises(ConflictError):
        _register(env, "ANA@example.com")


def test_register_disabled_is_forbidden():
    env = build_identity_env(AuthPolicy(allow_registration=False))
    with pytest.raises(PermissionDeniedError):
        _register(env)


def test_login_success_returns_token_that_authenticates(env):
    user = _register(env)
    result = env.auth.login(email="ana@example.com", password=PASSWORD)
    assert result.user.id == user.id
    assert env.auth.authenticate(result.token.value).id == user.id
    assert result.user.last_login_at is not None


def test_login_unknown_email_gives_generic_error(env):
    with pytest.raises(AuthenticationError) as unknown:
        env.auth.login(email="nadie@example.com", password=PASSWORD)
    _register(env)
    with pytest.raises(AuthenticationError) as wrong:
        env.auth.login(email="ana@example.com", password="Otra-clave-999")
    assert unknown.value.message == wrong.value.message
    assert unknown.value.code == wrong.value.code == "invalid_credentials"


def test_failed_login_persists_counter_and_audit(env):
    user = _register(env)
    commits_before = env.tx.commits
    with pytest.raises(AuthenticationError):
        env.auth.login(email="ana@example.com", password="mala-clave-1")
    assert user.failed_login_count == 1
    assert env.tx.commits == commits_before + 1
    assert AuditAction.LOGIN_FAILED in env.audit_repo.actions()


def test_lockout_blocks_even_correct_password_until_it_expires(env):
    user = _register(env)
    for _ in range(3):
        with pytest.raises(AuthenticationError):
            env.auth.login(email="ana@example.com", password="mala-clave-1")
    assert user.locked_until is not None
    assert AuditAction.ACCOUNT_LOCKED in env.audit_repo.actions()

    with pytest.raises(AuthenticationError):
        env.auth.login(email="ana@example.com", password=PASSWORD)

    env.clock.advance(minutes=16)
    assert env.auth.login(email="ana@example.com", password=PASSWORD).user.id == user.id


def test_login_inactive_user_is_denied(env):
    user = _register(env)
    user.is_active = False
    with pytest.raises(AuthenticationError):
        env.auth.login(email="ana@example.com", password=PASSWORD)


def test_authenticate_rejects_invalid_token(env):
    with pytest.raises(AuthenticationError) as exc:
        env.auth.authenticate("esto-no-es-un-jwt")
    assert exc.value.code == "invalid_token"


def test_login_and_registration_are_audited(env):
    _register(env)
    env.auth.login(email="ana@example.com", password=PASSWORD)
    assert env.audit_repo.actions() == [AuditAction.REGISTERED, AuditAction.LOGIN]


def _make_admin(env: IdentityEnv):
    return env.users.create(
        email="admin@example.com",
        password_hash=env.hasher.hash(PASSWORD),
        full_name="Admin",
        role_names=["user", "admin"],
    )


def test_admin_set_roles_applies_immediately_and_is_audited(env):
    admin = _make_admin(env)
    user = _register(env)
    updated = env.admin.set_roles(
        actor=admin, user_id=user.id, roles=[RoleName.USER, RoleName.PROFESSIONAL]
    )
    assert updated.role_names == ["professional", "user"]
    event = env.audit_repo.events[-1]
    assert event.action == AuditAction.ROLES_CHANGED
    assert event.detail == {"before": ["user"], "after": ["professional", "user"]}


def test_admin_cannot_remove_own_admin_role(env):
    admin = _make_admin(env)
    with pytest.raises(BusinessRuleError):
        env.admin.set_roles(actor=admin, user_id=admin.id, roles=[RoleName.USER])


def test_admin_cannot_deactivate_self(env):
    admin = _make_admin(env)
    with pytest.raises(BusinessRuleError):
        env.admin.set_active(actor=admin, user_id=admin.id, active=False)


def test_deactivated_user_loses_access_with_existing_token(env):
    admin = _make_admin(env)
    user = _register(env)
    token = env.auth.login(email="ana@example.com", password=PASSWORD).token.value
    env.admin.set_active(actor=admin, user_id=user.id, active=False)
    with pytest.raises(AuthenticationError):
        env.auth.authenticate(token)