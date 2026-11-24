"""Auditoría anti-IDOR (Fase 9, §3.1 del plan).

Un IDOR (Insecure Direct Object Reference) es pedir el recurso de otro usuario
cambiando un identificador. La política del sistema es uniforme desde la Fase 4:

- Sin acceso vigente al expediente → **404** (no revela existencia).
- Acceso insuficiente (p. ej. `viewer` intentando escribir) → **403**.
- `admin` **no** tiene acceso implícito a expedientes: también recibe 404.

Esta suite recorre todos los recursos con `id` propio y comprueba, con dos
usuarios y dos expedientes, que el ajeno no puede leer ni escribir, y que la
respuesta de error no filtra datos del recurso.
"""

from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.api.deps import (
    get_analytics_service,
    get_consent_service,
    get_dashboard_service,
    get_measurement_service,
    get_media_service,
    get_pose_service,
    get_profile_access_service,
    get_profile_service,
    get_report_service,
    get_simulation_service,
)
from app.api.security import get_current_user
from app.main import create_app
from app.services.dashboard_service import DashboardService
from tests.fakes import build_services

MEDIA_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
    b"\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05"
    b"\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _provider(service):
    return lambda: service


class Env:
    """Dos usuarios, dos expedientes y un recurso de cada tipo en el ajeno."""

    def __init__(self) -> None:
        self.services = build_services()
        svc = self.services
        self.app = create_app()
        deps = {
            get_profile_service: svc.profiles,
            get_profile_access_service: svc.access_service,
            get_measurement_service: svc.measurements,
            get_consent_service: svc.consent,
            get_analytics_service: svc.analytics,
            get_report_service: svc.reports,
            get_simulation_service: svc.simulations,
            get_media_service: svc.media,
            get_pose_service: svc.pose,
        }
        for dependency, service in deps.items():
            # `_provider` evita un parámetro en la firma del override: FastAPI
            # analiza la firma y un `service=` con default se trataría como
            # dependencia en lugar de valor fijo.
            self.app.dependency_overrides[dependency] = _provider(service)
        self.app.dependency_overrides[get_dashboard_service] = lambda: DashboardService(
            svc.profiles_repo, svc.analytics_repo, svc.pose_repo, svc.audit, svc.tx, clock=svc.clock
        )
        self.client = TestClient(self.app)

        self.owner = svc.new_user("ana")
        self.intruder = svc.new_user("bruno")
        self.admin = svc.new_user("carla", role="admin")

        self.owner_profile = self._profile(self.owner, "BV-ANA")
        self.other_profile = self._profile(self.owner, "BV-OTRO")
        self.intruder_profile = self._profile(self.intruder, "BV-BRU")

        self.ids = self._populate(self.owner_profile)

    # --- preparación ---

    def _profile(self, owner, code: str) -> str:
        response = self.as_user(owner).post("/api/profiles", json={"display_code": code})
        assert response.status_code == 201, response.text
        pid = response.json()["id"]
        accepted = self.as_user(owner).post(
            f"/api/profiles/{pid}/consents",
            json={"purpose": "data_processing", "declaration": True},
        )
        assert accepted.status_code == 201, accepted.text
        return pid

    def _populate(self, pid: str) -> dict[str, str]:
        client = self.as_user(self.owner)
        measurement = client.post(
            f"/api/profiles/{pid}/measurements",
            json={
                "metric_type": "weight",
                "value": "80.00",
                "unit": "kg",
                "measured_at": self.services.clock().isoformat(),
                "method": "scale",
            },
        )
        assert measurement.status_code == 201, measurement.text

        media = client.post(
            f"/api/profiles/{pid}/media",
            files={"file": ("foto.png", MEDIA_BYTES, "image/png")},
        )
        assert media.status_code == 201, media.text
        asset_id = media.json()["id"]

        pose = client.post(f"/api/media/{asset_id}/pose-analyses")
        assert pose.status_code in (201, 202), pose.text
        pose_id = pose.json()["id"]

        report = client.post(
            f"/api/profiles/{pid}/reports",
            json={"kind": "measurements_csv"},
        )
        assert report.status_code in (200, 201), report.text
        report_id = report.json()["id"]

        simulation = client.post(
            f"/api/profiles/{pid}/simulations",
            json={
                "label": "Cintura -4",
                "run_now": False,
                "metrics": [{"metric_type": "weight", "mode": "delta_absolute", "value": "-4"}],
            },
        )
        assert simulation.status_code == 201, simulation.text
        simulation_id = simulation.json()["id"]

        return {
            "measurement": measurement.json()["id"],
            "media": asset_id,
            "pose": pose_id,
            "report": report_id,
            "simulation": simulation_id,
        }

    # --- ayudas ---

    def as_user(self, user) -> TestClient:
        self.app.dependency_overrides[get_current_user] = lambda: user
        return self.client

    def ids_of(self, pid: str, kind: str) -> str:
        """Crea un recurso del tipo pedido en un expediente propio."""
        if pid == self.owner_profile:
            return self.ids[kind]
        raise AssertionError("usa el expediente preparado")


