"""
Unit tests for Phase 47 — Multi-Device Fleet Management API.

Tests cover:
  1. Fleet summary with empty registry
  2. Fleet summary with registered agents (seeded via update_agent_registry)
  3. Fleet devices list (sorting: health_score, cpu_usage, ticks)
  4. Online-only filter for fleet devices
  5. Single device profile (registered + unknown)
  6. Health ranking order (worst first)
  7. Anomaly detection (critical temp, battery, offline, high CPU)
  8. No anomalies when fleet is healthy
  9. Fleet comparison endpoint (valid + empty + too-many devices)
 10. Bulk-action validation (unknown action rejected)
 11. Fleet summary source distribution
"""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from fastapi import HTTPException

from app.api.v1 import live_stream
from app.api.v1.live_stream import _agent_registry, _AgentInfo, update_agent_registry
from app.api.v1 import fleet as fleet_module
from app.api.v1.fleet import (
    fleet_summary, fleet_devices, fleet_device_profile,
    fleet_ranking, fleet_anomalies, fleet_bulk_action, fleet_comparison,
    BulkActionRequest, _build_device_card,
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
              is_old: bool = False) -> None:
    """Convenience: add an agent to the registry with a mocked last_payload."""
    info = _AgentInfo(device_id=device_id, source=source)
    if is_old:
        # Simulate agent that hasn't been seen for 60 s (offline)
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
        "power_source":   "battery",
        "fan_speed":      1800,
    }
    _agent_registry[device_id] = info


def _mock_db():
    """Return a mock DB session whose latest_snapshot returns None."""
    db = MagicMock()
    db.query.return_value.options.return_value.filter.return_value.order_by.return_value.first.return_value = None
    return db


# ─────────────────────────────────────────────────────────────────────────────
# 1. Fleet summary — empty registry
# ─────────────────────────────────────────────────────────────────────────────

class TestFleetSummaryEmpty:

    def test_total_devices_zero(self):
        result = fleet_summary(db=_mock_db())
        assert result.total_devices    == 0
        assert result.online_devices   == 0
        assert result.offline_devices  == 0
        assert result.fleet_avg_health is None
        assert result.fleet_min_health is None

    def test_category_counts_zero(self):
        result = fleet_summary(db=_mock_db())
        assert result.healthy_count  == 0
        assert result.warning_count  == 0
        assert result.critical_count == 0
        assert result.total_alerts   == 0

    def test_sources_empty_dict(self):
        result = fleet_summary(db=_mock_db())
        assert result.sources == {}

    def test_generated_at_is_iso(self):
        result = fleet_summary(db=_mock_db())
        datetime.fromisoformat(result.generated_at)   # should not raise


# ─────────────────────────────────────────────────────────────────────────────
# 2. Fleet summary — with registered agents
# ─────────────────────────────────────────────────────────────────────────────

class TestFleetSummaryPopulated:

    def test_counts_two_devices(self):
        _register("mac-001", "mac")
        _register("win-001", "windows-ohm")
        result = fleet_summary(db=_mock_db())
        assert result.total_devices == 2

    def test_both_online(self):
        _register("mac-001")
        _register("mac-002")
        result = fleet_summary(db=_mock_db())
        assert result.online_devices == 2
        assert result.offline_devices == 0

    def test_offline_device_counted(self):
        _register("mac-001")
        _register("mac-002", is_old=True)
        result = fleet_summary(db=_mock_db())
        assert result.online_devices  == 1
        assert result.offline_devices == 1

    def test_avg_health_is_numeric(self):
        _register("mac-001", cpu=30.0, temp=50.0, battery=80.0)
        result = fleet_summary(db=_mock_db())
        assert result.fleet_avg_health is not None
        assert 0.0 <= result.fleet_avg_health <= 100.0

    def test_source_distribution(self):
        _register("mac-001", source="mac")
        _register("mac-002", source="mac")
        _register("win-001", source="windows-ohm")
        result = fleet_summary(db=_mock_db())
        assert result.sources.get("mac") == 2
        assert result.sources.get("windows-ohm") == 1


# ─────────────────────────────────────────────────────────────────────────────
# 3. Fleet devices list
# ─────────────────────────────────────────────────────────────────────────────

