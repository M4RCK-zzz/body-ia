from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.core.errors import BusinessRuleError, ConflictError, NotFoundError
from app.core.security_errors import ConsentRequiredError, PermissionDeniedError
from app.domain.access import AccessLevel, ConsentPurpose
from app.domain.measurements import (
    MeasurementCorrection,
    MeasurementMethod,
    MeasurementType,
    MeasurementUnit,
    NewMeasurement,
)
from tests.fakes import build_services

NOW = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)


def make(**overrides) -> NewMeasurement:
    base = {
        "metric_type": MeasurementType.WEIGHT,
        "value": Decimal("72.50"),
        "unit": MeasurementUnit.KG,
        "measured_at": NOW - timedelta(days=1),
        "method": MeasurementMethod.SCALE,
        "created_by": "Ana",
        "notes": None,
    }
    base.update(overrides)
    return NewMeasurement(**base)


def correction(value: str = "71.80", **overrides) -> MeasurementCorrection:
    base = {"value": Decimal(value), "created_by": "Luis", "reason": "Lectura errónea"}
    base.update(overrides)
    return MeasurementCorrection(**base)


@pytest.fixture
def env():
    """Servicios, propietaria (Ana) y un expediente activo con consentimiento vigente."""
    s = build_services(clock=lambda: NOW)
    ana = s.new_user("ana")
    pid = s.profile_for(ana)
    s.accept_consent(ana, pid)
    return s, ana, pid


# ---------- validaciones de dominio (cobertura original) ----------


def test_record_valid_measurement(env):
    s, ana, pid = env
    view = s.measurements.record(ana, pid, make())
    assert view.is_current is True
    assert view.measurement.value == Decimal("72.50")
    assert view.measurement.unit == "kg"
    assert view.measurement.method == "scale"


def test_rejects_value_out_of_range(env):
    s, ana, pid = env
    with pytest.raises(BusinessRuleError):
        s.measurements.record(ana, pid, make(value=Decimal("900")))


def test_rejects_unit_mismatch(env):
    s, ana, pid = env
    with pytest.raises(BusinessRuleError):
        s.measurements.record(
            ana,
            pid,
            make(metric_type=MeasurementType.WAIST, value=Decimal("80"), unit=MeasurementUnit.KG),
        )


def test_rejects_future_measured_at(env):
    s, ana, pid = env
    with pytest.raises(BusinessRuleError):
        s.measurements.record(ana, pid, make(measured_at=NOW + timedelta(hours=1)))


def test_rejects_archived_profile(env):
    s, ana, pid = env
    s.profiles.archive(ana, pid)
    with pytest.raises(BusinessRuleError):
        s.measurements.record(ana, pid, make())


def test_correction_is_non_destructive_and_author_is_the_actor(env):
    s, ana, pid = env
    luis = s.new_user("luis")
    s.grant_direct(pid, luis, AccessLevel.EDITOR)
    original = s.measurements.record(ana, pid, make()).measurement
    corrected = s.measurements.correct(
        luis, pid, original.id, correction(created_by="Impostor")
    ).measurement
    assert original.value == Decimal("72.50")
    assert corrected.value == Decimal("71.80")
    assert corrected.supersedes_id == original.id
    assert corrected.correction_reason == "Lectura errónea"
    assert corrected.created_by == "Luis"  # del actor, no del payload
    assert corrected.created_by_user_id == luis.id
    assert len(s.measurements_repo.items) == 2


def test_second_correction_of_same_original_conflicts(env):
    s, ana, pid = env
    original = s.measurements.record(ana, pid, make()).measurement
    s.measurements.correct(ana, pid, original.id, correction())
    with pytest.raises(ConflictError):
        s.measurements.correct(ana, pid, original.id, correction("70.00"))


def test_history_returns_chain_in_order(env):
    s, ana, pid = env
    v1 = s.measurements.record(ana, pid, make()).measurement
    v2 = s.measurements.correct(ana, pid, v1.id, correction("71.80")).measurement
    v3 = s.measurements.correct(ana, pid, v2.id, correction("71.20")).measurement
    chain = s.measurements.history(ana, pid, v2.id)
    assert [v.measurement.id for v in chain] == [v1.id, v2.id, v3.id]
    assert [v.is_current for v in chain] == [False, False, True]


