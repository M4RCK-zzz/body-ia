from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest

from app.core.errors import BusinessRuleError, NotFoundError
from app.domain.measurements import (
    MeasurementCorrection,
    MeasurementMethod,
    MeasurementType,
    MeasurementUnit,
)
from tests.test_reports_service import BASE, _env, _measurements, _profile


class TestSummary:
    def test_descriptive_only(self):
        env = _env()
        owner = env.new_user("ana")
        pid = _profile(env, owner)
        _measurements(env, owner, pid)

        summary = env.analytics.summary(owner, pid, window_days=30)

        weight = next(t for t in summary.trends if t.metric_type == "weight")
        assert weight.count == 5
        assert weight.last_value == Decimal("72.20")
        assert weight.delta_absolute == Decimal("0.40")
        # Sin campos de predicción: la analítica es estrictamente descriptiva.
        assert not hasattr(weight, "forecast")
        assert summary.data_kind == "observed"

    def test_metrics_without_data_are_named(self):
        env = _env()
        owner = env.new_user("ana")
        pid = _profile(env, owner)
        _measurements(env, owner, pid)

        summary = env.analytics.summary(owner, pid)

        assert "Peso" not in summary.metrics_without_data
        assert summary.metrics_without_data  # el resto del catálogo no tiene datos
        for trend in summary.trends:
            if trend.metric_type != "weight":
                assert trend.count == 0
                assert trend.last_value is None

    def test_window_filters_points(self):
        env = _env()
        owner = env.new_user("ana")
        pid = _profile(env, owner)
        _measurements(env, owner, pid)

        week = env.analytics.summary(owner, pid, window_days=7, record_audit=False)
        quarter = env.analytics.summary(owner, pid, window_days=90, record_audit=False)

        assert week.date_to - week.date_from == timedelta(days=7)
        assert quarter.date_to - quarter.date_from == timedelta(days=90)

    def test_invalid_window_is_rejected(self):
        env = _env()
        owner = env.new_user("ana")
        pid = _profile(env, owner)

        with pytest.raises(BusinessRuleError):
            env.analytics.summary(owner, pid, window_days=14)

    def test_audit_records_view(self):
        env = _env()
        owner = env.new_user("ana")
        pid = _profile(env, owner)

        env.analytics.summary(owner, pid)

        assert "analytics.viewed" in env.audit_repo.actions()

    def test_no_access_is_hidden(self):
        env = _env()
        owner = env.new_user("ana")
        stranger = env.new_user("beto")
        pid = _profile(env, owner)

        with pytest.raises(NotFoundError):
            env.analytics.summary(stranger, pid)

    def test_corrected_measurements_are_counted_not_duplicated(self):
        env = _env()
        owner = env.new_user("ana")
        pid = _profile(env, owner)
        _measurements(env, owner, pid, values=(72.0,))
        original = env.measurements_repo.items[0]
        env.measurements.correct(
            owner,
            pid,
            original.id,
            MeasurementCorrection(
                value=Decimal("73.0"), created_by=owner.full_name, reason="error de captura"
            ),
        )

        summary = env.analytics.summary(owner, pid)
        weight = next(t for t in summary.trends if t.metric_type == "weight")

        assert weight.count == 1
        assert weight.corrected_count == 1
        assert weight.last_value == Decimal("73.00")

    def test_series_rows_respects_metric_filter(self):
        env = _env()
        owner = env.new_user("ana")
        pid = _profile(env, owner)
        _measurements(env, owner, pid)

        rows = env.analytics.series_rows(
            owner, pid, date_from=None, date_to=None, metric_types=[MeasurementType.WEIGHT]
        )

        assert len(rows) == 1
        assert rows[0][0].metric_type == "weight"
        assert len(rows[0][1]) == 5


class TestEmptyProfile:
    def test_profile_without_measurements(self):
        env = _env()
        owner = env.new_user("ana")
        pid = _profile(env, owner, "BV-404")

        summary = env.analytics.summary(owner, pid)

        assert summary.total_measurements == 0
        assert all(trend.count == 0 for trend in summary.trends)
        assert all(trend.last_value is None for trend in summary.trends)


def test_measurement_units_used(  ):
    # Guarda de regresión: las métricas del catálogo siguen siendo kg/cm.
    assert {MeasurementUnit.KG.value, MeasurementUnit.CM.value} == {"kg", "cm"}
    assert MeasurementMethod.SCALE.value == "scale"
    assert BASE.tzinfo is not None
