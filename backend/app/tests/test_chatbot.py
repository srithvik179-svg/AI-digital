"""
Unit tests for the Phase 8 Telemetry Chatbot Engine.
Validates intent classification, template correctness, multi-intent handling, fallback responses, and performance.
"""
import pytest
from unittest.mock import MagicMock
from datetime import datetime

from app.services.chatbot_engine import generate_chatbot_response
from app.models.telemetry import TelemetrySnapshot, CPUMetrics, GPUMetrics, BatteryMetrics, DiskMetrics, PowerMetrics, ThermalMetrics

# ─── Helpers ──────────────────────────────────────────────────────────

def create_mock_snapshot(
    device_id: str = "test-laptop",
    cpu_usage: float = 22.0,
    active_process_count: int = 85,
    cpu_frequency_mhz: float = 2400.0,
    gpu_usage: float = 12.0,
    gpu_temperature: float = 45.0,
    gpu_memory_usage: float = 15.0,
    battery_level: float = 90.0,
    battery_health: float = 95.0,
    battery_temperature: float = 31.0,
    cycle_count: int = 150,
    power_source: str = "ac",
    disk_usage: float = 40.0,
    read_bytes_sec: int = 1048576, # 1 MB/s
    write_bytes_sec: int = 524288,  # 0.5 MB/s
) -> TelemetrySnapshot:
    """Create a mock TelemetrySnapshot object with populated child metrics."""
    snapshot = TelemetrySnapshot(
        id="mock-snapshot-123",
        device_id=device_id,
        timestamp=datetime.utcnow(),
    )
    snapshot.cpu = CPUMetrics(
        cpu_usage=cpu_usage,
        active_process_count=active_process_count,
        cpu_frequency_mhz=cpu_frequency_mhz
    )
    snapshot.gpu = GPUMetrics(
        gpu_usage=gpu_usage,
        gpu_temperature=gpu_temperature,
        gpu_memory_usage=gpu_memory_usage
    )
    snapshot.battery = BatteryMetrics(
        battery_level=battery_level,
        battery_health=battery_health,
        battery_temperature=battery_temperature,
        cycle_count=cycle_count
    )
    snapshot.disk = DiskMetrics(
        disk_usage=disk_usage,
        read_bytes_sec=read_bytes_sec,
        write_bytes_sec=write_bytes_sec
    )
    snapshot.power = PowerMetrics(
        power_source=power_source
    )
    snapshot.thermal = ThermalMetrics(
        cpu_temperature=cpu_temperature if 'cpu_temperature' in locals() else 48.0,
        fan_speed_rpm=1500
    )
    return snapshot


# ─── Tests ────────────────────────────────────────────────────────────

class TestChatbotEngine:
    def test_chatbot_responds_to_cpu_query(self):
        """CPU query triggers CPU status template and displays correct utilization."""
        db = MagicMock()
        mock_snap = create_mock_snapshot(cpu_usage=75.5, active_process_count=120)
        db.query.return_value.options.return_value.filter.return_value.order_by.return_value.first.return_value = mock_snap
        
        result = generate_chatbot_response("test-laptop", "How is my CPU doing?", db)
        assert "CPU Status" in result["response"]
        assert "75.5%" in result["response"]
        assert "120 active processes" in result["response"]
        assert "test-laptop" in result["source_documents"][0]

    def test_chatbot_responds_to_gpu_query(self):
        """GPU query triggers GPU status template."""
        db = MagicMock()
        mock_snap = create_mock_snapshot(gpu_usage=44.2, gpu_temperature=65.0)
        db.query.return_value.options.return_value.filter.return_value.order_by.return_value.first.return_value = mock_snap
        
        result = generate_chatbot_response("test-laptop", "Check my GPU load and temperature", db)
        assert "GPU Status" in result["response"]
        assert "44.2%" in result["response"]
        assert "65.0°C" in result["response"]

    def test_chatbot_responds_to_battery_query(self):
        """Battery query triggers Battery status template."""
        db = MagicMock()
        mock_snap = create_mock_snapshot(battery_level=18.5, battery_health=82.0, power_source="battery")
        db.query.return_value.options.return_value.filter.return_value.order_by.return_value.first.return_value = mock_snap
        
        result = generate_chatbot_response("test-laptop", "Is my battery low?", db)
        assert "Battery Status" in result["response"]
        assert "18.5%" in result["response"]
        assert "82.0%" in result["response"]
        assert "Power source: BATTERY" in result["response"]
        assert "Battery is low" in result["response"]

    def test_chatbot_responds_to_disk_query(self):
        """Disk query triggers Disk status template."""
        db = MagicMock()
        mock_snap = create_mock_snapshot(disk_usage=91.2)
        db.query.return_value.options.return_value.filter.return_value.order_by.return_value.first.return_value = mock_snap
        
        result = generate_chatbot_response("test-laptop", "disk storage check", db)
        assert "Disk Status" in result["response"]
        assert "91.2%" in result["response"]
        assert "free space" in result["response"].lower() or "critical" in result["response"].lower()

    def test_chatbot_handles_multi_intent_query(self):
        """Query containing both CPU and Battery keywords triggers both responses combined."""
        db = MagicMock()
        mock_snap = create_mock_snapshot(cpu_usage=15.0, battery_level=95.0)
        db.query.return_value.options.return_value.filter.return_value.order_by.return_value.first.return_value = mock_snap
        
        result = generate_chatbot_response("test-laptop", "show cpu and battery health", db)
        assert "CPU Status" in result["response"]
        assert "Battery Status" in result["response"]
        assert "15.0%" in result["response"]
        assert "95.0%" in result["response"]

    def test_chatbot_off_topic_fallback(self):
        """General questions or off-topic queries return a descriptive capability limitation text."""
        db = MagicMock()
        result = generate_chatbot_response("test-laptop", "What is the capital of Japan?", db)
        assert "I can only answer questions related to your device's telemetry data" in result["response"]
        assert result["source_documents"] == []

    def test_chatbot_missing_snapshot_fallback(self):
        """When no database telemetry exists, return a user-friendly error response."""
        db = MagicMock()
        db.query.return_value.options.return_value.filter.return_value.order_by.return_value.first.return_value = None
        
        result = generate_chatbot_response("test-laptop", "Check battery level", db)
        assert "I couldn't find any telemetry data" in result["response"]
        assert "test-laptop" in result["response"]

    def test_chatbot_latency(self):
        """Ensure response generates in sub-millisecond range (wall clock)."""
        db = MagicMock()
        mock_snap = create_mock_snapshot()
        db.query.return_value.options.return_value.filter.return_value.order_by.return_value.first.return_value = mock_snap
        
        import time
        t0 = time.perf_counter()
        generate_chatbot_response("test-laptop", "status of cpu, gpu, disk, battery", db)
        elapsed = time.perf_counter() - t0
        # Success criteria is under 1 second, but deterministic rule matching is < 1 millisecond.
        assert elapsed < 0.1, f"Chatbot response took too long: {elapsed:.3f}s"
