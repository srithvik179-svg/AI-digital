"""
Unit tests for the Phase 6 Alert Detection Engine.
Validates every rule category and edge case behaviour.
"""
import pytest
from app.services.alert_engine import (
    evaluate_alerts,
    AlertSeverity, AlertCategory,
    group_alerts_by_category,
    RULES,
)


# ─── Helpers ──────────────────────────────────────────────────────────

def base_healthy():
    """Returns kwargs for a perfectly healthy snapshot (no alerts)."""
    return dict(
        cpu_temperature=50.0,
        battery_level=80.0,
        battery_health=90.0,
        disk_usage=50.0,
        gpu_temperature=45.0,
        battery_temperature=30.0,
        cycle_count=200,
        write_bytes_sec=1_000_000,  # 1 MB/s
        signal_strength_dbm=-55.0,
        link_speed_mbps=300,
        thermal_state="nominal",
        power_source="ac",
        device_id="test-laptop",
    )


# ─── Zero-alert baseline ──────────────────────────────────────────────

class TestNoAlertsBaseline:
    def test_healthy_snapshot_fires_no_alerts(self):
        alerts = evaluate_alerts(**base_healthy())
        assert alerts == [], f"Expected no alerts, got: {[a.rule_id for a in alerts]}"


# ─── Overheating rules ────────────────────────────────────────────────

class TestOverheatingAlerts:
    def test_cpu_warning_fires_at_76_degrees(self):
        kwargs = base_healthy()
        kwargs["cpu_temperature"] = 76.0
        alerts = evaluate_alerts(**kwargs)
        rule_ids = [a.rule_id for a in alerts]
        assert "cpu_temp_warning" in rule_ids

    def test_cpu_critical_fires_at_89_degrees(self):
        kwargs = base_healthy()
        kwargs["cpu_temperature"] = 89.0
        alerts = evaluate_alerts(**kwargs)
        rule_ids = [a.rule_id for a in alerts]
        assert "cpu_temp_critical" in rule_ids

    def test_cpu_critical_suppresses_warning(self):
        """When Critical fires for cpu_temperature, Warning must NOT also fire."""
        kwargs = base_healthy()
        kwargs["cpu_temperature"] = 89.0
        alerts = evaluate_alerts(**kwargs)
        rule_ids = [a.rule_id for a in alerts]
        assert "cpu_temp_critical" in rule_ids
        assert "cpu_temp_warning" not in rule_ids, "Warning should be suppressed by Critical"

    def test_gpu_temp_warning(self):
        kwargs = base_healthy()
        kwargs["gpu_temperature"] = 82.0
        alerts = evaluate_alerts(**kwargs)
        assert any(a.rule_id == "gpu_temp_warning" for a in alerts)

    def test_gpu_temp_critical_suppresses_warning(self):
        kwargs = base_healthy()
        kwargs["gpu_temperature"] = 92.0
        alerts = evaluate_alerts(**kwargs)
        rule_ids = [a.rule_id for a in alerts]
        assert "gpu_temp_critical" in rule_ids
        assert "gpu_temp_warning" not in rule_ids

    def test_thermal_state_serious_triggers_alert(self):
        kwargs = base_healthy()
        kwargs["thermal_state"] = "serious"
        alerts = evaluate_alerts(**kwargs)
        assert any("thermal_state_serious" in a.rule_id for a in alerts)

    def test_thermal_state_critical_triggers_critical_alert(self):
        kwargs = base_healthy()
        kwargs["thermal_state"] = "critical"
        alerts = evaluate_alerts(**kwargs)
        thermal_alerts = [a for a in alerts if a.rule_id.startswith("thermal_state")]
        assert len(thermal_alerts) >= 1
        assert thermal_alerts[0].severity == AlertSeverity.CRITICAL


# ─── Battery rules ────────────────────────────────────────────────────

class TestBatteryAlerts:
    def test_battery_level_warning_at_18_percent(self):
        kwargs = base_healthy()
        kwargs["battery_level"] = 18.0
        kwargs["power_source"] = "battery"
        alerts = evaluate_alerts(**kwargs)
        assert any(a.rule_id == "battery_level_warning" for a in alerts)

    def test_battery_level_critical_at_8_percent(self):
        kwargs = base_healthy()
        kwargs["battery_level"] = 8.0
        kwargs["power_source"] = "battery"
        alerts = evaluate_alerts(**kwargs)
        rule_ids = [a.rule_id for a in alerts]
        assert "battery_level_critical" in rule_ids
        assert "battery_level_warning" not in rule_ids

    def test_battery_health_warning_at_75_percent(self):
        kwargs = base_healthy()
        kwargs["battery_health"] = 75.0
        alerts = evaluate_alerts(**kwargs)
        assert any(a.rule_id == "battery_health_warning" for a in alerts)

    def test_battery_health_critical_at_55_percent(self):
        kwargs = base_healthy()
        kwargs["battery_health"] = 55.0
        alerts = evaluate_alerts(**kwargs)
        rule_ids = [a.rule_id for a in alerts]
        assert "battery_health_critical" in rule_ids
        assert "battery_health_warning" not in rule_ids

    def test_cycle_count_warning_above_800(self):
        kwargs = base_healthy()
        kwargs["cycle_count"] = 850
        alerts = evaluate_alerts(**kwargs)
        assert any(a.rule_id == "battery_cycle_warning" for a in alerts)

    def test_battery_temp_warning_at_42_degrees(self):
        kwargs = base_healthy()
        kwargs["battery_temperature"] = 42.0
        alerts = evaluate_alerts(**kwargs)
        assert any(a.rule_id == "battery_temp_warning" for a in alerts)


