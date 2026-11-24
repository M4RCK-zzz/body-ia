from __future__ import annotations

import hashlib
from datetime import timedelta
from decimal import Decimal
from uuid import UUID

import pytest

from app.core.errors import BusinessRuleError
from app.core.security_errors import ConsentRequiredError, PermissionDeniedError
from app.domain.measurements import (
    MeasurementCorrection,
    MeasurementMethod,
    MeasurementType,
    MeasurementUnit,
    NewMeasurement,
)
from app.domain.simulation import SimulationStatus
from app.models.measurement import Measurement
from app.workers.simulation_worker import SimulationWorker
from tests.fakes import build_services

BASE = None  # se define perezosamente para no duplicar la constante de Fase 7


def _settings():
    from app.core.config import Settings

    return Settings(
        database_url="postgresql+psycopg://test:test@localhost:5432/test",
        jwt_secret="test-secret-only-for-pytest-0123456789-abcdef",
        simulation_poll_seconds=1,
        simulation_stale_processing_seconds=600,
        simulation_max_delta_percent=30,
        simulation_max_active_per_profile=20,
    )


def env():
    return build_services()


def seed(env, owner, pid, values=None):
    pid = UUID(str(pid))
    values = values or {
        MeasurementType.WEIGHT: "80.00",
        MeasurementType.HEIGHT: "170.00",
        MeasurementType.WAIST: "88.00",
        MeasurementType.HIP: "100.00",
    }
    for index, (metric, value) in enumerate(values.items()):
        env.measurements.record(
            owner,
            pid,
            NewMeasurement(
                metric_type=metric,
                value=Decimal(value),
                unit=MeasurementUnit.KG
                if metric is MeasurementType.WEIGHT
                else MeasurementUnit.CM,
                measured_at=env.clock() - timedelta(days=len(values) - index),
                method=MeasurementMethod.SCALE,
                created_by=owner.full_name,
            ),
        )


def profile_with_consent(env, owner, code="BV-001"):
    pid = env.profile_for(owner, code)
    env.accept_consent(owner, pid)
    return pid


def worker(env, now=None):
    return SimulationWorker(
        _settings(),
        simulation_repo=env.simulations_repo,
        audit=env.audit,
        tx=env.tx,
        clock=(lambda: now) if now else env.clock,
    )


def create(env, owner, pid, **kwargs):
    payload = {
        "label": "Escenario A",
        "parameters": [
            {"metric_type": "waist", "mode": "delta_absolute", "value": "-4.40"}
        ],
    }
    payload.update(kwargs)
    return env.simulations.create(owner, pid, **payload)


# --- helpers para no contaminar mediciones -----------------------------------------


def measurement_fingerprint(env, pid):
    rows = sorted(
        (str(m.id), m.metric_type, str(m.value), m.unit, m.measured_at.isoformat())
        for m in env.measurements_repo.items
        if str(m.profile_id) == str(pid)
    )
    payload = "|".join(";".join(row) for row in rows)
    return len(rows), hashlib.sha256(payload.encode()).hexdigest()


