from datetime import UTC, datetime, timedelta
from decimal import Decimal
import pytest
from app.core.errors import BusinessRuleError, ConflictError
from app.domain.measurements import (
    MeasurementCorrection, MeasurementMethod, MeasurementType, MeasurementUnit, NewMeasurement,
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
    services = build_services(clock=lambda: NOW)
    profile = services.profiles.create("BV-001")
    return services, profile.id

def test_record_valid_measurement(env):
    s, pid = env
    view = s.measurements.record(pid, make())
    assert view.is_current is True
    assert view.measurement.value == Decimal("72.50")
    assert view.measurement.unit == "kg"
    assert view.measurement.method == "scale"

def test_rejects_value_out_of_range(env):
    s, pid = env
    with pytest.raises(BusinessRuleError):
        s.measurements.record(pid, make(value=Decimal("900")))

def test_rejects_unit_mismatch(env):
    s, pid = env
    with pytest.raises(BusinessRuleError):
        s.measurements.record(
            pid, make(metric_type=MeasurementType.WAIST, value=Decimal("80"), unit=MeasurementUnit.KG)
        )

def test_rejects_future_measured_at(env):
    s, pid = env
    with pytest.raises(BusinessRuleError):
        s.measurements.record(pid, make(measured_at=NOW + timedelta(hours=1)))

def test_rejects_archived_profile(env):
    s, pid = env
    s.profiles.archive(pid)
    with pytest.raises(BusinessRuleError):
        s.measurements.record(pid, make())

def test_correction_is_non_destructive(env):
    s, pid = env
    original = s.measurements.record(pid, make()).measurement
    corrected = s.measurements.correct(pid, original.id, correction()).measurement

    assert original.value == Decimal("72.50")
    assert corrected.value == Decimal("71.80")
    assert corrected.supersedes_id == original.id
    assert corrected.correction_reason == "Lectura errónea"
    assert corrected.created_by == "Luis"
    assert len(s.measurements_repo.items) == 2

def test_second_correction_of_same_original_conflicts(env):
    s, pid = env
    original = s.measurements.record(pid, make()).measurement
    s.measurements.correct(pid, original.id, correction())
    with pytest.raises(ConflictError):
        s.measurements.correct(pid, original.id, correction("70.00"))

def test_history_returns_chain_in_order(env):
    s, pid = env
    v1 = s.measurements.record(pid, make()).measurement
    v2 = s.measurements.correct(pid, v1.id, correction("71.80")).measurement
    v3 = s.measurements.correct(pid, v2.id, correction("71.20")).measurement

    chain = s.measurements.history(pid, v2.id)
    assert [v.measurement.id for v in chain] == [v1.id, v2.id, v3.id]
    assert [v.is_current for v in chain] == [False, False, True]

def test_list_hides_superseded_by_default(env):
    s, pid = env
    original = s.measurements.record(pid, make()).measurement
    s.measurements.correct(pid, original.id, correction())

    views, total = s.measurements.list_measurements(pid)
    assert total == 1
    assert views[0].measurement.value == Decimal("71.80")

def test_list_can_include_superseded_with_flags(env):
    s, pid = env
    original = s.measurements.record(pid, make()).measurement
    s.measurements.correct(pid, original.id, correction())

    views, total = s.measurements.list_measurements(pid, include_superseded=True)
    assert total == 2
    flags = {v.measurement.supersedes_id is None: v.is_current for v in views}
    assert flags == {True: False, False: True}

def test_series_is_current_only_and_ascending(env):
    s, pid = env
    s.measurements.record(pid, make(measured_at=NOW - timedelta(days=3), value=Decimal("74")))
    mid = s.measurements.record(pid, make(measured_at=NOW - timedelta(days=2), value=Decimal("73"))).measurement
    s.measurements.record(pid, make(measured_at=NOW - timedelta(days=1), value=Decimal("72")))
    s.measurements.correct(pid, mid.id, correction("73.40"))

    data = s.measurements.series(pid, MeasurementType.WEIGHT)
    assert [m.value for m in data.points] == [Decimal("74.00"), Decimal("73.40"), Decimal("72.00")]
    assert data.unit == MeasurementUnit.KG