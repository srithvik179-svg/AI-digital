"""
Unit tests for Phase 49 — Executive Dashboard API.

Tests cover:
  1. Executive overview with empty registry
  2. Executive overview with registered agents (healthy vs warnings vs criticals)
  3. Risk level calculation logic (healthy, warning, critical, moderate)
  4. KPI cards structure and values
  5. AI Recommendations aggregation and ranking
  6. Device predictions (thermal, battery, fan speed)
  7. Incident logging and deduplication
  8. Health histogram bucket counts
"""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from fastapi import HTTPException

from app.api.v1.live_stream import _agent_registry, _AgentInfo
from app.api.v1.executive import (
    executive_overview, executive_kpis, executive_recommendations,
    executive_risk, executive_predictions, executive_incidents,
    executive_device_health, _risk_level, _risk_color, _build_kpis,
    _build_recommendations, _build_predictions, _build_incidents,
    _build_histogram,
)

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures / helpers
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clear_registry():
    """Ensure a clean registry for every test."""
    _agent_registry.clear()
    yield
    _agent_registry.clear()


def _register(device_id: str, source: str = "mac",
              cpu: float = 30.0, temp: float = 55.0,
              battery: float = 80.0, mem: float = 50.0,
              is_old: bool = False, fan: float = 1800.0,
              power_source: str = "battery") -> None:
    """Convenience: add an agent to the registry with a mocked last_payload."""
    info = _AgentInfo(device_id=device_id, source=source)
    if is_old:
        info.last_heartbeat = datetime.utcnow() - timedelta(seconds=60)
    info.ticks_received = 42
    info.last_payload = {
        "device_id":      device_id,
        "cpu_usage":      cpu,
        "memory_usage":   mem,
        "disk_usage":     30.0,
        "cpu_temperature":temp,
        "battery_level":  battery,
        "battery_health": 92.0,
        "power_source":   power_source,
        "fan_speed":      fan,
    }
    _agent_registry[device_id] = info


def _mock_db():
    """Return a mock DB session whose latest_snapshot returns None."""
    db = MagicMock()
    # Chain with options (used in fleet.py)
    db.query.return_value.options.return_value.filter.return_value.order_by.return_value.first.return_value = None
    # Chain without options (used in executive.py)
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
    return db


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestRiskLevelLogic:

    def test_risk_level_empty(self):
        assert _risk_level(0, 0, 0, 0) == "UNKNOWN"

    def test_risk_level_critical(self):
        assert _risk_level(5, 2, 1, 8) == "CRITICAL"

    def test_risk_level_high_warning_ratio(self):
        # 2 warnings out of 10 is 20%, which is >= 20%
        assert _risk_level(8, 2, 0, 10) == "HIGH"

    def test_risk_level_moderate_warning_ratio(self):
        # 1 warning out of 10 is 10%, which is >= 10%
        assert _risk_level(9, 1, 0, 10) == "MODERATE"

    def test_risk_level_healthy(self):
        # 0 warnings, 0 criticals
        assert _risk_level(10, 0, 0, 10) == "HEALTHY"

    def test_risk_colors(self):
        assert _risk_color("CRITICAL") == "#ef4444"
        assert _risk_color("HIGH") == "#f97316"
        assert _risk_color("MODERATE") == "#f59e0b"
        assert _risk_color("HEALTHY") == "#10b981"
        assert _risk_color("UNKNOWN") == "#64748b"


class TestExecutiveKPIs:

    def test_kpis_empty_registry(self):
        kpis = executive_kpis(db=_mock_db())
        # Should return a list of KPICards
        assert len(kpis) == 6
        assert kpis[0].label == "Fleet Health"
        assert kpis[0].value == 0.0
        assert kpis[1].value == "UNKNOWN"

    def test_kpis_populated_registry(self):
        _register("mac-001", cpu=10.0, temp=40.0, battery=90.0)
        _register("mac-002", cpu=95.0, temp=92.0, battery=15.0)  # critical/bad device
        kpis = executive_kpis(db=_mock_db())
        assert len(kpis) == 6
        # Active Alerts KPI index is 2
        assert kpis[2].label == "Active Alerts"
        # Online Devices index is 3
        assert kpis[3].value == "2/2"