# (método, plantilla de ruta, tipo de recurso) — cada una apunta a un id real.
RESOURCE_READS = [
    ("GET", "/api/profiles/{profile}/measurements", None),
    ("GET", "/api/profiles/{profile}/measurements/series?metric_type=weight", None),
    ("GET", "/api/profiles/{profile}/analytics", None),
    ("GET", "/api/profiles/{profile}/media", None),
    ("GET", "/api/profiles/{profile}/pose-analyses", None),
    ("GET", "/api/profiles/{profile}/reports", None),
    ("GET", "/api/profiles/{profile}/simulations", None),
    ("GET", "/api/profiles/{profile}/access", None),
    ("GET", "/api/profiles/{profile}/consents", None),
    ("GET", "/api/media/{media}", None),
    ("GET", "/api/media/{media}/content", None),
    ("GET", "/api/pose-analyses/{pose}", None),
    ("GET", "/api/reports/{report}", None),
    ("GET", "/api/simulations/{simulation}", None),
    ("GET", "/api/simulations/{simulation}/comparison", None),
]


@pytest.fixture(scope="module")
def env() -> Env:
    return Env()


@pytest.mark.parametrize(("method", "template", "_kind"), RESOURCE_READS)
def test_intruder_cannot_read_other_users_resources(env: Env, method, template, _kind) -> None:
    """Sin acceso: 404 uniforme. Nunca 200 y nunca 403 (que confirmaría existencia)."""
    url = template.format(profile=env.owner_profile, **env.ids)
    response = env.as_user(env.intruder).request(method, url)

    assert response.status_code == 404, (url, response.status_code, response.text[:200])
    body = response.text
    assert env.owner_profile not in body
    assert "BV-ANA" not in body
    assert env.ids["media"] not in body
    assert env.ids["report"] not in body
    assert env.ids["simulation"] not in body


@pytest.mark.parametrize(("method", "template", "_kind"), RESOURCE_READS)
def test_admin_without_grant_gets_404(env: Env, method, template, _kind) -> None:
    """El rol `admin` no da acceso implícito a expedientes (ADR-004)."""
    url = template.format(profile=env.owner_profile, **env.ids)
    response = env.as_user(env.admin).request(method, url)
    assert response.status_code == 404, (url, response.status_code)


def test_intruder_cannot_write_into_other_profile(env: Env) -> None:
    pid = env.owner_profile
    client = env.as_user(env.intruder)
    payload = {
        "metric_type": "weight",
        "value": "70.00",
        "unit": "kg",
        "measured_at": env.services.clock().isoformat(),
        "method": "scale",
    }
    assert client.post(f"/api/profiles/{pid}/measurements", json=payload).status_code == 404
    assert (
        client.post(
            f"/api/profiles/{pid}/media", files={"file": ("x.png", MEDIA_BYTES, "image/png")}
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/profiles/{pid}/simulations",
            json={
                "label": "x",
                "run_now": False,
                "metrics": [{"metric_type": "weight", "mode": "delta_absolute", "value": "-1"}],
            },
        ).status_code
        == 404
    )
    assert client.delete(f"/api/media/{env.ids['media']}").status_code == 404
    assert client.post(f"/api/simulations/{env.ids['simulation']}/run").status_code == 404


def test_viewer_can_read_but_not_write(env: Env) -> None:
    """Acceso insuficiente es 403 con código estable, no 404 (el viewer sí ve el perfil)."""
    pid = env.owner_profile
    viewer = env.services.new_user("dora")
    env.services.grant_direct(UUID(pid), viewer, "viewer")

    client = env.as_user(viewer)
    assert client.get(f"/api/profiles/{pid}/measurements").status_code == 200
    response = client.post(
        f"/api/profiles/{pid}/simulations",
        json={
            "label": "x",
            "run_now": False,
            "metrics": [{"metric_type": "weight", "mode": "delta_absolute", "value": "-1"}],
        },
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "insufficient_access"


def test_own_resources_are_reachable(env: Env) -> None:
    """Control positivo: el dueño sí lee lo suyo (la suite no pasa por estar roto todo)."""
    pid = env.owner_profile
    client = env.as_user(env.owner)
    assert client.get(f"/api/profiles/{pid}/measurements").status_code == 200
    assert client.get(f"/api/media/{env.ids['media']}").status_code == 200
    assert client.get(f"/api/reports/{env.ids['report']}").status_code == 200
    assert client.get(f"/api/simulations/{env.ids['simulation']}").status_code == 200


def test_intruder_does_not_see_other_profiles_in_listings(env: Env) -> None:
    """Los listados globales no incluyen expedientes ajenos."""
    client = env.as_user(env.intruder)
    codes = {row["display_code"] for row in client.get("/api/profiles").json()["items"]}
    assert codes == {"BV-BRU"}

    reports = client.get("/api/reports").json()["items"]
    assert all(row["profile_id"] != env.owner_profile for row in reports)

    simulations = client.get("/api/simulations").json()["items"]
    assert all(row["profile_id"] != env.owner_profile for row in simulations)


def test_revoked_access_loses_read_and_is_audited(env: Env) -> None:
    """Revocar el acceso devuelve 404 inmediato y deja `access.denied` en auditoría."""
    pid = env.owner_profile
    viewer = env.services.new_user("eva")
    env.services.grant_direct(UUID(pid), viewer, "editor")
    client = env.as_user(viewer)
    assert client.get(f"/api/profiles/{pid}/measurements").status_code == 200

    env.services.access_service.revoke(env.owner, UUID(pid), viewer.id)
    assert client.get(f"/api/profiles/{pid}/measurements").status_code == 404

    actions = [event.action for event in env.services.audit_repo.events]
    assert "access.denied" in actions