class TestCreate:
    def test_queued_by_default(self):
        env_ = env()
        owner = env_.new_user("ana")
        pid = profile_with_consent(env_, owner)
        seed(env_, owner, pid)

        simulation, created = create(env_, owner, pid)

        assert created is True
        assert simulation.status == SimulationStatus.QUEUED.value
        assert simulation.data_kind == "simulation"
        assert simulation.engine_version == "1.0.0"
        assert simulation.queued_at is not None
        assert simulation.baseline_hash and len(simulation.baseline_hash) == 64
        assert "simulation.created" in env_.audit_repo.actions()
        assert "simulation.queued" in env_.audit_repo.actions()

    def test_draft_when_not_run(self):
        env_ = env()
        owner = env_.new_user("ana")
        pid = profile_with_consent(env_, owner)
        seed(env_, owner, pid)

        simulation, _ = create(env_, owner, pid, run_now=False)

        assert simulation.status == SimulationStatus.DRAFT.value
        assert simulation.queued_at is None

    def test_baseline_rows_snapshot_values(self):
        env_ = env()
        owner = env_.new_user("ana")
        pid = profile_with_consent(env_, owner)
        seed(env_, owner, pid)

        simulation, _ = create(env_, owner, pid)

        rows = env_.simulations_repo.baselines_for(simulation.id)
        # La base guarda la métrica simulada y los componentes de los derivados.
        assert [row.metric_type for row in rows] == ["height", "hip", "waist"]
        waist = next(row for row in rows if row.metric_type == "waist")
        assert waist.value_snapshot == Decimal("88.00")
        assert waist.unit == "cm"

    def test_requires_editor(self):
        env_ = env()
        owner = env_.new_user("ana")
        viewer = env_.new_user("beto")
        pid = profile_with_consent(env_, owner)
        seed(env_, owner, pid)
        env_.grant_direct(pid, viewer, "viewer")

        with pytest.raises(PermissionDeniedError):
            create(env_, viewer, pid)

    def test_requires_valid_consent(self):
        env_ = env()
        owner = env_.new_user("ana")
        pid = env_.profile_for(owner)
        for metric, value in {
            MeasurementType.WEIGHT: "80.00",
            MeasurementType.HEIGHT: "170.00",
            MeasurementType.WAIST: "88.00",
            MeasurementType.HIP: "100.00",
        }.items():
            env_.measurements_repo.add(
                Measurement(
                    profile_id=pid,
                    metric_type=metric.value,
                    value=Decimal(value),
                    unit="kg" if metric is MeasurementType.WEIGHT else "cm",
                    measured_at=env_.clock(),
                    method=MeasurementMethod.SCALE.value,
                    created_by=owner.full_name,
                )
            )

        with pytest.raises(ConsentRequiredError):
            create(env_, owner, pid)

    def test_requires_active_profile(self):
        env_ = env()
        owner = env_.new_user("ana")
        pid = profile_with_consent(env_, owner)
        seed(env_, owner, pid)
        env_.profiles.archive(owner, pid)

        with pytest.raises(BusinessRuleError):
            create(env_, owner, pid)

    def test_missing_metric_has_clear_error(self):
        env_ = env()
        owner = env_.new_user("ana")
        pid = profile_with_consent(env_, owner)
        seed(env_, owner, pid)

        with pytest.raises(BusinessRuleError, match="No hay medición vigente"):
            create(
                env_,
                owner,
                pid,
                parameters=[
                    {"metric_type": "chest", "mode": "delta_absolute", "value": "-3"}
                ],
            )

    def test_rejects_delta_over_limit(self):
        env_ = env()
        owner = env_.new_user("ana")
        pid = profile_with_consent(env_, owner)
        seed(env_, owner, pid)

        with pytest.raises(BusinessRuleError, match="supera"):
            create(
                env_,
                owner,
                pid,
                parameters=[
                    {"metric_type": "waist", "mode": "delta_percent", "value": "-45"}
                ],
            )

    def test_rejects_blank_label(self):
        env_ = env()
        owner = env_.new_user("ana")
        pid = profile_with_consent(env_, owner)
        seed(env_, owner, pid)

        with pytest.raises(BusinessRuleError):
            create(env_, owner, pid, label="   ")

    def test_active_limit(self):
        env_ = env()
        owner = env_.new_user("ana")
        pid = profile_with_consent(env_, owner)
        seed(env_, owner, pid)

        for index in range(20):
            create(env_, owner, pid, label=f"Escenario {index}")

        with pytest.raises(BusinessRuleError, match="límite"):
            create(env_, owner, pid, label="Escenario 21")