class TestExecutiveRecommendations:

    def test_recommendations_healthy_fleet(self):
        _register("mac-001", cpu=20.0, temp=45.0, battery=80.0)
        recs = executive_recommendations(db=_mock_db())
        # Should be empty since there are no anomalies
        assert len(recs) == 0

    def test_recommendations_with_anomalies(self):
        _register("hot-mac", temp=95.0, cpu=80.0)
        recs = executive_recommendations(db=_mock_db())
        assert len(recs) > 0
        thermal_rec = next((r for r in recs if r.category == "thermal"), None)
        assert thermal_rec is not None
        assert "hot-mac" in thermal_rec.devices
        assert thermal_rec.priority == "critical"
        assert thermal_rec.confidence == 0.93


class TestExecutivePredictions:

    def test_predictions_none_for_idle_devices(self):
        _register("idle-mac", cpu=5.0, temp=40.0, battery=100.0, power_source="usb")
        preds = executive_predictions(db=_mock_db())
        assert len(preds) == 0

    def test_predictions_thermal_runaway(self):
        # CPU > 65 and CPU usage > 70 triggers thermal rising rate prediction
        _register("hot-running", cpu=85.0, temp=70.0)
        preds = executive_predictions(db=_mock_db())
        assert len(preds) == 1
        assert preds[0].metric == "cpu_temperature"
        assert preds[0].severity in ("warning", "critical")

    def test_predictions_battery_drain(self):
        # battery < 50% and on battery
        _register("draining", cpu=20.0, battery=40.0, power_source="battery")
        preds = executive_predictions(db=_mock_db())
        assert len(preds) == 1
        assert preds[0].metric == "battery_level"
        assert preds[0].predicted == 0.0

    def test_predictions_fan_saturation(self):
        # fan speed > 5000 and cpu temp > 80
        _register("saturated", cpu=80.0, temp=82.0, fan=5500.0)
        preds = executive_predictions(db=_mock_db())
        fan_pred = next((p for p in preds if p.metric == "fan_speed"), None)
        assert fan_pred is not None
        assert fan_pred.predicted == 6000.0


class TestExecutiveIncidents:

    def test_incidents_empty(self):
        incidents = executive_incidents(db=_mock_db())
        assert len(incidents) == 0

    def test_incidents_with_anomalies(self):
        _register("anomaly-device", temp=95.0, cpu=95.0)
        incidents = executive_incidents(db=_mock_db())
        assert len(incidents) > 0
        # Check uniqueness of device_id + metric key in output
        keys = [f"{i.device_id}:{i.metric}" for i in incidents]
        assert len(keys) == len(set(keys))


class TestExecutiveDeviceHealthHistogram:

    def test_histogram_buckets(self):
        # Bucket logic: 90-100, 80-89, 70-79, 55-69, 0-54
        _register("healthy-95", cpu=5.0, temp=40.0, battery=98.0) # score should be high, ~95+
        _register("critical-45", cpu=98.0, temp=98.0, battery=2.0) # score should be very low, <50
        hist = executive_device_health(db=_mock_db())
        assert len(hist) == 5
        assert hist[0].label == "90–100"
        assert hist[4].label == "0–54"
        total_counted = sum(b.count for b in hist)
        assert total_counted == 2


class TestExecutiveOverview:

    def test_overview_fields_present(self):
        _register("mac-001", cpu=25.0, temp=50.0, battery=85.0)
        overview = executive_overview(db=_mock_db())
        assert overview.total_devices == 1
        assert overview.online_devices == 1
        assert len(overview.kpis) == 6
        assert isinstance(overview.fleet_health, float)
        assert overview.fleet_risk in ("HEALTHY", "MODERATE", "HIGH", "CRITICAL")
        assert len(overview.health_histogram) == 5
        assert overview.summary_sentence != ""
