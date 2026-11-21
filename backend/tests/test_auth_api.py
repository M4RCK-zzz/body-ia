from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_auth_service, get_user_admin_service
from app.main import create_app
from tests.identity_fakes import IdentityEnv, build_identity_env

PASSWORD = "Correcta-12345"


@pytest.fixture
def api() -> tuple[TestClient, IdentityEnv]:
    env = build_identity_env()
    app = create_app()
    app.dependency_overrides[get_auth_service] = lambda: env.auth
    app.dependency_overrides[get_user_admin_service] = lambda: env.admin
    return TestClient(app), env


def _register_and_login(client: TestClient, email: str = "ana@example.com") -> str:
    body = {"email": email, "password": PASSWORD, "full_name": "Ana Pérez"}
    assert client.post("/api/auth/register", json=body).status_code == 201
    login = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200
    return login.json()["access_token"]


def test_register_login_me_flow_never_leaks_password(api):
    client, _ = api
    token = _register_and_login(client)
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "ana@example.com"
    assert me.json()["roles"] == ["user"]
    assert "password" not in me.text


def test_me_without_token_is_401_with_challenge(api):
    client, _ = api
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["error"]["code"] == "missing_token"


def test_weak_password_is_422(api):
    client, _ = api
    response = client.post(
        "/api/auth/register",
        json={"email": "ana@example.com", "password": "solo-letras-largas", "full_name": "Ana"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_wrong_credentials_are_401(api):
    client, _ = api
    _register_and_login(client)
    response = client.post(
        "/api/auth/login", json={"email": "ana@example.com", "password": "otra-clave-1"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


def test_regular_user_cannot_use_admin_endpoints(api):
    client, _ = api
    token = _register_and_login(client)
    response = client.get("/api/admin/users", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


def test_admin_can_list_users_and_read_audit(api):
    client, env = api
    env.users.create(
        email="admin@example.com",
        password_hash=env.hasher.hash(PASSWORD),
        full_name="Admin",
        role_names=["admin"],
    )
    token = client.post(
        "/api/auth/login", json={"email": "admin@example.com", "password": PASSWORD}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    users = client.get("/api/admin/users", headers=headers)
    assert users.status_code == 200
    assert users.json()["total"] == 1

    audit = client.get("/api/admin/audit-events", params={"action": "auth.login"}, headers=headers)
    assert audit.status_code == 200
    assert audit.json()["total"] == 1