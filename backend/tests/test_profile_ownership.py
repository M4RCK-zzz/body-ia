import pytest

from app.core.errors import ConflictError
from app.core.security_errors import PermissionDeniedError
from app.domain.access import AccessLevel
from tests.fakes import build_services


def test_create_gives_owner_access_and_audits():
    s = build_services()
    ana = s.new_user("ana")
    pid = s.profile_for(ana)
    access = s.access_repo.get_active(pid, ana.id)
    assert access is not None and access.level == "owner"
    assert s.profiles_repo.get(pid).owner_id == ana.id
    assert "profile.created" in s.audit_repo.actions()
    assert s.tx.commits >= 1


def test_duplicate_display_code_conflicts():
    s = build_services()
    s.profile_for(s.new_user("ana"), "BV-001")
    with pytest.raises(ConflictError):
        s.profile_for(s.new_user("luis"), "BV-001")


def test_get_returns_my_access():
    s = build_services()
    ana, luis = s.new_user("ana"), s.new_user("luis")
    pid = s.profile_for(ana)
    s.grant_direct(pid, luis, AccessLevel.VIEWER)
    assert s.profiles.get(ana, pid).my_access == "owner"
    assert s.profiles.get(luis, pid).my_access == "viewer"


def test_viewer_cannot_archive():
    s = build_services()
    ana, luis = s.new_user("ana"), s.new_user("luis")
    pid = s.profile_for(ana)
    s.grant_direct(pid, luis, AccessLevel.VIEWER)
    with pytest.raises(PermissionDeniedError):
        s.profiles.archive(luis, pid)
    assert s.profiles_repo.get(pid).status == "active"


def test_owner_archives_and_restores_with_audit():
    s = build_services()
    ana = s.new_user("ana")
    pid = s.profile_for(ana)
    s.profiles.archive(ana, pid)
    assert s.profiles_repo.get(pid).status == "archived"
    s.profiles.restore(ana, pid)
    assert s.profiles_repo.get(pid).status == "active"
    assert {"profile.archived", "profile.restored"} <= set(s.audit_repo.actions())