class TestNoContamination:
    """El requisito central: simular no toca las mediciones observadas."""

    def test_measurements_are_byte_identical_after_create_and_run(self):
        env_ = env()
        owner = env_.new_user("ana")
        pid = profile_with_consent(env_, owner)
        seed(env_, owner, pid)
        before = measurement_fingerprint(env_, pid)

        create(env_, owner, pid)
        worker(env_).run_once()

        assert measurement_fingerprint(env_, pid) == before

    def test_analytics_unchanged(self):
        env_ = env()
        owner = env_.new_user("ana")
        pid = profile_with_consent(env_, owner)
        seed(env_, owner, pid)
        before = env_.analytics.summary(owner, pid, record_audit=False)

        create(env_, owner, pid)
        worker(env_).run_once()

        after = env_.analytics.summary(owner, pid, record_audit=False)
        assert before.total_measurements == after.total_measurements
        assert [t.last_value for t in before.trends] == [t.last_value for t in after.trends]

    def test_measurement_count_unchanged(self):
        env_ = env()
        owner = env_.new_user("ana")
        pid = profile_with_consent(env_, owner)
        seed(env_, owner, pid)
        before = env_.analytics_repo.measurement_count(pid)

        create(env_, owner, pid)
        worker(env_).run_once()

        assert env_.analytics_repo.measurement_count(pid) == before

    def test_simulation_is_not_a_measurement_record(self):
        env_ = env()
        owner = env_.new_user("ana")
        pid = profile_with_consent(env_, owner)
        seed(env_, owner, pid)
        before = len(env_.measurements_repo.items)

        create(env_, owner, pid)
        worker(env_).run_once()

        assert len(env_.measurements_repo.items) == before
        # Ningún valor del escenario aparece en la tabla de mediciones.
        values = {str(m.value) for m in env_.measurements_repo.items}
        assert "83.60" not in values

    def test_corrected_measurement_becomes_new_baseline_not_mutated(self):
        env_ = env()
        owner = env_.new_user("ana")
        pid = profile_with_consent(env_, owner)
        seed(env_, owner, pid)
        original = next(m for m in env_.measurements_repo.items if m.metric_type == "waist")

        first, _ = create(env_, owner, pid)
        worker(env_).run_once()

        env_.measurements.correct(
            owner,
            pid,
            original.id,
            MeasurementCorrection(
                value=Decimal("86.00"), created_by=owner.full_name, reason="error de captura"
            ),
        )
        second, _ = create(env_, owner, pid, label="Escenario B")
        worker(env_).run_once()

        # El escenario antiguo conserva su base y se marca que cambió después.
        comparison = env_.simulations.comparison(owner, first.id)
        waist_row = next(
            row for row in comparison["baseline"]["metrics"] if row["metric_type"] == "waist"
        )
        assert waist_row["value"] == 88.0
        assert waist_row["superseded_since"] is True
        # El nuevo escenario parte de la medición vigente corregida.
        second_waist = next(
            row for row in env_.simulations_repo.baselines_for(second.id)
            if row.metric_type == "waist"
        )
        assert second_waist.value_snapshot == Decimal("86.00")
        # La medición original sigue intacta (inmutable).
        assert original.value == Decimal("88.00")


class TestWorker:
    def _queued(self, env_, owner, pid):
        simulation, _ = create(env_, owner, pid)
        return simulation

    def test_completes_with_result_and_checksum(self):
        env_ = env()
        owner = env_.new_user("ana")
        pid = profile_with_consent(env_, owner)
        seed(env_, owner, pid)
        simulation = self._queued(env_, owner, pid)

        assert worker(env_).run_once() is True

        assert simulation.status == SimulationStatus.COMPLETED.value
        assert simulation.completed_at is not None
        assert simulation.started_at is not None
        assert simulation.result_checksum and len(simulation.result_checksum) == 64
        metrics = simulation.result_json["metrics"]
        assert metrics["waist"]["simulated"] == "83.60"
        assert simulation.result_json["data_kind"] == "simulation"
        assert "simulation.completed" in env_.audit_repo.actions()

    def test_twice_run_is_idempotent(self):
        env_ = env()
        owner = env_.new_user("ana")
        pid = profile_with_consent(env_, owner)
        seed(env_, owner, pid)
        simulation = self._queued(env_, owner, pid)

        worker(env_).run_once()
        checksum = simulation.result_checksum
        assert worker(env_).run_once() is False
        assert simulation.result_checksum == checksum

    def test_no_pending_returns_false(self):
        assert worker(env()).run_once() is False

    def test_baseline_tampering_fails_the_scenario(self):
        env_ = env()
        owner = env_.new_user("ana")
        pid = profile_with_consent(env_, owner)
        seed(env_, owner, pid)
        simulation = self._queued(env_, owner, pid)
        env_.simulations_repo.baselines_for(simulation.id)[0].value_snapshot = Decimal("70.00")

        worker(env_).run_once()

        assert simulation.status == SimulationStatus.FAILED.value
        assert "integridad" in simulation.error_message
        assert "simulation.failed" in env_.audit_repo.actions()

    def test_stale_queue_is_failed(self):
        env_ = env()
        owner = env_.new_user("ana")
        pid = profile_with_consent(env_, owner)
        seed(env_, owner, pid)
        simulation = self._queued(env_, owner, pid)
        simulation.queued_at = env_.clock() - timedelta(days=2)

        assert worker(env_).mark_stale() == 1
        assert simulation.status == SimulationStatus.FAILED.value
        assert simulation.error_message == "queue_stale"


