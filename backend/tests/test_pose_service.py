from __future__ import annotations

import io

import pytest
from PIL import Image

from app.core.errors import BusinessRuleError, NotFoundError
from app.core.security_errors import ConsentRequiredError, PermissionDeniedError
from app.domain.media import MediaStatus
from app.domain.pose import PoseAnalysisStatus
from tests.fakes import build_services


def _jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (24, 24), (10, 20, 30)).save(buf, "JPEG")
    return buf.getvalue()


def _env(clock=None):
    env = build_services()
    return env


def _ready_asset(env, owner, code="BV-001"):
    pid = env.profile_for(owner, code)
    env.accept_consent(owner, pid)
    asset = env.media.upload(owner, pid, data=_jpeg(), declared_mime="image/jpeg")
    return pid, asset


class TestEnqueue:
    def test_enqueue_creates_queued_task(self):
        env = _env()
        owner = env.new_user("ana")
        pid, asset = _ready_asset(env, owner)

        analysis, created = env.pose.enqueue(owner, asset.id)

        assert created is True
        assert analysis.status == PoseAnalysisStatus.QUEUED.value
        assert analysis.profile_id == pid
        assert analysis.media_asset_id == asset.id
        assert analysis.created_by_user_id == owner.id
        assert "pose.queued" in env.audit_repo.actions()

    def test_reencode_asset_returns_existing_task_not_duplicated(self):
        env = _env()
        owner = env.new_user("ana")
        pid, asset = _ready_asset(env, owner)

        first, created1 = env.pose.enqueue(owner, asset.id)
        second, created2 = env.pose.enqueue(owner, asset.id)

        assert created1 is True
        assert created2 is False
        assert first.id == second.id
        assert len(env.pose_repo.items) == 1

    def test_enqueue_rejects_non_ready_asset(self):
        env = _env()
        owner = env.new_user("ana")
        pid, asset = _ready_asset(env, owner)
        asset.status = MediaStatus.DELETED.value

        with pytest.raises(BusinessRuleError, match="ready"):
            env.pose.enqueue(owner, asset.id)

    def test_enqueue_rejects_unknown_asset(self):
        env = _env()
        owner = env.new_user("ana")
        pid, _ = _ready_asset(env, owner)
        from uuid import uuid4

        with pytest.raises(NotFoundError):
            env.pose.enqueue(owner, uuid4())

    def test_enqueue_requires_editor_level(self, ):
        env = _env()
        owner = env.new_user("ana")
        pid, asset = _ready_asset(env, owner)
        viewer = env.new_user("viewer")
        env.grant_direct(pid, viewer, "viewer")

        with pytest.raises(PermissionDeniedError):
            env.pose.enqueue(viewer, asset.id)

    def test_enqueue_requires_consent(self):
        from app.domain.access import ConsentPurpose

        env = _env()
        owner = env.new_user("ana")
        pid = env.profile_for(owner, "BV-001")
        env.accept_consent(owner, pid)
        asset = env.media.upload(owner, pid, data=_jpeg(), declared_mime="image/jpeg")
        # Al revocar el consentimiento, enqueue debe rechazarse
        env.consent.revoke(owner, pid, ConsentPurpose.DATA_PROCESSING)

        with pytest.raises(ConsentRequiredError):
            env.pose.enqueue(owner, asset.id)


class TestGet:
    def test_get_requires_access(self):
        env = _env()
        owner = env.new_user("ana")
        pid, asset = _ready_asset(env, owner)
        analysis, _ = env.pose.enqueue(owner, asset.id)
        outsider = env.new_user("outsider")

        with pytest.raises(NotFoundError):
            env.pose.get(outsider, analysis.id)

    def test_get_returns_analysis(self):
        env = _env()
        owner = env.new_user("ana")
        pid, asset = _ready_asset(env, owner)
        analysis, _ = env.pose.enqueue(owner, asset.id)

        fetched = env.pose.get(owner, analysis.id)
        assert fetched.id == analysis.id


class TestList:
    def test_list_for_asset(self):
        env = _env()
        owner = env.new_user("ana")
        pid, asset = _ready_asset(env, owner)
        env.pose.enqueue(owner, asset.id)

        rows, total = env.pose.list_for_asset(owner, asset.id)
        assert total == 1
        assert rows[0].id == rows[0].id

    def test_list_for_profile_filters_by_status(self):
        env = _env()
        owner = env.new_user("ana")
        pid, asset = _ready_asset(env, owner)
        env.pose.enqueue(owner, asset.id)

        rows, total = env.pose.list_for_profile(owner, pid, status="queued")
        assert total == 1
        rows, total = env.pose.list_for_profile(owner, pid, status="completed")
        assert total == 0
