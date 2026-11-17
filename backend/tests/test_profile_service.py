from uuid import uuid4
import pytest
from app.core.errors import BusinessRuleError, ConflictError, NotFoundError
from app.domain.profiles import ProfileStatus
from tests.fakes import build_services

def test_create_rejects_duplicate_code():
    s = build_services()
    s.profiles.create("BV-001")
    with pytest.raises(ConflictError):
        s.profiles.create("BV-001")

def test_archive_and_restore():
    s = build_services()
    profile = s.profiles.create("BV-001")

    archived = s.profiles.archive(profile.id)
    assert archived.status == ProfileStatus.ARCHIVED.value
    assert archived.archived_at is not None

    restored = s.profiles.restore(profile.id)
    assert restored.status == ProfileStatus.ACTIVE.value
    assert restored.archived_at is None

def test_rename_archived_profile_is_rejected():
    s = build_services()
    profile = s.profiles.create("BV-001")
    s.profiles.archive(profile.id)
    with pytest.raises(BusinessRuleError):
        s.profiles.rename(profile.id, "BV-002")

def test_get_unknown_profile_raises_not_found():
    with pytest.raises(NotFoundError):
        build_services().profiles.get(uuid4())