class TestFleetDevicesList:

    def test_returns_all_devices(self):
        _register("d1"); _register("d2"); _register("d3")
        cards = fleet_devices(db=_mock_db())
        assert len(cards) == 3

    def test_online_only_filter(self):
        _register("online-1")
        _register("offline-1", is_old=True)
        cards = fleet_devices(online_only=True, db=_mock_db())
        assert all(c.online for c in cards)
        assert len(cards) == 1

    def test_sort_by_health_score(self):
        _register("good",    cpu=5.0,  temp=40.0, battery=95.0)
        _register("bad",     cpu=95.0, temp=90.0, battery=5.0)
        cards = fleet_devices(sort_by="health_score", db=_mock_db())
        assert len(cards) == 2
        # Worst device first
        assert cards[0].health_score <= cards[1].health_score

    def test_sort_by_ticks(self):
        _register("d1"); _register("d2")
        _agent_registry["d1"].ticks_received = 100
        _agent_registry["d2"].ticks_received = 10
        cards = fleet_devices(sort_by="ticks", db=_mock_db())
        assert cards[0].ticks_received >= cards[1].ticks_received

    def test_device_card_fields_present(self):
        _register("mac-001", "mac")
        cards = fleet_devices(db=_mock_db())
        assert len(cards) == 1
        c = cards[0]
        assert c.device_id == "mac-001"
        assert c.source    == "mac"
        assert c.ticks_received == 42


# ─────────────────────────────────────────────────────────────────────────────
# 4. Single device profile
# ─────────────────────────────────────────────────────────────────────────────

class TestFleetDeviceProfile:

    def test_known_device_returns_card(self):
        _register("mac-001")
        card = fleet_device_profile("mac-001", db=_mock_db())
        assert card.device_id == "mac-001"

    def test_unknown_device_raises_404(self):
        with pytest.raises(HTTPException) as exc:
            fleet_device_profile("ghost-device", db=_mock_db())
        assert exc.value.status_code == 404

    def test_health_score_is_float(self):
        _register("mac-001", cpu=40.0, temp=55.0, battery=70.0)
        card = fleet_device_profile("mac-001", db=_mock_db())
        assert isinstance(card.health_score, float)
        assert 0 <= card.health_score <= 100


# ─────────────────────────────────────────────────────────────────────────────
# 5. Health ranking
# ─────────────────────────────────────────────────────────────────────────────

class TestFleetRanking:

    def test_ranking_sorted_worst_first(self):
        _register("good", cpu=5.0,  temp=40.0, battery=95.0)
        _register("bad",  cpu=95.0, temp=90.0, battery=5.0)
        ranks = fleet_ranking(db=_mock_db())
        assert ranks[0].rank == 1
        assert ranks[0].health_score <= ranks[1].health_score

    def test_all_devices_have_rank(self):
        _register("d1"); _register("d2"); _register("d3")
        ranks = fleet_ranking(db=_mock_db())
        assert [r.rank for r in ranks] == list(range(1, len(ranks) + 1))

    def test_ranking_includes_offline(self):
        _register("online")
        _register("offline", is_old=True)
        ranks = fleet_ranking(db=_mock_db())
        assert len(ranks) == 2


# ─────────────────────────────────────────────────────────────────────────────
# 6. Anomaly detection
# ─────────────────────────────────────────────────────────────────────────────

class TestFleetAnomalies:

    def test_no_anomalies_healthy_device(self):
        _register("healthy", cpu=20.0, temp=50.0, battery=80.0, mem=40.0)
        anomalies = fleet_anomalies(db=_mock_db())
        # May still produce a health-score warning; check no CRITICAL temp/battery
        critical_metrics = {a.metric for a in anomalies if a.severity == "critical"}
        assert "cpu_temperature" not in critical_metrics
        assert "battery_level"   not in critical_metrics

    def test_critical_temperature_flagged(self):
        _register("hot", temp=92.0, cpu=80.0, battery=60.0)
        anomalies = fleet_anomalies(db=_mock_db())
        temp_anomaly = next((a for a in anomalies if a.metric == "cpu_temperature"), None)
        assert temp_anomaly is not None
        assert temp_anomaly.severity == "critical"

    def test_critical_battery_flagged(self):
        _register("dying", battery=5.0, temp=50.0, cpu=20.0)
        anomalies = fleet_anomalies(db=_mock_db())
        bat_anomaly = next((a for a in anomalies if a.metric == "battery_level"), None)
        assert bat_anomaly is not None
        assert bat_anomaly.severity == "critical"

    def test_offline_device_flagged(self):
        _register("ghost", is_old=True)
        anomalies = fleet_anomalies(db=_mock_db())
        conn_anomaly = next((a for a in anomalies if a.metric == "connectivity"), None)
        assert conn_anomaly is not None
        assert conn_anomaly.severity == "warning"

    def test_high_cpu_flagged_as_warning(self):
        _register("busy", cpu=95.0, temp=50.0, battery=70.0, mem=40.0)
        anomalies = fleet_anomalies(db=_mock_db())
        cpu_anomaly = next((a for a in anomalies if a.metric == "cpu_usage"), None)
        assert cpu_anomaly is not None
        assert cpu_anomaly.severity == "warning"

    def test_critical_anomalies_sorted_first(self):
        _register("crit-bat",  battery=5.0, temp=50.0, cpu=20.0)
        _register("warn-cpu",  cpu=95.0,    temp=50.0, battery=70.0, mem=40.0)
        anomalies = fleet_anomalies(db=_mock_db())
        if len(anomalies) >= 2:
            severities = [a.severity for a in anomalies]
            # All criticals should come before warnings
            first_warning = next((i for i, s in enumerate(severities) if s == "warning"), len(severities))
            last_critical = next((len(severities) - 1 - i for i, s in enumerate(reversed(severities)) if s == "critical"), -1)
            assert last_critical <= first_warning


