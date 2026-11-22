from __future__ import annotations

import io

import pytest
from PIL import Image

from app.core.errors import (
    BusinessRuleError,
    FileTooLargeError,
    MediaRejectedError,
    NotFoundError,
    UnsupportedMediaTypeError,
)
from app.core.security_errors import ConsentRequiredError, PermissionDeniedError
from app.domain.media import MediaStatus
from app.services.media_service import MediaService
from tests.fakes import Services, build_services


def _jpeg(width=32, height=16) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), (10, 20, 30)).save(buf, "JPEG")
    return buf.getvalue()


@pytest.fixture
def env() -> Services:
    return build_services()


def _profile(env: Services, code: str = "BV-001", owner=None) -> tuple:
    owner = owner or env.new_user("ana")
    pid = env.profile_for(owner, code)
    return pid, owner


def _service_with_limit(env: Services, max_bytes: int):
    media = env.media
    return MediaService(
        media._guard,
        media._media,
        media._storage,
        media._consents,
        media._audit,
        media._tx,
        media._clock,
        max_upload_bytes=max_bytes,
        max_pixels=25_000_000,
        retention_days=365,
    )


def _upload(env: Services, pid, actor, data=None, mime: str = "image/jpeg"):
    payload = data if data is not None else _jpeg()
    return env.media.upload(actor, pid, data=payload, declared_mime=mime)


class TestUpload:
    def test_upload_ready_with_file_and_audit(self, env):
        pid, owner = _profile(env)
        env.accept_consent(owner, pid)
        data = _jpeg()

        asset = _upload(env, pid, owner, data)

        assert asset.status == MediaStatus.READY.value
        assert asset.mime_type == "image/jpeg"
        assert asset.storage_key is not None
        assert env.storage.exists(asset.storage_key)
        assert asset.width == 32 and asset.height == 16
        import hashlib

        stored_bytes = env.storage.get(asset.storage_key)
        assert asset.checksum == hashlib.sha256(stored_bytes).hexdigest()
        assert asset.retention_until is not None
        actions = env.audit_repo.actions()
        assert "media.uploaded" in actions

    def test_upload_author_is_server_side_from_actor(self, env):
        pid, owner = _profile(env)
        env.accept_consent(owner, pid)

        asset = _upload(env, pid, owner)

        assert asset.uploaded_by_snapshot == owner.full_name
        assert asset.uploaded_by_user_id == owner.id

    def test_upload_rejected_without_file_or_consent_block(self, env):
        pid, owner = _profile(env)
        env.accept_consent(owner, pid)

        with pytest.raises(MediaRejectedError):
            _upload(env, pid, owner, data=b"not-an-image")

        rejected = [a for a in env.media_repo.items if a.profile_id == pid]
        assert len(rejected) == 1
        assert rejected[0].status == MediaStatus.REJECTED.value
        assert rejected[0].storage_key is None
        assert rejected[0].mime_type is None
        # Nada queda en el storage
        assert not env.storage.files
        assert "media.rejected" in env.audit_repo.actions()

    def test_upload_rejects_oversize_and_bad_mime(self, env):
        pid, owner = _profile(env)
        env.accept_consent(owner, pid)

        service = _service_with_limit(env, max_bytes=100)
        with pytest.raises(FileTooLargeError):
            service.upload(owner, pid, data=b"x" * 101, declared_mime="image/jpeg")

        with pytest.raises(UnsupportedMediaTypeError):
            env.media.upload(owner, pid, data=_jpeg(), declared_mime="text/plain")

    def test_viewer_cannot_upload(self, env):
        pid, owner = _profile(env)
        env.accept_consent(owner, pid)
        viewer = env.new_user("luis")
        env.grant_direct(pid, viewer, "viewer")
        with pytest.raises(PermissionDeniedError):
            _upload(env, pid, viewer)

    def test_requires_active_profile(self, env):
        pid, owner = _profile(env)
        env.accept_consent(owner, pid)
        env.profiles.archive(owner, pid)
        with pytest.raises(BusinessRuleError):
            _upload(env, pid, owner)

    def test_requires_consent(self, env):
        pid, owner = _profile(env)
        with pytest.raises(ConsentRequiredError):
            _upload(env, pid, owner)

    def test_other_profile_is_404(self, env):
        pid, owner = _profile(env)
        env.accept_consent(owner, pid)
        stranger = env.new_user("stranger")
        with pytest.raises(NotFoundError):
            _upload(env, pid, stranger)

    def test_delete_cleans_storage_and_audits(self, env):
        pid, owner = _profile(env)
        env.accept_consent(owner, pid)
        asset = _upload(env, pid, owner)

        deleted = env.media.delete(owner, asset.id)

        assert deleted.status == MediaStatus.DELETED.value
        assert deleted.deleted_at is not None
        assert deleted.deleted_by_user_id == owner.id
        assert not env.storage.exists(deleted.storage_key)
        assert "media.deleted" in env.audit_repo.actions()

    def test_delete_is_idempotent(self, env):
        pid, owner = _profile(env)
        env.accept_consent(owner, pid)
        asset = _upload(env, pid, owner)
        env.media.delete(owner, asset.id)
        again = env.media.delete(owner, asset.id)
        assert again.status == MediaStatus.DELETED.value


class TestList:
    def test_list_excludes_deleted_by_default(self, env):
        pid, owner = _profile(env)
        env.accept_consent(owner, pid)
        a1 = _upload(env, pid, owner)
        a2 = _upload(env, pid, owner)
        env.media.delete(owner, a2.id)
        assets, total = env.media.list_assets(owner, pid)
        assert total == 1 and assets[0].id == a1.id

    def test_list_filters_by_status(self, env):
        pid, owner = _profile(env)
        env.accept_consent(owner, pid)
        _upload(env, pid, owner)
        with pytest.raises(MediaRejectedError):
            _upload(env, pid, owner, data=b"nope")

        rejected, _ = env.media.list_assets(owner, pid, status=MediaStatus.REJECTED)
        assert len(rejected) == 1

        ready, _ = env.media.list_assets(owner, pid, status=MediaStatus.READY)
        assert len(ready) == 1


class TestContent:
    def test_content_ready_returns_bytes(self, env):
        pid, owner = _profile(env)
        env.accept_consent(owner, pid)
        asset = _upload(env, pid, owner)
        got, data = env.media.content(owner, asset.id)
        assert got.id == asset.id
        assert data == env.storage.get(asset.storage_key)

    def test_content_for_rejected_asset_returns_404(self, env):
        pid, owner = _profile(env)
        env.accept_consent(owner, pid)
        with pytest.raises(MediaRejectedError):
            _upload(env, pid, owner, data=b"nope")
        rejected = [a for a in env.media_repo.items if a.profile_id == pid][0]
        with pytest.raises(NotFoundError):
            env.media.content(owner, rejected.id)


class TestGet:
    def test_get_cross_profile_is_404(self, env):
        pid, owner = _profile(env)
        env.accept_consent(owner, pid)
        asset = _upload(env, pid, owner)
        stranger = env.new_user("stranger")
        with pytest.raises(NotFoundError):
            env.media.get(stranger, asset.id)
