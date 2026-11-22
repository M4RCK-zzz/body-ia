from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.api.deps import (
    get_consent_service,
    get_media_service,
    get_profile_access_service,
    get_profile_service,
)
from app.api.security import get_current_user
from app.main import create_app
from tests.fakes import build_services


class ApiEnv:
    def __init__(self) -> None:
        self.services = build_services()
        self.app = create_app()
        self.app.dependency_overrides[get_profile_service] = lambda: self.services.profiles
        self.app.dependency_overrides[get_media_service] = lambda: self.services.media
        self.app.dependency_overrides[get_consent_service] = lambda: self.services.consent
        self.app.dependency_overrides[get_profile_access_service] = (
            lambda: self.services.access_service
        )
        self.client = TestClient(self.app)
        self.ana = self.services.new_user("ana")
        self.luis = self.services.new_user("luis")
        self.root = self.services.new_user("root", role="admin")
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

    def grant(self, pid: str, user, level: str) -> None:
        r = self.client.post(
            f"/api/profiles/{pid}/access", json={"email": user.email, "level": level}
        )
        assert r.status_code in (200, 201), r.text


@pytest.fixture
def env() -> ApiEnv:
    return ApiEnv()


def _jpeg(width=32, height=32) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), (10, 20, 30)).save(buf, "JPEG")
    return buf.getvalue()


def test_upload_full_lifecycle(env):
    pid = env.profile()
    env.accept_consent(pid)
    r = env.client.post(
        f"/api/profiles/{pid}/media",
        files={"file": ("foto.jpg", _jpeg(), "image/jpeg")},
    )
    assert r.status_code == 201, r.text
    asset = r.json()
    assert asset["status"] == "ready"
    assert asset["mime_type"] == "image/jpeg"
    assert asset["uploaded_by"] == "Ana"
    assert asset["width"] == 32 and asset["height"] == 32
    assert len(asset["checksum"]) == 64
    assert asset["rejection_reason"] is None
    assert "foto" not in str(asset)  # ni el nombre original

    # Listado
    r = env.client.get(f"/api/profiles/{pid}/media")
    assert r.status_code == 200
    assert r.json()["total"] == 1

    # Metadata
    r = env.client.get(f"/api/media/{asset['id']}")
    assert r.status_code == 200 and r.json()["id"] == asset["id"]

    # Contenido: bytes + encabezados privados
    r = env.client.get(f"/api/media/{asset['id']}/content")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/jpeg")
    assert r.headers["cache-control"] == "private, no-store"
    assert r.headers["x-content-type-options"] == "nosniff"
    stored = [a for a in env.services.media_repo.items if str(a.id) == asset["id"]][0]
    assert r.content == env.services.storage.get(stored.storage_key)

    # Borrado
    r = env.client.delete(f"/api/media/{asset['id']}")
    assert r.status_code == 200
    assert r.json()["status"] == "deleted"
    r = env.client.get(f"/api/media/{asset['id']}/content")
    assert r.status_code == 404


def test_upload_requires_consent(env):
    pid = env.profile()
    r = env.client.post(
        f"/api/profiles/{pid}/media", files={"file": ("f.jpg", _jpeg(), "image/jpeg")}
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "consent_required"


def test_upload_viewer_forbidden(env):
    pid = env.profile()
    env.accept_consent(pid)
    env.grant(pid, env.luis, "viewer")
    env.login(env.luis)
    r = env.client.post(
        f"/api/profiles/{pid}/media", files={"file": ("f.jpg", _jpeg(), "image/jpeg")}
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "insufficient_access"


def test_upload_other_profile_is_404(env):
    pid = env.profile()
    env.accept_consent(pid)
    env.login(env.luis)
    r = env.client.post(
        f"/api/profiles/{pid}/media", files={"file": ("f.jpg", _jpeg(), "image/jpeg")}
    )
    assert r.status_code == 404


def test_upload_bad_mime_is_415(env):
    pid = env.profile()
    env.accept_consent(pid)
    r = env.client.post(
        f"/api/profiles/{pid}/media",
        files={"file": ("f.txt", b"plain text", "text/plain")},
    )
    assert r.status_code == 415
    assert r.json()["error"]["code"] == "unsupported_media_type"


def test_upload_corrupt_image_is_rejected_with_metadata_only(env):
    pid = env.profile()
    env.accept_consent(pid)
    r = env.client.post(
        f"/api/profiles/{pid}/media",
        files={"file": ("f.jpg", b"\x00\x01\x02\x03 garbage", "image/jpeg")},
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "media_rejected"

    # Metadatos persistidos, sin bytes ni storage_key
    assets = [a for a in env.services.media_repo.items if str(a.profile_id) == pid]
    assert len(assets) == 1
    assert assets[0].status == "rejected"
    assert assets[0].storage_key is None
    assert assets[0].rejection_reason
    assert not env.services.storage.files


def test_list_and_content_cross_profile_404(env):
    pid = env.profile()
    env.accept_consent(pid)
    r = env.client.post(
        f"/api/profiles/{pid}/media", files={"file": ("f.jpg", _jpeg(), "image/jpeg")}
    )
    asset_id = r.json()["id"]
    env.login(env.luis)  # stranger
    assert env.client.get(f"/api/profiles/{pid}/media").status_code == 404
    assert env.client.get(f"/api/media/{asset_id}").status_code == 404
    assert env.client.get(f"/api/media/{asset_id}/content").status_code == 404


def test_admin_has_no_implicit_access(env):
    pid = env.profile()
    env.accept_consent(pid)
    env.login(env.root)
    assert env.client.get(f"/api/profiles/{pid}/media").status_code == 404


def test_delete_is_idempotent_and_audited(env):
    pid = env.profile()
    env.accept_consent(pid)
    r = env.client.post(
        f"/api/profiles/{pid}/media", files={"file": ("f.jpg", _jpeg(), "image/jpeg")}
    )
    asset_id = r.json()["id"]
    assert env.client.delete(f"/api/media/{asset_id}").status_code == 200
    assert env.client.delete(f"/api/media/{asset_id}").status_code == 200
    assert "media.deleted" in env.services.audit_repo.actions()


def test_editor_can_upload(env):
    pid = env.profile()
    env.accept_consent(pid)
    env.grant(pid, env.luis, "editor")
    env.login(env.luis)
    r = env.client.post(
        f"/api/profiles/{pid}/media", files={"file": ("f.jpg", _jpeg(), "image/jpeg")}
    )
    assert r.status_code == 201
    assert r.json()["uploaded_by"] == "Luis"