# ─── Disk rules ───────────────────────────────────────────────────────

class TestDiskAlerts:
    def test_disk_usage_warning_at_83_percent(self):
        kwargs = base_healthy()
        kwargs["disk_usage"] = 83.0
        alerts = evaluate_alerts(**kwargs)
        assert any(a.rule_id == "disk_usage_warning" for a in alerts)

    def test_disk_usage_critical_at_94_percent(self):
        kwargs = base_healthy()
        kwargs["disk_usage"] = 94.0
        alerts = evaluate_alerts(**kwargs)
        rule_ids = [a.rule_id for a in alerts]
        assert "disk_usage_critical" in rule_ids
        assert "disk_usage_warning" not in rule_ids

    def test_disk_write_storm_at_150_mbps(self):
        kwargs = base_healthy()
        kwargs["write_bytes_sec"] = 150_000_000  # 150 MB/s
        alerts = evaluate_alerts(**kwargs)
        assert any(a.rule_id == "disk_write_storm" for a in alerts)

    def test_disk_write_normal_does_not_trigger(self):
        kwargs = base_healthy()
        kwargs["write_bytes_sec"] = 50_000_000  # 50 MB/s — below threshold
        alerts = evaluate_alerts(**kwargs)
        assert not any(a.rule_id == "disk_write_storm" for a in alerts)


# ─── Network rules ────────────────────────────────────────────────────

class TestNetworkAlerts:
    def test_wifi_signal_warning_at_minus_72_dbm(self):
        kwargs = base_healthy()
        kwargs["signal_strength_dbm"] = -72.0
        alerts = evaluate_alerts(**kwargs)
        assert any(a.rule_id == "wifi_signal_warning" for a in alerts)

    def test_wifi_signal_critical_at_minus_87_dbm(self):
        kwargs = base_healthy()
        kwargs["signal_strength_dbm"] = -87.0
        alerts = evaluate_alerts(**kwargs)
        rule_ids = [a.rule_id for a in alerts]
        assert "wifi_signal_critical" in rule_ids
        assert "wifi_signal_warning" not in rule_ids

    def test_wifi_link_speed_warning_at_24_mbps(self):
        kwargs = base_healthy()
        kwargs["link_speed_mbps"] = 24
        alerts = evaluate_alerts(**kwargs)
        assert any(a.rule_id == "wifi_speed_warning" for a in alerts)


# ─── Multi-alert scenarios ────────────────────────────────────────────

class TestMultiAlertScenarios:
    def test_multiple_categories_fire_simultaneously(self):
        """A sick laptop can have alerts in all 4 categories at once."""
        kwargs = base_healthy()
        kwargs["cpu_temperature"] = 89.0       # Overheating Critical
        kwargs["battery_level"] = 8.0          # Battery Critical
        kwargs["battery_health"] = 55.0        # Battery Critical (health)
        kwargs["disk_usage"] = 94.0            # Disk Critical
        kwargs["signal_strength_dbm"] = -87.0  # Network Critical
        alerts = evaluate_alerts(**kwargs)
        categories = {a.category for a in alerts}
        assert AlertCategory.OVERHEATING in categories
        assert AlertCategory.BATTERY     in categories
        assert AlertCategory.DISK        in categories
        assert AlertCategory.NETWORK     in categories

    def test_alert_contains_correct_metric_value(self):
        kwargs = base_healthy()
        kwargs["cpu_temperature"] = 80.0
        alerts = evaluate_alerts(**kwargs)
        cpu_alert = next((a for a in alerts if a.rule_id == "cpu_temp_warning"), None)
        assert cpu_alert is not None
        assert cpu_alert.metric_value == 80.0
        assert cpu_alert.threshold_value == 75.0

    def test_alert_device_id_propagated(self):
        kwargs = base_healthy()
        kwargs["cpu_temperature"] = 80.0
        kwargs["device_id"] = "my-test-laptop"
        alerts = evaluate_alerts(**kwargs)
        assert all(a.device_id == "my-test-laptop" for a in alerts)

    def test_group_by_category_utility(self):
        kwargs = base_healthy()
        kwargs["cpu_temperature"] = 80.0
        kwargs["disk_usage"] = 83.0
        alerts = evaluate_alerts(**kwargs)
        grouped = group_alerts_by_category(alerts)
        assert AlertCategory.OVERHEATING in grouped
        assert AlertCategory.DISK in grouped
        assert len(grouped[AlertCategory.OVERHEATING]) >= 1
        assert len(grouped[AlertCategory.DISK]) >= 1

    def test_no_optional_params_does_not_crash(self):
        """Minimal call with only required 4 params must not raise."""
        alerts = evaluate_alerts(
            cpu_temperature=50.0,
            battery_level=80.0,
            battery_health=90.0,
            disk_usage=50.0,
        )
        assert isinstance(alerts, list)

    def test_rule_ids_are_unique(self):
        """All configured rules must have unique IDs."""
        ids = [r.rule_id for r in RULES]
        assert len(ids) == len(set(ids)), "Duplicate rule_ids detected"
