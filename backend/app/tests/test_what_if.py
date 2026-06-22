"""
Unit tests for Phase 41 What-If Simulation Engine.
"""
import pytest
import time
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_simulation_success():
    """Ensure basic simulation request returns complete prediction schema."""
    req_body = {
        "cpu_usage": 30.0,
        "gpu_usage": 10.0,
        "memory_usage": 50.0,
        "battery_level": 80.0,
        "battery_health": 90.0,
        "power_source": "battery",
        "ambient_temperature": 25.0
    }
    
    response = client.post("/api/v1/what-if-simulation/simulate", json=req_body)
    assert response.status_code == 200
    data = response.json()
    
    # Assert Temperature Predictions
    assert "temperature" in data
    assert "cpu_temperature" in data["temperature"]
    assert "fan_speed_rpm" in data["temperature"]
    assert "thermal_state" in data["temperature"]
    assert "is_throttling" in data["temperature"]
    assert "throttle_ratio" in data["temperature"]
    
    # Assert Power Predictions
    assert "power" in data
    assert "total_power_draw_watts" in data["power"]
    assert "cpu_power_draw_watts" in data["power"]
    
    # Assert Battery Predictions
    assert "battery" in data
    assert "battery_status" in data["battery"]
    assert "battery_drain_rate_percent_per_hour" in data["battery"]
    assert "battery_remaining_minutes" in data["battery"]

def test_simulation_heavy_load_throttling():
    """Ensure heavy CPU/GPU workload triggers thermal throttling and serious/critical states."""
    req_body = {
        "cpu_usage": 95.0,
        "gpu_usage": 80.0,
        "memory_usage": 80.0,
        "battery_level": 80.0,
        "battery_health": 90.0,
        "power_source": "battery",
        "ambient_temperature": 25.0
    }
    
    response = client.post("/api/v1/what-if-simulation/simulate", json=req_body)
    assert response.status_code == 200
    data = response.json()
    
    temp_data = data["temperature"]
    # Under 95% CPU and 80% GPU load, temperature should be high and throttling should engage
    assert temp_data["cpu_temperature"] > 75.0
    assert temp_data["thermal_state"] in ["serious", "critical"]
    if temp_data["cpu_temperature"] >= 85.0:
        assert temp_data["is_throttling"] is True
        assert temp_data["throttle_ratio"] < 1.0
        
    # High workload power draw should be significantly higher than idle
    assert data["power"]["total_power_draw_watts"] > 25.0

def test_simulation_battery_vs_ac():
    """Verify differences between discharging on battery and charging on AC power."""
    # 1. On Battery
    bat_req = {
        "cpu_usage": 40.0,
        "power_source": "battery"
    }
    response = client.post("/api/v1/what-if-simulation/simulate", json=bat_req)
    assert response.status_code == 200
    bat_data = response.json()["battery"]
    assert bat_data["battery_status"] == "discharging"
    assert bat_data["battery_drain_rate_percent_per_hour"] > 0.0
    assert bat_data["battery_charge_rate_percent_per_hour"] == 0.0
    assert bat_data["battery_remaining_minutes"] > 0.0

    # 2. On AC (charging)
    ac_req = {
        "cpu_usage": 40.0,
        "battery_level": 50.0,
        "power_source": "ac"
    }
    response = client.post("/api/v1/what-if-simulation/simulate", json=ac_req)
    assert response.status_code == 200
    ac_data = response.json()["battery"]
    assert ac_data["battery_status"] == "charging"
    assert ac_data["battery_drain_rate_percent_per_hour"] == 0.0
    assert ac_data["battery_charge_rate_percent_per_hour"] > 0.0
    assert ac_data["battery_remaining_minutes"] > 0.0

def test_validation_boundaries():
    """Ensure invalid load ranges are rejected by Pydantic validation."""
    invalid_req = {
        "cpu_usage": 150.0,  # Invalid
        "power_source": "battery"
    }
    response = client.post("/api/v1/what-if-simulation/simulate", json=invalid_req)
    assert response.status_code == 422  # Validation Error

def test_simulation_latency():
    """Verify that steady-state calculation completes in sub-10ms (real-time success criteria)."""
    req_body = {
        "cpu_usage": 50.0,
        "gpu_usage": 20.0,
        "memory_usage": 50.0,
        "battery_level": 80.0,
        "battery_health": 90.0,
        "power_source": "battery"
    }
    
    t0 = time.perf_counter()
    response = client.post("/api/v1/what-if-simulation/simulate", json=req_body)
    elapsed = (time.perf_counter() - t0) * 1000.0  # in ms
    
    assert response.status_code == 200
    assert elapsed < 10.0, f"What-If Simulation engine was too slow: {elapsed:.2f}ms"
