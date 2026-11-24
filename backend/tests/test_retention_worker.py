"""Worker de retención (Fase 9): DRY RUN, purga real y garantías de no daño.

La regla que no se negocia: `measurements`, `pose_analyses` y `audit_events` no se
tocan nunca. El worker ni siquiera tiene repositorios de esas tablas.
"""

from __future__ import annotations

import hashlib
from datetime import timedelta
from decimal import Decimal

from app.core.config import Settings
from app.domain.identity import AuditAction
from app.domain.measurements import (
    MeasurementMethod,
    MeasurementType,
    MeasurementUnit,
    NewMeasurement,
)
from app.workers.retention_worker import RetentionWorker
from tests.fakes import build_services
from tests.test_simulation_service import profile_with_consent, seed

BASE = {
    "database_url": "postgresql+psycopg://u:p@localhost:5432/db",
    "jwt_secret": "x" * 48,
    "cors_origins": "http://localhost:5173",
}


def _settings(**overrides) -> Settings:
    return Settings(**{**BASE, **overrides})


def _measurements_fingerprint(svc) -> str:
    rows = sorted(
        (str(m.profile_id), m.metric_type, str(m.value), m.measured_at.isoformat())
        for m in svc.measurements_repo.items
    )
    return hashlib.sha256(repr(rows).encode()).hexdigest()


def _env(settings: Settings | None = None):
    svc = build_services()
    ana = svc.new_user("ana")
    pid = profile_with_consent(svc, ana)
    seed(svc, ana, pid)
    worker = RetentionWorker(
        settings or _settings(),
        media_repo=svc.media_repo,
        report_repo=svc.reports_repo,
        simulation_repo=svc.simulations_repo,
        storage=svc.storage,
        audit=svc.audit,
        tx=svc.tx,
        clock=svc.clock,
    )
    return svc, ana, pid, worker


def test_dry_run_is_the_default_and_changes_nothing() -> None:
    svc, ana, pid, worker = _env()
    assert worker._settings.retention_dry_run is True

    asset = svc.media.upload(
        ana,
        pid,
        data=_png_bytes(),
        declared_mime="image/png",
    )
    asset.retention_until = svc.clock() - timedelta(days=1)
    fingerprint = _measurements_fingerprint(svc)

    report = worker.run_once()

    assert report.dry_run is True
    assert report.media == 1  # lo detecta…
    assert svc.media_repo.get(asset.id).status == "ready"  # …pero no lo toca
    assert svc.storage.exists(asset.storage_key)
    assert _measurements_fingerprint(svc) == fingerprint


def test_apply_purges_expired_media_and_audits() -> None:
    svc, ana, pid, worker = _env(_settings(retention_dry_run=False))
    asset = svc.media.upload(ana, pid, data=_png_bytes(), declared_mime="image/png")
    key = asset.storage_key
    asset.retention_until = svc.clock() - timedelta(days=1)
    fingerprint = _measurements_fingerprint(svc)

    report = worker.run_once()

    assert report.media == 1
    assert report.dry_run is False
    assert svc.media_repo.get(asset.id).status == "deleted"
    assert not svc.storage.exists(key)
    assert _measurements_fingerprint(svc) == fingerprint
    actions = [event.action for event in svc.audit_repo.events]
    assert str(AuditAction.MEDIA_PURGED) in actions


def test_unexpired_media_is_kept() -> None:
    svc, ana, pid, worker = _env(_settings(retention_dry_run=False))
    asset = svc.media.upload(ana, pid, data=_png_bytes(), declared_mime="image/png")

    assert worker.run_once().media == 0
    assert svc.media_repo.get(asset.id).status == "ready"
    assert svc.storage.exists(asset.storage_key)


def test_observations_are_out_of_reach() -> None:
    """`measurements` no cambia ni cuando el worker purga de verdad."""
    svc, ana, pid, worker = _env(_settings(retention_dry_run=False))
    before = _measurements_fingerprint(svc)
    count = len(svc.measurements_repo.items)

    worker.run_once()

    assert _measurements_fingerprint(svc) == before
    assert len(svc.measurements_repo.items) == count
    # Una medición nueva sigue siendo posible: la base está intacta.
    svc.measurements.record(
        ana,
        pid,
        NewMeasurement(
            metric_type=MeasurementType.WEIGHT,
            value=Decimal("79.00"),
            unit=MeasurementUnit.KG,
            measured_at=svc.clock(),
            method=MeasurementMethod.SCALE,
            created_by="Ana",
        ),
    )
    assert len(svc.measurements_repo.items) == count + 1


def test_archived_simulation_result_is_cleared_but_baseline_kept() -> None:
    svc, ana, pid, worker = _env(_settings(retention_dry_run=False))
    created = svc.simulations.create(
        ana,
        pid,
        label="Escenario viejo",
        parameters=[{"metric_type": "waist", "mode": "delta_absolute", "value": "-4"}],
        run_now=True,
    )[0]
    svc.simulations_repo.get(created.id).status = "archived"
    svc.simulations_repo.get(created.id).archived_at = svc.clock() - timedelta(days=400)
    svc.simulations_repo.get(created.id).result_json = {"metrics": {}}
    baselines_before = len(svc.simulations_repo.baselines)

    report = worker.run_once()

    assert report.simulations == 1
    assert svc.simulations_repo.get(created.id).result_json is None
    assert len(svc.simulations_repo.baselines) == baselines_before  # traza conservada


def _png_bytes() -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
        b"\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05"
        b"\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