def test_list_hides_superseded_by_default(env):
    s, ana, pid = env
    original = s.measurements.record(ana, pid, make()).measurement
    s.measurements.correct(ana, pid, original.id, correction())
    views, total = s.measurements.list_measurements(ana, pid)
    assert total == 1
    assert views[0].measurement.value == Decimal("71.80")


def test_list_can_include_superseded_with_flags(env):
    s, ana, pid = env
    original = s.measurements.record(ana, pid, make()).measurement
    s.measurements.correct(ana, pid, original.id, correction())
    views, total = s.measurements.list_measurements(ana, pid, include_superseded=True)
    assert total == 2
    flags = {v.measurement.supersedes_id is None: v.is_current for v in views}
    assert flags == {True: False, False: True}


def test_series_is_current_only_and_ascending(env):
    s, ana, pid = env
    s.measurements.record(ana, pid, make(measured_at=NOW - timedelta(days=3), value=Decimal("74")))
    mid = s.measurements.record(
        ana, pid, make(measured_at=NOW - timedelta(days=2), value=Decimal("73"))
    ).measurement
    s.measurements.record(ana, pid, make(measured_at=NOW - timedelta(days=1), value=Decimal("72")))
    s.measurements.correct(ana, pid, mid.id, correction("73.40"))
    data = s.measurements.series(ana, pid, MeasurementType.WEIGHT)
    assert [m.value for m in data.points] == [Decimal("74.00"), Decimal("73.40"), Decimal("72.00")]
    assert data.unit == MeasurementUnit.KG


# ---------- Fase 3B: acceso, consentimiento y auditoría ----------


def test_record_without_consent_is_blocked():
    s = build_services(clock=lambda: NOW)
    ana = s.new_user("ana")
    pid = s.profile_for(ana)  # sin aceptar consentimiento
    with pytest.raises(ConsentRequiredError):
        s.measurements.record(ana, pid, make())
    assert s.measurements_repo.items == []


def test_revoked_consent_blocks_writes_but_not_reads(env):
    s, ana, pid = env
    original = s.measurements.record(ana, pid, make()).measurement
    s.consent.revoke(ana, pid, ConsentPurpose.DATA_PROCESSING)
    with pytest.raises(ConsentRequiredError):
        s.measurements.record(ana, pid, make())
    with pytest.raises(ConsentRequiredError):
        s.measurements.correct(ana, pid, original.id, correction())
    _, total = s.measurements.list_measurements(ana, pid)
    assert total == 1


def test_viewer_cannot_record_or_correct(env):
    s, ana, pid = env
    luis = s.new_user("luis")
    s.grant_direct(pid, luis, AccessLevel.VIEWER)
    original = s.measurements.record(ana, pid, make()).measurement
    with pytest.raises(PermissionDeniedError):
        s.measurements.record(luis, pid, make())
    with pytest.raises(PermissionDeniedError):
        s.measurements.correct(luis, pid, original.id, correction())
    assert len(s.measurements_repo.items) == 1


def test_viewer_can_read(env):
    s, ana, pid = env
    luis = s.new_user("luis")
    s.grant_direct(pid, luis, AccessLevel.VIEWER)
    s.measurements.record(ana, pid, make())
    views, total = s.measurements.list_measurements(luis, pid)
    assert total == 1 and views[0].measurement.created_by == "Ana"


def test_user_without_access_gets_404_and_denial_is_audited(env):
    s, _, pid = env
    luis = s.new_user("luis")
    with pytest.raises(NotFoundError):
        s.measurements.list_measurements(luis, pid)
    with pytest.raises(NotFoundError):
        s.measurements.record(luis, pid, make())
    assert s.audit_repo.actions().count("access.denied") == 2


def test_editor_records_with_own_authorship(env):
    s, _, pid = env
    luis = s.new_user("luis")
    s.grant_direct(pid, luis, AccessLevel.EDITOR)
    saved = s.measurements.record(luis, pid, make(created_by="Ana")).measurement
    assert saved.created_by == "Luis"
    assert saved.created_by_user_id == luis.id


def test_writes_are_audited(env):
    s, ana, pid = env
    original = s.measurements.record(ana, pid, make()).measurement
    s.measurements.correct(ana, pid, original.id, correction())
    actions = s.audit_repo.actions()
    assert "measurement.recorded" in actions
    assert "measurement.corrected" in actions
