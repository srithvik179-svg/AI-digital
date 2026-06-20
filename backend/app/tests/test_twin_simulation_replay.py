"""
Unit tests for Laptop Telemetry Digital Twin simulation step math, historical replay, and what-if scenarios.
"""
import pytest
from unittest.mock import MagicMock
from datetime import datetime, timedelta
from app.services.digital_twin_model import VirtualLaptop
from app.api.v1.twin_state import get_historical_replay, simulate_what_if_scenario
from app.schemas.telemetry import WhatIfRequest
from app.models.telemetry import (
    TelemetrySnapshot, CPUMetrics, GPUMetrics, MemoryMetrics,
    BatteryMetrics, DiskMetrics, WiFiMetrics, ThermalMetrics, PowerMetrics
)

# ─── Helpers ──────────────────────────────────────────────────────────

def create_telemetry_snapshot(
    device_id: str = "test-laptop",
    cpu_usage: float = 15.0,
    cpu_temperature: float = 48.0,
    battery_level: float = 85.0,
    fan_speed_rpm: int = 1200,
    power_source: str = "battery",
    timestamp: datetime = None
) -> TelemetrySnapshot:
    """Create a mock TelemetrySnapshot database model."""
    ts = timestamp or datetime.utcnow()
    s = TelemetrySnapshot(id="test-snap", device_id=device_id, timestamp=ts, health_score=95.0, health_category="Healthy")
    s.cpu = CPUMetrics(cpu_usage=cpu_usage, active_process_count=80, cpu_frequency_mhz=2400.0)
    s.gpu = GPUMetrics(gpu_usage=5.0, gpu_temperature=42.0, gpu_memory_usage=10.0)
    s.memory = MemoryMetrics(memory_usage=40.0)
    s.battery = BatteryMetrics(battery_level=battery_level, battery_health=94.0, battery_temperature=30.0, cycle_count=180)
    s.disk = DiskMetrics(disk_usage=30.0, read_bytes_sec=1024, write_bytes_sec=2048)
    s.wifi = WiFiMetrics(signal_strength_dbm=-50, link_speed_mbps=300, ssid="MyWiFi")
    s.thermal = ThermalMetrics(cpu_temperature=cpu_temperature, fan_speed_rpm=fan_speed_rpm, thermal_state="nominal")
    s.power = PowerMetrics(power_source=power_source)
    return s


# ─── Tests ────────────────────────────────────────────────────────────

