"""
Unit tests for the Phase 11 Digital Twin Core Model and Simulator.
Validates object-oriented state transitions, wear projections, and thermodynamic equations.
"""
import pytest
from unittest.mock import MagicMock
from datetime import datetime

from app.services.digital_twin_model import VirtualLaptop
from app.models.telemetry import TelemetrySnapshot, CPUMetrics, GPUMetrics, MemoryMetrics, BatteryMetrics, DiskMetrics, WiFiMetrics, ThermalMetrics, PowerMetrics

# ─── Helpers ──────────────────────────────────────────────────────────

def create_telemetry_snapshot(
    device_id: str = "test-laptop",
    cpu_usage: float = 15.0,
    active_process_count: int = 80,
    cpu_frequency_mhz: float = 2400.0,
    gpu_usage: float = 5.0,
    gpu_temperature: float = 42.0,
    gpu_memory_usage: float = 10.0,
    battery_level: float = 85.0,
    battery_health: float = 94.0,
    battery_temperature: float = 30.0,
    cycle_count: int = 180,
    power_source: str = "ac",
    disk_usage: float = 30.0,
    read_bytes_sec: int = 1024,
    write_bytes_sec: int = 2048,
    cpu_temperature: float = 48.0,
    fan_speed_rpm: int = 1200,
    thermal_state: str = "nominal",
    health_score: float = 95.0,
    health_category: str = "Healthy"
) -> TelemetrySnapshot:
    """Create a fully populated mock TelemetrySnapshot database model."""
    s = TelemetrySnapshot(id="test-snap", device_id=device_id, timestamp=datetime.utcnow(), health_score=health_score, health_category=health_category)
    s.cpu = CPUMetrics(cpu_usage=cpu_usage, active_process_count=active_process_count, cpu_frequency_mhz=cpu_frequency_mhz)
    s.gpu = GPUMetrics(gpu_usage=gpu_usage, gpu_temperature=gpu_temperature, gpu_memory_usage=gpu_memory_usage)
    s.memory = MemoryMetrics(memory_usage=40.0)
    s.battery = BatteryMetrics(battery_level=battery_level, battery_health=battery_health, battery_temperature=battery_temperature, cycle_count=cycle_count)
    s.disk = DiskMetrics(disk_usage=disk_usage, read_bytes_sec=read_bytes_sec, write_bytes_sec=write_bytes_sec)
    s.wifi = WiFiMetrics(signal_strength_dbm=-50, link_speed_mbps=300, ssid="MyWiFi")
    s.thermal = ThermalMetrics(cpu_temperature=cpu_temperature, fan_speed_rpm=fan_speed_rpm, thermal_state=thermal_state)
    s.power = PowerMetrics(power_source=power_source)
    return s


# ─── Tests ────────────────────────────────────────────────────────────

class TestDigitalTwinStateEngine:
    def test_state_updates_subcomponents_correctly(self):
        """VirtualLaptop updates all virtual sub-components from snapshot correctly."""
        snapshot = create_telemetry_snapshot(
            cpu_usage=55.0,
            cpu_temperature=72.0,
            battery_level=42.0,
            power_source="battery",
            disk_usage=68.0,
        )
        
        laptop = VirtualLaptop("test-device")
        laptop.update_state(snapshot)
        
        assert laptop.device_id == "test-device"
        assert laptop.cpu.current_usage == 55.0
        assert laptop.thermal.cpu_temperature == 72.0
        assert laptop.battery.level == 42.0
        assert laptop.battery.power_source == "battery"
        assert laptop.disk.usage == 68.0
        assert laptop.health_score == 95.0

    def test_cpu_rolling_average(self):
        """CPU sub-system maintains rolling average of load entries."""
        laptop = VirtualLaptop("test-device")
        
        # Stream 12 updates
        for load in [10.0] * 5 + [20.0] * 5 + [30.0] * 2:
            snap = create_telemetry_snapshot(cpu_usage=load)
            laptop.update_state(snap)
            
        # The history size is capped at 10, so it should only evaluate last 10 entries:
        # 3x 10.0 + 5x 20.0 + 2x 30.0 = (30 + 100 + 60) / 10 = 19.0
        assert len(laptop.cpu.historical_load) == 10
        assert laptop.cpu.load_average == 19.0

    def test_battery_wear_and_lifetime_projection(self):
        """Battery wear and remaining days projections map cycle counts and health correctly."""
        laptop = VirtualLaptop("test-device")
        
        snap = create_telemetry_snapshot(cycle_count=400, battery_health=85.0)
        laptop.update_state(snap)
        
        # Wear project relative to 1000 limit
        assert laptop.battery.estimated_wear_percentage == 40.0
        # Days remaining before health drops to 70% threshold: (85 - 70) / 0.03 = 500 days
        assert laptop.battery.lifetime_projection_days == 500.0

    def test_thermal_target_fan_speeds(self):
        """Target fan speeds scale correctly with temperature thresholds."""
        laptop = VirtualLaptop("test-device")
        
        # Nominal temperature
        laptop.update_state(create_telemetry_snapshot(cpu_temperature=45.0))
        assert laptop.thermal.target_fan_speed_rpm == 1200
        
        # Warm temperature
        laptop.update_state(create_telemetry_snapshot(cpu_temperature=70.0))
        assert laptop.thermal.target_fan_speed_rpm == 3500
        
        # Hot temperature
        laptop.update_state(create_telemetry_snapshot(cpu_temperature=88.0))
        assert laptop.thermal.target_fan_speed_rpm == 6000

    def test_workload_simulation_thermodynamics(self):
        """Workload simulation runs correct thermodynamic equations (heats up, spins fans, drains battery)."""
        laptop = VirtualLaptop("test-device")
        
        # Set initial baseline
        snap = create_telemetry_snapshot(cpu_temperature=50.0, battery_level=90.0, power_source="battery")
        laptop.update_state(snap)
        
        # Simulate heavy CPU workload (100% CPU, 0% GPU) for 15 minutes
        result = laptop.simulate_workload(cpu_load=100.0, gpu_load=0.0, duration_mins=15.0)
        
        # Temperature must rise
        assert result["projected_state"]["cpu_temperature"] > 50.0
        # Fan RPM must increase due to heat
        assert result["projected_state"]["fan_speed_rpm"] >= 4000
        # Battery level must drain
        assert result["projected_state"]["battery_level"] < 90.0
        # Power draw is projected
        assert result["projected_state"]["power_draw_watts"] > 10.0
