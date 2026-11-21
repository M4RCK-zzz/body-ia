from uuid import uuid4

import pytest

from app.core.errors import BusinessRuleError, ConflictError, NotFoundError
from app.core.security_errors import PermissionDeniedError
from app.domain.access import AccessLevel
from app.domain.profiles import ProfileStatus
from tests.fakes import build_services


def _p(view):
    """ProfileView o Profile, según lo que devuelva el servicio."""
    return getattr(view, "profile", view)


def test_create_rejects_duplicate_code():
    s = build_services()
    ana = s.new_user("ana")
    s.profiles.create(ana, "BV-001")
    with pytest.raises(ConflictError):
        s.profiles.create(ana, "BV-001")


def test_archive_and_restore():
    s = build_services()
    ana = s.new_user("ana")
    pid = s.profile_for(ana)
    archived = _p(s.profiles.archive(ana, pid))
    assert archived.status == ProfileStatus.ARCHIVED.value
    assert archived.archived_at is not None
    restored = _p(s.profiles.restore(ana, pid))
    assert restored.status == ProfileStatus.ACTIVE.value
    assert restored.archived_at is None


def test_rename_archived_profile_is_rejected():
    s = build_services()
    ana = s.new_user("ana")
    pid = s.profile_for(ana)
    s.profiles.archive(ana, pid)
    with pytest.raises(BusinessRuleError):
        s.profiles.rename(ana, pid, "BV-002")


def test_get_unknown_profile_raises_not_found():
    s = build_services()
    with pytest.raises(NotFoundError):
        s.profiles.get(s.new_user("ana"), uuid4())


def test_editor_cannot_rename():
    s = build_services()
    ana, luis = s.new_user("ana"), s.new_user("luis")
    pid = s.profile_for(ana)
    s.grant_direct(pid, luis, AccessLevel.EDITOR)
    with pytest.raises(PermissionDeniedError):
        s.profiles.rename(luis, pid, "BV-002")
    assert s.profiles_repo.get(pid).display_code == "BV-001"


def test_list_only_returns_profiles_with_active_access():
    s = build_services()
    ana, luis = s.new_user("ana"), s.new_user("luis")
    shared = s.profile_for(ana, "BV-001")
    s.profile_for(ana, "BV-002")
    s.grant_direct(shared, luis, AccessLevel.VIEWER)
    rows_luis, total_luis = s.profiles.list_page(luis, status=None, limit=50, offset=0)
    assert total_luis == 1
    assert [v.my_access for v in rows_luis] == ["viewer"]
    _, total_ana = s.profiles.list_page(ana, status=None, limit=50, offset=0)
    assert total_ana == 2