class TestDigitalTwinSimulationReplay:
    def test_step_simulation_dissipation_and_throttling(self):
        """Simulation steps update temperatures, ramp fan speed, and throttle clock frequency at high temp."""
        laptop = VirtualLaptop("test-device")
        
        # Start hot at 84°C
        snap = create_telemetry_snapshot(cpu_temperature=84.0, fan_speed_rpm=3000)
        laptop.update_state(snap)
        
        # 1. Run 1 step with heavy load. Temp should rise above 85°C.
        state1 = laptop.step_simulation(cpu_load=100.0, gpu_load=20.0, delta_t_mins=1.0)
        t1 = state1["components"]["thermal"]["cpu_temperature"]
        assert t1 > 84.0
        
        # 2. Run another step. Frequency throttling should react to the high temperature of step 1.
        state2 = laptop.step_simulation(cpu_load=100.0, gpu_load=20.0, delta_t_mins=1.0)
        freq2 = state2["components"]["cpu"]["frequency_mhz"]
        assert freq2 < 3500.0
        
        # 3. Fan speed should be ramping up towards target
        fan1 = state1["components"]["thermal"]["fan_speed_rpm"]
        assert fan1 > 3000  # Ramps up by 1000 RPM per minute

    def test_battery_charging_discharge_dynamics(self):
        """Battery charges when on AC power and discharges based on component load when on Battery."""
        # Charging check
        laptop_ac = VirtualLaptop("test-device")
        snap_ac = create_telemetry_snapshot(battery_level=50.0, power_source="ac")
        laptop_ac.update_state(snap_ac)
        
        state_ac = laptop_ac.step_simulation(cpu_load=20.0, gpu_load=0.0, power_source="ac", delta_t_mins=10.0)
        assert state_ac["components"]["battery"]["level"] > 50.0
        assert state_ac["components"]["battery"]["power_source"] == "ac"

        # Discharging check
        laptop_bat = VirtualLaptop("test-device")
        snap_bat = create_telemetry_snapshot(battery_level=50.0, power_source="battery")
        laptop_bat.update_state(snap_bat)
        
        state_bat = laptop_bat.step_simulation(cpu_load=80.0, gpu_load=50.0, power_source="battery", delta_t_mins=10.0)
        assert state_bat["components"]["battery"]["level"] < 50.0
        assert state_bat["components"]["battery"]["power_source"] == "battery"
        # Health wear should be applied
        assert state_bat["components"]["battery"]["health"] < 94.0

    def test_historical_replay_endpoint_flow(self):
        """Historical replay endpoint queries chronologically and applies sequential simulation tracking."""
        db = MagicMock()
        
        # Create 3 sequential snapshots in descending order (newest first)
        t_base = datetime(2026, 6, 20, 12, 0, 0)
        snaps = [
            create_telemetry_snapshot(timestamp=t_base, cpu_usage=30.0),
            create_telemetry_snapshot(timestamp=t_base - timedelta(minutes=5), cpu_usage=20.0),
            create_telemetry_snapshot(timestamp=t_base - timedelta(minutes=10), cpu_usage=10.0)
        ]
        
        # Mock database query
        db.query.return_value.options.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = snaps
        
        results = get_historical_replay(device_id="test-laptop", limit=3, db=db)
        
        assert len(results) == 3
        # Check chronological order (oldest first after get_historical_replay reverses desc snaps)
        assert results[0]["timestamp"] < results[1]["timestamp"]
        assert results[1]["timestamp"] < results[2]["timestamp"]
        
        # Check twin state availability
        assert "twin_state" in results[0]
        assert results[0]["twin_state"]["components"]["cpu"]["current_usage"] == 10.0
        assert results[2]["twin_state"]["components"]["cpu"]["current_usage"] == 30.0

    def test_what_if_scenario_simulation_endpoint(self):
        """What-If scenario projection returns structured step projections and correct timestamp increments."""
        db = MagicMock()
        
        t_base = datetime(2026, 6, 20, 12, 0, 0)
        snap = create_telemetry_snapshot(timestamp=t_base, cpu_temperature=55.0, battery_level=90.0, power_source="battery")
        
        # Mock database query for starting snap search
        db.query.return_value.options.return_value.filter.return_value.filter.return_value.order_by.return_value.first.return_value = snap
        
        payload = WhatIfRequest(
            device_id="test-laptop",
            start_timestamp=t_base,
            cpu_load=90.0,
            gpu_load=50.0,
            duration_minutes=5.0,
            power_source="battery"
        )
        
        results = simulate_what_if_scenario(payload=payload, db=db)
        
        assert len(results) == 5
        # Verify timestamp incrementing minute-by-minute
        first_step_time = datetime.fromisoformat(results[0]["timestamp"])
        last_step_time = datetime.fromisoformat(results[4]["timestamp"])
        
        assert first_step_time == t_base + timedelta(minutes=1)
        assert last_step_time == t_base + timedelta(minutes=5)
        
        # Temperatures should rise step-by-step
        assert results[4]["cpu_temperature"] > results[0]["cpu_temperature"]
        # Battery should drain step-by-step
        assert results[4]["battery_level"] < results[0]["battery_level"]
        # Standard indicators must be flattened in outer list dict
        assert "cpu_usage" in results[0]
        assert "cpu_temperature" in results[0]
        assert "battery_level" in results[0]
        assert "fan_speed" in results[0]
