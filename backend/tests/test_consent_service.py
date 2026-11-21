from types import SimpleNamespace

import pytest

from app.core.errors import AppError
from app.core.security_errors import ConsentRequiredError, PermissionDeniedError
from app.domain.access import AccessLevel, ConsentPurpose
from tests.fakes import build_services

PURPOSE = ConsentPurpose.DATA_PROCESSING


@pytest.fixture
def env():
    s = build_services()
    owner = s.new_user("ana")
    other = s.new_user("luis")
    return SimpleNamespace(s=s, owner=owner, other=other, pid=s.profile_for(owner))


def test_without_consent_ensure_valid_fails(env):
    with pytest.raises(ConsentRequiredError):
        env.s.consent.ensure_valid(env.pid, PURPOSE)


def test_owner_accepts_and_consent_becomes_valid(env):
    env.s.consent.accept(env.owner, env.pid, PURPOSE)
    env.s.consent.ensure_valid(env.pid, PURPOSE)
    assert "consent.accepted" in env.s.audit_repo.actions()


def test_editor_cannot_accept(env):
    env.s.grant_direct(env.pid, env.other, AccessLevel.EDITOR)
    with pytest.raises(PermissionDeniedError):
        env.s.consent.accept(env.other, env.pid, PURPOSE)


def test_accepting_same_version_twice_is_idempotent(env):
    env.s.consent.accept(env.owner, env.pid, PURPOSE)
    env.s.consent.accept(env.owner, env.pid, PURPOSE)
    assert len(env.s.consents_repo.items) == 1


def test_revoke_invalidates_consent_and_keeps_the_row(env):
    env.s.consent.accept(env.owner, env.pid, PURPOSE)
    env.s.consent.revoke(env.owner, env.pid, PURPOSE)
    with pytest.raises(ConsentRequiredError):
        env.s.consent.ensure_valid(env.pid, PURPOSE)
    rows = env.s.consents_repo.items
    assert len(rows) == 1 and rows[0].revoked_at is not None
    assert "consent.revoked" in env.s.audit_repo.actions()


def test_cannot_accept_on_archived_profile(env):
    env.s.profiles.archive(env.owner, env.pid)
    with pytest.raises(AppError):
        env.s.consent.accept(env.owner, env.pid, PURPOSE)


def test_statuses_reflect_validity(env):
    before = env.s.consent.statuses(env.owner, env.pid)
    assert [s.valid for s in before] == [False]
    env.s.consent.accept(env.owner, env.pid, PURPOSE)
    after = env.s.consent.statuses(env.owner, env.pid)
    assert [s.valid for s in after] == [True]