class TestRunArchiveList:
    def test_run_draft(self):
        env_ = env()
        owner = env_.new_user("ana")
        pid = profile_with_consent(env_, owner)
        seed(env_, owner, pid)
        simulation, _ = create(env_, owner, pid, run_now=False)

        assert env_.simulations.run(owner, simulation.id).status == "queued"
        with pytest.raises(BusinessRuleError):
            env_.simulations.run(owner, simulation.id)

    def test_archive_completed(self):
        env_ = env()
        owner = env_.new_user("ana")
        pid = profile_with_consent(env_, owner)
        seed(env_, owner, pid)
        simulation, _ = create(env_, owner, pid)
        worker(env_).run_once()

        archived = env_.simulations.archive(owner, simulation.id)

        assert archived.status == SimulationStatus.ARCHIVED.value
        assert archived.archived_at is not None
        assert archived.result_json is not None  # el resultado no se pierde
        assert "simulation.archived" in env_.audit_repo.actions()

    def test_archive_draft_does_not_invent_result(self):
        env_ = env()
        owner = env_.new_user("ana")
        pid = profile_with_consent(env_, owner)
        seed(env_, owner, pid)
        simulation, _ = create(env_, owner, pid, run_now=False)

        archived = env_.simulations.archive(owner, simulation.id)

        assert archived.status == "archived"
        assert archived.result_json is None
        assert archived.completed_at is None

    def test_archived_hidden_by_default(self):
        env_ = env()
        owner = env_.new_user("ana")
        pid = profile_with_consent(env_, owner)
        seed(env_, owner, pid)
        simulation, _ = create(env_, owner, pid)
        worker(env_).run_once()
        env_.simulations.archive(owner, simulation.id)

        rows, total = env_.simulations.list_for_profile(owner, pid)
        archived_rows, archived_total = env_.simulations.list_for_profile(
            owner, pid, include_archived=True
        )

        assert total == 0 and rows == []
        assert archived_total == 1

    def test_only_author_or_owner_can_archive(self):
        env_ = env()
        owner = env_.new_user("ana")
        editor = env_.new_user("beto")
        pid = profile_with_consent(env_, owner)
        seed(env_, owner, pid)
        env_.grant_direct(pid, editor, "editor")
        simulation, _ = create(env_, editor, pid)
        worker(env_).run_once()

        assert env_.simulations.archive(editor, simulation.id).status == "archived"

        other = env_.new_user("eva")
        env_.grant_direct(pid, other, "editor")
        second, _ = create(env_, other, pid, label="Otro")
        worker(env_).run_once()

        with pytest.raises(PermissionDeniedError):
            env_.simulations.archive(editor, second.id)
        assert env_.simulations.archive(owner, second.id).status == "archived"

    def test_list_mine_hides_revoked_access(self):
        env_ = env()
        owner = env_.new_user("ana")
        editor = env_.new_user("beto")
        pid = profile_with_consent(env_, owner)
        seed(env_, owner, pid)
        env_.grant_direct(pid, editor, "editor")
        create(env_, editor, pid)

        rows, total = env_.simulations.list_mine(editor)
        assert total == 1

        env_.access_service.revoke(owner, pid, editor.id)
        assert env_.simulations.list_mine(editor)[1] == 0

    def test_comparison_shape(self):
        env_ = env()
        owner = env_.new_user("ana")
        pid = profile_with_consent(env_, owner)
        seed(env_, owner, pid)
        simulation, _ = create(env_, owner, pid)
        worker(env_).run_once()

        comparison = env_.simulations.comparison(owner, simulation.id)

        assert comparison["data_kind"] == "simulation"
        assert comparison["engine"]["version"] == "1.0.0"
        waist_row = next(
            row for row in comparison["baseline"]["metrics"] if row["metric_type"] == "waist"
        )
        assert waist_row["value"] == 88.0
        assert comparison["scenario"]["metrics"][0]["value"] == 83.6
        assert float(comparison["scenario"]["metrics"][0]["delta_absolute"]) == -4.4
        assert "waist_height" in comparison["derived"]
        assert "height" in comparison["unchanged"]
        assert "escenario hipotético" in comparison["banner"].lower()
        assert "simulation.viewed" in env_.audit_repo.actions()

    def test_limits_contract_excludes_height(self):
        contract = env().simulations.limits_contract()

        metric_types = {row["metric_type"] for row in contract["metrics"]}
        assert "height" not in metric_types
        assert {"weight", "waist", "hip", "chest", "arm", "thigh"} <= metric_types
        assert contract["max_delta_percent"] == 30.0
        assert contract["height_as_reference_only"] is True


def test_simulable_metric_types_are_known():
    assert MeasurementType.WEIGHT.value in {"weight"}
    assert MeasurementUnit.KG.value == "kg"
    assert MeasurementMethod.SCALE.value == "scale"
