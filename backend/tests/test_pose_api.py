from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.api.deps import (
    get_consent_service,
    get_media_service,
    get_pose_service,
    get_profile_access_service,
    get_profile_service,
)
from app.api.security import get_current_user
from app.main import create_app
from tests.fakes import build_services


def _jpeg(width=32, height=32) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), (10, 20, 30)).save(buf, "JPEG")
    return buf.getvalue()


class ApiEnv:
    def __init__(self) -> None:
        self.services = build_services()
        self.app = create_app()
        self.app.dependency_overrides[get_profile_service] = lambda: self.services.profiles
        self.app.dependency_overrides[get_media_service] = lambda: self.services.media
        self.app.dependency_overrides[get_pose_service] = lambda: self.services.pose
        self.app.dependency_overrides[get_consent_service] = lambda: self.services.consent
        self.app.dependency_overrides[get_profile_access_service] = (
            lambda: self.services.access_service
        )
        self.client = TestClient(self.app)
        self.ana = self.services.new_user("ana")
        self.login(self.ana)

    def login(self, user) -> None:
        self.app.dependency_overrides[get_current_user] = lambda: user

    def accept_consent(self, pid: str) -> None:
        r = self.client.post(
            f"/api/profiles/{pid}/consents",
            json={"purpose": "data_processing", "declaration": True},
        )
        assert r.status_code == 201, r.text

    def profile(self, code: str = "BV-001") -> str:
        r = self.client.post("/api/profiles", json={"display_code": code})
        assert r.status_code == 201, r.text
        return r.json()["id"]

    def upload_asset(self, pid: str) -> str:
        r = self.client.post(
            f"/api/profiles/{pid}/media",
            files={"file": ("foto.jpg", _jpeg(), "image/jpeg")},
        )
        assert r.status_code == 201, r.text
        return r.json()["id"]


@pytest.fixture
def env() -> ApiEnv:
    return ApiEnv()


def _make(env: ApiEnv, code: str = "BV-001"):
    pid = env.profile(code)
    env.accept_consent(pid)
    asset_id = env.upload_asset(pid)
    return pid, asset_id


def test_enqueue_returns_201_and_badge(env):
    pid, asset_id = _make(env)
    r = env.client.post(f"/api/media/{asset_id}/pose-analyses")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "queued"
    assert body["media_asset_id"] == asset_id
    assert body["profile_id"] == pid
    assert body["visual_estimate_badge"] == "ESTIMACIÓN VISUAL"
    assert body["data_kind"] == "visual_estimate"
    assert body["landmarks"] is None  # la tarea nueva no tiene landmarks
    assert "pose.queued" in env.services.audit_repo.actions()


def test_enqueue_is_idempotent_200(env):
    pid, asset_id = _make(env)
    r1 = env.client.post(f"/api/media/{asset_id}/pose-analyses")
    assert r1.status_code == 201
    r2 = env.client.post(f"/api/media/{asset_id}/pose-analyses")
    assert r2.status_code == 200, r2.text
    assert r2.json()["id"] == r1.json()["id"]
    # La tarea no se duplica
    assert len(env.services.pose_repo.items) == 1


def test_enqueue_rejects_non_ready_asset(env):
    pid, asset_id = _make(env)
    # Forzar un estado no-ready
    import uuid

    asset = env.services.media_repo.get(uuid.UUID(asset_id))
    assert asset is not None
    asset.status = "rejected"
    r = env.client.post(f"/api/media/{asset_id}/pose-analyses")
    assert r.status_code == 422


def test_get_analysis_returns_200_with_badge(env):
    pid, asset_id = _make(env)
    r = env.client.post(f"/api/media/{asset_id}/pose-analyses")
    analysis_id = r.json()["id"]
    r = env.client.get(f"/api/pose-analyses/{analysis_id}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"] == analysis_id
    assert body["status"] == "queued"
    assert body["visual_estimate_badge"] == "ESTIMACIÓN VISUAL"


def test_list_by_asset_returns_page(env):
    pid, asset_id = _make(env)
    env.client.post(f"/api/media/{asset_id}/pose-analyses")
    r = env.client.get(f"/api/media/{asset_id}/pose-analyses")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["status"] == "queued"


def test_list_by_profile_returns_page(env):
    pid, asset_id = _make(env)
    env.client.post(f"/api/media/{asset_id}/pose-analyses")
    r = env.client.get(f"/api/profiles/{pid}/pose-analyses")
    assert r.status_code == 200
    assert r.json()["total"] == 1


def test_unknown_analysis_returns_404(env):
    r = env.client.get("/api/pose-analyses/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


def test_get_requires_access(env):
    pid, asset_id = _make(env)
    r = env.client.post(f"/api/media/{asset_id}/pose-analyses")
    analysis_id = r.json()["id"]
    outsider = env.services.new_user("outsider")
    env.login(outsider)
    r = env.client.get(f"/api/pose-analyses/{analysis_id}")
    assert r.status_code in (403, 404)
