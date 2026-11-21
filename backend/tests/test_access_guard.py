from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.errors import NotFoundError
from app.core.security_errors import PermissionDeniedError
from app.domain.access import AccessLevel
from tests.fakes import build_services


@pytest.fixture
def env():
    s = build_services()
    owner = s.new_user("ana")
    other = s.new_user("luis")
    return SimpleNamespace(s=s, owner=owner, other=other, pid=s.profile_for(owner))


def test_owner_passes_and_gets_owner_level(env):
    profile, access = env.s.guard.require(env.pid, env.owner, minimum=AccessLevel.OWNER)
    assert profile.id == env.pid
    assert access.level == "owner"


def test_unknown_profile_is_404_and_not_audited(env):
    with pytest.raises(NotFoundError):
        env.s.guard.require(uuid4(), env.owner)
    assert "access.denied" not in env.s.audit_repo.actions()


def test_no_access_is_404_and_audited(env):
    commits_before = env.s.tx.commits
    with pytest.raises(NotFoundError):
        env.s.guard.require(env.pid, env.other)
    events = [e for e in env.s.audit_repo.events if e.action == "access.denied"]
    assert len(events) == 1
    assert events[0].actor_user_id == env.other.id
    assert "no_access" in str(events[0].detail)
    assert env.s.tx.commits > commits_before  # la denegación se confirma antes de lanzar


def test_insufficient_level_is_403_and_audited(env):
    env.s.grant_direct(env.pid, env.other, AccessLevel.VIEWER)
    with pytest.raises(PermissionDeniedError):
        env.s.guard.require(env.pid, env.other, minimum=AccessLevel.EDITOR)
    events = [e for e in env.s.audit_repo.events if e.action == "access.denied"]
    assert len(events) == 1
    assert "insufficient_level" in str(events[0].detail)


def test_editor_can_edit_but_not_own(env):
    env.s.grant_direct(env.pid, env.other, AccessLevel.EDITOR)
    env.s.guard.require(env.pid, env.other, minimum=AccessLevel.EDITOR)
    with pytest.raises(PermissionDeniedError):
        env.s.guard.require(env.pid, env.other, minimum=AccessLevel.OWNER)


def test_admin_has_no_implicit_access(env):
    admin = env.s.new_user("root", role="admin")
    with pytest.raises(NotFoundError):
        env.s.guard.require(env.pid, admin)


def test_revoked_access_stops_working_immediately(env):
    grant = env.s.grant_direct(env.pid, env.other, AccessLevel.VIEWER)
    env.s.guard.require(env.pid, env.other)
    grant.revoked_at = env.s.clock()
    with pytest.raises(NotFoundError):
        env.s.guard.require(env.pid, env.other)


@pytest.mark.parametrize(
    ("granted", "required", "allowed"),
    [
        ("viewer", "viewer", True),
        ("viewer", "editor", False),
        ("viewer", "owner", False),
        ("editor", "viewer", True),
        ("editor", "editor", True),
        ("editor", "owner", False),
        ("owner", "viewer", True),
        ("owner", "editor", True),
        ("owner", "owner", True),
    ],
)
def test_permission_matrix(env, granted, required, allowed):
    actor = env.owner
    if granted != "owner":
        env.s.grant_direct(env.pid, env.other, granted)
        actor = env.other
    minimum = AccessLevel(required)
    if allowed:
        env.s.guard.require(env.pid, actor, minimum=minimum)
    else:
        with pytest.raises(PermissionDeniedError):
            env.s.guard.require(env.pid, actor, minimum=minimum)
            