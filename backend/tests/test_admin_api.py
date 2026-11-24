"""Panel de administración (Fase 10): filtros nuevos y reglas de seguridad.

La UI de Administración consume `/api/admin/*`. Estos tests fijan el contrato
extendido (búsqueda, rol, estado, actor y rango de fechas) y, sobre todo, que
`admin` **no** gana acceso a expedientes por el hecho de tener el rol.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_auth_service, get_user_admin_service
from app.main import create_app

PASSWORD = "clave-segura-123"


@pytest.fixture()
def api(monkeypatch):
    from tests.identity_fakes import build_identity_env

    monkeypatch.setenv("JWT_SECRET", "s" * 40)
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173")
    env = build_identity_env()
    app = create_app()
    app.dependency_overrides[get_auth_service] = lambda: env.auth
    app.dependency_overrides[get_user_admin_service] = lambda: env.admin
    with TestClient(app) as client:
        yield client, env


def _user(env, email: str, name: str, roles: list[str]):
    return env.users.create(
        email=email, password_hash=env.hasher.hash(PASSWORD), full_name=name, role_names=roles
    )


def _headers(client: TestClient, email: str) -> dict[str, str]:
    token = client.post("/api/auth/login", json={"email": email, "password": PASSWORD}).json()[
        "access_token"
    ]
    return {"Authorization": f"Bearer {token}"}


def _admin(env) -> str:
    return _user(env, "root@example.com", "Raíz", ["admin"]).email


def test_only_admin_reaches_the_panel(api):
    client, env = api
    _admin(env)
    _user(env, "ana@example.com", "Ana", ["user"])
    headers = _headers(client, "ana@example.com")

    for path in ("/api/admin/users", "/api/admin/audit-events", "/api/admin/audit-actions"):
        response = client.get(path, headers=headers)
        assert response.status_code == 403, path
        assert response.json()["error"]["code"] == "forbidden"


def test_admin_without_token_is_401(api):
    client, _ = api
    assert client.get("/api/admin/users").status_code == 401


def test_user_search_by_name_and_email(api):
    client, env = api
    headers = _headers(client, _admin(env))
    _user(env, "ana@example.com", "Ana Torres", ["user"])
    _user(env, "luis@example.com", "Luis Pérez", ["professional"])

    by_name = client.get("/api/admin/users", params={"search": "torres"}, headers=headers)
    assert by_name.status_code == 200
    assert [u["email"] for u in by_name.json()["items"]] == ["ana@example.com"]
    assert by_name.json()["total"] == 1

    by_email = client.get("/api/admin/users", params={"search": "luis@"}, headers=headers)
    assert [u["email"] for u in by_email.json()["items"]] == ["luis@example.com"]

    everything = client.get("/api/admin/users", params={"search": ""}, headers=headers)
    assert everything.json()["total"] == 3


def test_user_filters_by_role_and_active_state(api):
    client, env = api
    _admin_user = _user(env, "root@example.com", "Raíz", ["admin"])
    headers = _headers(client, "root@example.com")
    ana = _user(env, "ana@example.com", "Ana Torres", ["user"])
    _user(env, "luis@example.com", "Luis Pérez", ["professional"])
    env.admin.set_active(actor=_admin_user, user_id=ana.id, active=False)

    admins = client.get("/api/admin/users", params={"role": "admin"}, headers=headers)
    assert [u["email"] for u in admins.json()["items"]] == ["root@example.com"]
    assert admins.json()["total"] == 1

    inactive = client.get("/api/admin/users", params={"is_active": "false"}, headers=headers)
    assert [u["email"] for u in inactive.json()["items"]] == ["ana@example.com"]

    active = client.get("/api/admin/users", params={"is_active": "true"}, headers=headers)
    assert active.json()["total"] == 2


def test_unknown_role_filter_is_422(api):
    client, env = api
    headers = _headers(client, _admin(env))
    response = client.get("/api/admin/users", params={"role": "superuser"}, headers=headers)
    assert response.status_code == 422


def test_pagination_metadata_is_consistent(api):
    client, env = api
    headers = _headers(client, _admin(env))
    for index in range(3):
        _user(env, f"user{index}@example.com", f"Usuario {index}", ["user"])

    page = client.get(
        "/api/admin/users", params={"limit": 2, "offset": 2}, headers=headers
    ).json()
    assert page["limit"] == 2 and page["offset"] == 2
    assert page["total"] == 4
    assert len(page["items"]) == 2


def test_admin_cannot_deactivate_self(api):
    client, env = api
    headers = _headers(client, _admin(env))
    me = client.get("/api/auth/me", headers=headers).json()

    response = client.post(f"/api/admin/users/{me['id']}/deactivate", headers=headers)
    assert response.status_code == 422
    assert "desactivar tu propia cuenta" in response.json()["error"]["message"]


def test_admin_cannot_remove_own_admin_role(api):
    client, env = api
    headers = _headers(client, _admin(env))
    me = client.get("/api/auth/me", headers=headers).json()

    response = client.put(
        f"/api/admin/users/{me['id']}/roles", json={"roles": ["user"]}, headers=headers
    )
    assert response.status_code == 422
    assert "administrador" in response.json()["error"]["message"]


def test_roles_change_is_audited_and_applied(api):
    client, env = api
    headers = _headers(client, _admin(env))
    ana = _user(env, "ana@example.com", "Ana", ["user"])

    response = client.put(
        f"/api/admin/users/{ana.id}/roles",
        json={"roles": ["user", "professional"]},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["roles"] == ["professional", "user"]

    events = client.get(
        "/api/admin/audit-events", params={"action": "admin.roles_changed"}, headers=headers
    ).json()
    assert events["total"] == 1
    assert events["items"][0]["detail"]["after"] == ["professional", "user"]


def test_audit_events_resolve_actor_names(api):
    client, env = api
    email = _admin(env)
    headers = _headers(client, email)

    page = client.get("/api/admin/audit-events", headers=headers).json()
    actors = {actor["email"]: actor for actor in page["actors"]}
    assert email in actors
    assert actors[email]["full_name"] == "Raíz"
    # Solo id, correo y nombre: el panel no necesita el hash ni los roles del actor.
    assert set(actors[email]) == {"id", "email", "full_name"}


def test_audit_filters_by_actor_action_and_dates(api):
    client, env = api
    headers = _headers(client, _admin(env))
    ana = _user(env, "ana@example.com", "Ana", ["user"])
    me = client.get("/api/auth/me", headers=headers).json()

    # Genera un evento de un actor distinto (login fallido queda anotado).
    client.post("/api/auth/login", json={"email": ana.email, "password": "incorrecta-1234"})

    mine = client.get(
        "/api/admin/audit-events", params={"actor_user_id": me["id"]}, headers=headers
    ).json()
    assert mine["total"] >= 1
    assert all(item["actor_user_id"] == me["id"] for item in mine["items"])

    other = client.get(
        "/api/admin/audit-events", params={"actor_user_id": str(ana.id)}, headers=headers
    ).json()
    assert other["total"] >= 1

    # El reloj del entorno de pruebas es fijo: el rango se calcula sobre él.
    now = env.clock()
    future = client.get(
        "/api/admin/audit-events",
        params={"since": (now + timedelta(days=1)).isoformat()},
        headers=headers,
    ).json()
    assert future["total"] == 0

    window = client.get(
        "/api/admin/audit-events",
        params={
            "since": (now - timedelta(days=1)).isoformat(),
            "until": (now + timedelta(minutes=5)).isoformat(),
        },
        headers=headers,
    ).json()
    assert window["total"] >= 1

    expired = client.get(
        "/api/admin/audit-events",
        params={"until": (now - timedelta(days=1)).isoformat()},
        headers=headers,
    ).json()
    assert expired["total"] == 0


def test_audit_actions_endpoint_feeds_the_filter(api):
    client, env = api
    headers = _headers(client, _admin(env))
    actions = client.get("/api/admin/audit-actions", headers=headers).json()["actions"]
    assert "auth.login" in actions
    assert actions == sorted(actions)


def test_audit_action_filter_with_no_matches_is_empty(api):
    client, env = api
    headers = _headers(client, _admin(env))
    page = client.get(
        "/api/admin/audit-events", params={"action": "simulation.purged"}, headers=headers
    ).json()
    assert page["total"] == 0
    assert page["items"] == []


def test_admin_listing_never_exposes_profile_data(api):
    """El panel gestiona cuentas y roles; la UI lo dice y el contrato lo cumple.

    `admin` no gana acceso a expedientes (eso lo fija `test_access_guard.py`), y
    el listado de usuarios no incluye ningún dato corporal ni identificador de
    expediente: solo identidad y roles.
    """
    client, env = api
    headers = _headers(client, _admin(env))
    _user(env, "ana@example.com", "Ana", ["user"])

    page = client.get("/api/admin/users", headers=headers).json()
    allowed = {
        "id",
        "email",
        "full_name",
        "roles",
        "is_active",
        "created_at",
        "last_login_at",
    }
    for item in page["items"]:
        assert set(item) <= allowed


def test_date_range_requires_valid_iso_dates(api):
    client, env = api
    headers = _headers(client, _admin(env))
    response = client.get(
        "/api/admin/audit-events", params={"since": "ayer"}, headers=headers
    )
    assert response.status_code == 422
