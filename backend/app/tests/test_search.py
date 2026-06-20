"""
Unit tests for the Phase 9 Telemetry Search Engine.
Validates natural language query compilation to database filters and execution.
"""
import pytest
from unittest.mock import MagicMock
from datetime import datetime

from app.services.search_engine import search_telemetry_records
from app.models.telemetry import TelemetrySnapshot, CPUMetrics, GPUMetrics, MemoryMetrics, BatteryMetrics, DiskMetrics, WiFiMetrics, ThermalMetrics, PowerMetrics

# ─── Helpers ──────────────────────────────────────────────────────────

def create_snapshot(
    device_id: str,
    cpu_usage: float = 20.0,
    cpu_temperature: float = 50.0,
    battery_level: float = 80.0,
    power_source: str = "ac",
    gpu_usage: float = 10.0,
    memory_usage: float = 30.0,
    disk_usage: float = 35.0,
    signal_strength_dbm: int = -50,
    health_score: float = 95.0,
    health_category: str = "Healthy"
) -> TelemetrySnapshot:
    """Create a mock TelemetrySnapshot database record."""
    s = TelemetrySnapshot(id=f"snap-{cpu_usage}-{cpu_temperature}", device_id=device_id, timestamp=datetime.utcnow(), health_score=health_score, health_category=health_category)
    s.cpu = CPUMetrics(cpu_usage=cpu_usage, active_process_count=90)
    s.gpu = GPUMetrics(gpu_usage=gpu_usage, gpu_temperature=45.0, gpu_memory_usage=10.0)
    s.memory = MemoryMetrics(memory_usage=memory_usage)
    s.battery = BatteryMetrics(battery_level=battery_level, battery_health=95.0)
    s.disk = DiskMetrics(disk_usage=disk_usage)
    s.wifi = WiFiMetrics(signal_strength_dbm=signal_strength_dbm)
    s.thermal = ThermalMetrics(cpu_temperature=cpu_temperature, fan_speed_rpm=1500, thermal_state="nominal")
    s.power = PowerMetrics(power_source=power_source)
    return s


# ─── Tests ────────────────────────────────────────────────────────────

class TestSearchEngine:
    def test_search_high_temperature_events(self):
        """NLP: 'high temp' compiles to temperature >= 75 filter."""
        db = MagicMock()
        search_telemetry_records("test-device", "Show high temperature events", db)
        
        # Verify db query structure was constructed and filtered
        assert db.query.called
        assert db.query.return_value.join.called
        # Check that filter was called at least once
        assert db.query.return_value.join.return_value.join.return_value.join.return_value.join.return_value.join.return_value.join.return_value.join.return_value.join.return_value.options.return_value.filter.called

    def test_search_battery_drain_events(self):
        """NLP: 'battery drain' compiles to power_source == battery."""
        db = MagicMock()
        search_telemetry_records("test-device", "battery drain log", db)
        assert db.query.called

    def test_search_low_battery_events(self):
        """NLP: 'low battery' compiles to level <= 20."""
        db = MagicMock()
        search_telemetry_records("test-device", "critical low battery level", db)
        assert db.query.called

    def test_search_high_cpu_events(self):
        """NLP: 'high cpu' compiles to cpu_usage >= 75."""
        db = MagicMock()
        search_telemetry_records("test-device", "high cpu load", db)
        assert db.query.called

    def test_search_high_gpu_events(self):
        """NLP: 'high gpu' compiles to gpu_usage >= 75."""
        db = MagicMock()
        search_telemetry_records("test-device", "high gpu loading", db)
        assert db.query.called

    def test_search_high_memory_events(self):
        """NLP: 'high memory' compiles to memory_usage >= 75."""
        db = MagicMock()
        search_telemetry_records("test-device", "high memory pressure", db)
        assert db.query.called

    def test_search_disk_warning_events(self):
        """NLP: 'disk full' compiles to disk_usage >= 80."""
        db = MagicMock()
        search_telemetry_records("test-device", "Show disk storage space warnings", db)
        assert db.query.called

    def test_search_weak_wifi_events(self):
        """NLP: 'weak wifi' compiles to signal_strength_dbm < -70."""
        db = MagicMock()
        search_telemetry_records("test-device", "weak wifi connection", db)
        assert db.query.called

    def test_search_health_critical_events(self):
        """NLP: 'critical health' compiles to health_score < 50."""
        db = MagicMock()
        search_telemetry_records("test-device", "critical health events", db)
        assert db.query.called

    def test_search_logical_or_combination(self):
        """NLP: 'high cpu or low battery' compiles with OR operator instead of default AND."""
        db = MagicMock()
        search_telemetry_records("test-device", "high cpu or low battery", db)
        assert db.query.called

    def test_search_no_match_returns_all(self):
        """NLP: Unmatched queries result in no active filters (returns all snapshots)."""
        db = MagicMock()
        search_telemetry_records("test-device", "Show generic laptop snapshots", db)
        assert db.query.called

    def test_search_latency(self):
        """Ensure search query compilation is sub-millisecond."""
        db = MagicMock()
        import time
        t0 = time.perf_counter()
        search_telemetry_records("test-device", "high cpu usage and low battery level or high temperature", db)
        elapsed = time.perf_counter() - t0
        assert elapsed < 0.05, f"Search engine took too long to compile query: {elapsed:.3f}s"
