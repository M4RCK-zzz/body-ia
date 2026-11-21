from types import SimpleNamespace

import pytest

from app.core.errors import AppError, NotFoundError
from app.core.security_errors import PermissionDeniedError
from app.domain.access import AccessLevel
from tests.fakes import build_services

LUIS = "luis@example.com"


@pytest.fixture
def env():
    s = build_services()
    owner = s.new_user("ana")
    other = s.new_user("luis")
    return SimpleNamespace(s=s, owner=owner, other=other, pid=s.profile_for(owner))


def _rows(env):
    return [a for a in env.s.access_repo.items if a.user_id == env.other.id]


def test_owner_grants_editor_by_email_and_audits(env):
    env.s.access_service.grant(env.owner, env.pid, LUIS, AccessLevel.EDITOR)
    active = env.s.access_repo.get_active(env.pid, env.other.id)
    assert active is not None and active.level == "editor"
    assert "access.granted" in env.s.audit_repo.actions()


def test_non_owner_cannot_grant(env):
    env.s.grant_direct(env.pid, env.other, AccessLevel.EDITOR)
    third = env.s.new_user("eva")
    with pytest.raises(PermissionDeniedError):
        env.s.access_service.grant(env.other, env.pid, third.email, AccessLevel.VIEWER)


def test_cannot_grant_owner_level(env):
    with pytest.raises(AppError):
        env.s.access_service.grant(env.owner, env.pid, LUIS, AccessLevel.OWNER)
    assert _rows(env) == []


def test_cannot_grant_to_self(env):
    with pytest.raises(AppError):
        env.s.access_service.grant(env.owner, env.pid, env.owner.email, AccessLevel.VIEWER)


def test_unknown_email_is_404(env):
    with pytest.raises(NotFoundError):
        env.s.access_service.grant(env.owner, env.pid, "nadie@example.com", AccessLevel.VIEWER)


def test_inactive_account_is_404(env):
    env.other.is_active = False
    with pytest.raises(NotFoundError):
        env.s.access_service.grant(env.owner, env.pid, LUIS, AccessLevel.VIEWER)


def test_same_level_is_idempotent(env):
    env.s.access_service.grant(env.owner, env.pid, LUIS, AccessLevel.VIEWER)
    env.s.access_service.grant(env.owner, env.pid, LUIS, AccessLevel.VIEWER)
    assert len(_rows(env)) == 1


def test_level_change_revokes_old_row_and_keeps_history(env):
    env.s.access_service.grant(env.owner, env.pid, LUIS, AccessLevel.VIEWER)
    env.s.access_service.grant(env.owner, env.pid, LUIS, AccessLevel.EDITOR)
    rows = _rows(env)
    assert len(rows) == 2
    assert [r.level for r in rows if r.revoked_at is None] == ["editor"]
    assert [r.level for r in rows if r.revoked_at is not None] == ["viewer"]


def test_revoke_takes_effect_immediately(env):
    env.s.access_service.grant(env.owner, env.pid, LUIS, AccessLevel.EDITOR)
    env.s.guard.require(env.pid, env.other)
    env.s.access_service.revoke(env.owner, env.pid, env.other.id)
    with pytest.raises(NotFoundError):
        env.s.guard.require(env.pid, env.other)
    assert "access.revoked" in env.s.audit_repo.actions()


def test_cannot_revoke_the_owner(env):
    with pytest.raises(AppError):
        env.s.access_service.revoke(env.owner, env.pid, env.owner.id)
    assert env.s.access_repo.get_active(env.pid, env.owner.id) is not None


def test_owner_lists_access(env):
    env.s.access_service.grant(env.owner, env.pid, LUIS, AccessLevel.VIEWER)
    assert len(env.s.access_service.list_access(env.owner, env.pid)) == 2


def test_viewer_cannot_list_access(env):
    env.s.grant_direct(env.pid, env.other, AccessLevel.VIEWER)
    with pytest.raises(PermissionDeniedError):
        env.s.access_service.list_access(env.other, env.pid)
        