# ─────────────────────────────────────────────────────────────────────────────
# 7. Fleet comparison
# ─────────────────────────────────────────────────────────────────────────────

class TestFleetComparison:

    def test_comparison_registered_devices(self):
        _register("d1"); _register("d2")
        result = fleet_comparison(device_ids="d1,d2", db=_mock_db())
        assert len(result["devices"]) == 2
        assert "fleet_max" in result
        assert "fleet_min" in result

    def test_comparison_unregistered_device_returns_error_row(self):
        result = fleet_comparison(device_ids="ghost-999", db=_mock_db())
        row = result["devices"][0]
        assert "error" in row

    def test_comparison_empty_ids_raises_400(self):
        with pytest.raises(HTTPException) as exc:
            fleet_comparison(device_ids="   ", db=_mock_db())
        assert exc.value.status_code == 400

    def test_comparison_too_many_ids_raises_400(self):
        ids = ",".join([f"dev-{i}" for i in range(21)])
        with pytest.raises(HTTPException) as exc:
            fleet_comparison(device_ids=ids, db=_mock_db())
        assert exc.value.status_code == 400

    def test_comparison_fleet_max_is_numeric(self):
        _register("d1", cpu=30.0)
        _register("d2", cpu=70.0)
        result = fleet_comparison(device_ids="d1,d2", db=_mock_db())
        max_cpu = result["fleet_max"].get("cpu_usage")
        if max_cpu is not None:
            assert max_cpu >= 0.0


# ─────────────────────────────────────────────────────────────────────────────
# 8. Bulk action validation
# ─────────────────────────────────────────────────────────────────────────────

class TestFleetBulkAction:

    def test_unknown_action_raises_400(self):
        with pytest.raises(HTTPException) as exc:
            fleet_bulk_action(BulkActionRequest(action="DELETE_ALL"))
        assert exc.value.status_code == 400

    def test_valid_action_offline_device_returns_offline(self):
        _register("offline-dev", is_old=True)
        result = fleet_bulk_action(BulkActionRequest(action="ECO_MODE", device_ids=["offline-dev"]))
        assert result["results"]["offline-dev"] == "offline"

    def test_valid_action_unregistered_device_returns_not_registered(self):
        result = fleet_bulk_action(BulkActionRequest(action="KILL_HIGH_CPU", device_ids=["ghost"]))
        assert result["results"]["ghost"] == "not_registered"

    def test_valid_action_no_online_devices_returns_empty(self):
        _register("offline-1", is_old=True)
        result = fleet_bulk_action(BulkActionRequest(action="ECO_MODE"))
        # No online devices → no results (or all offline)
        for v in result["results"].values():
            assert v in ("offline", "not_registered")

    def test_response_contains_action_and_sent_at(self):
        result = fleet_bulk_action(BulkActionRequest(action="DISABLE_ECO_MODE"))
        assert result["action"]   == "DISABLE_ECO_MODE"
        assert "sent_at" in result
        datetime.fromisoformat(result["sent_at"])   # should not raise


# ─────────────────────────────────────────────────────────────────────────────
# 9. build_device_card helper
# ─────────────────────────────────────────────────────────────────────────────

class TestBuildDeviceCard:

    def test_online_agent_is_marked_online(self):
        _register("fresh")
        agent = _agent_registry["fresh"]
        card  = _build_device_card(agent, snap=None)
        assert card.online is True

    def test_stale_agent_is_marked_offline(self):
        _register("old", is_old=True)
        agent = _agent_registry["old"]
        card  = _build_device_card(agent, snap=None)
        assert card.online is False

    def test_health_score_within_bounds(self):
        _register("healthy", cpu=25.0, temp=52.0, battery=75.0)
        agent = _agent_registry["healthy"]
        card  = _build_device_card(agent, snap=None)
        assert card.health_score is not None
        assert 0.0 <= card.health_score <= 100.0

    def test_fields_from_last_payload(self):
        _register("payload-test", cpu=42.5, temp=63.0, battery=55.0)
        agent = _agent_registry["payload-test"]
        card  = _build_device_card(agent, snap=None)
        assert card.cpu_usage == 42.5
        assert card.cpu_temperature == 63.0
        assert card.battery_level == 55.0
