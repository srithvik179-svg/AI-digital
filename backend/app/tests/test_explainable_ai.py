"""
Unit tests for Phase 38 Explainable AI Service.
"""
import pytest
from unittest.mock import MagicMock
from app.services.ai_reasoning.explainable_ai import (
    explain_health_score,
    explain_health_classification,
    explain_temperature_forecast,
    explain_prediction
)

def test_explain_health_score_healthy():
    """For a perfectly healthy device, attributions return baseline weights summing to 100%."""
    metrics = {
        "cpu_usage": 10.0,
        "memory_usage": 20.0,
        "disk_usage": 30.0,
        "cpu_temperature": 45.0,
        "battery_level": 100.0,
        "battery_health": 100.0,
        "gpu_usage": 5.0,
        "signal_strength_dbm": -50,
        "power_source": "ac",
        "thermal_state": "nominal"
    }
    
    attributions = explain_health_score(metrics)
    
    assert len(attributions) == 7
    assert sum(attributions.values()) == pytest.approx(100.0)
    # CPU weight is 22%, temperature weight is 22%
    assert attributions["cpu"] == 22.0
    assert attributions["temperature"] == 22.0

def test_explain_health_score_degraded():
    """For a degraded device (e.g., high CPU & temp), those features dominate the attributions."""
    metrics = {
        "cpu_usage": 95.0,        # CPU score will be 0 (100% penalty)
        "memory_usage": 20.0,
        "disk_usage": 30.0,
        "cpu_temperature": 95.0,  # Temp score will be 0 (100% penalty)
        "battery_level": 100.0,
        "battery_health": 100.0,
        "gpu_usage": 5.0,
        "signal_strength_dbm": -50,
        "power_source": "ac",
        "thermal_state": "nominal"
    }
    
    attributions = explain_health_score(metrics)
    assert sum(attributions.values()) == pytest.approx(100.0)
    
    # CPU and temperature should have the highest attributions
    assert attributions["cpu"] > 10.0
    assert attributions["temperature"] > 10.0
    # Perfect ones (like memory, battery) should be 0.0
    assert attributions["memory"] == 0.0
    assert attributions["battery"] == 0.0

def test_explain_health_classification():
    """Assert classifier attributions sum to 100% and identify active splits."""
    metrics = {
        "cpu_usage": 80.0,
        "cpu_temperature": 85.0,
        "memory_usage": 70.0,
        "fan_rpm": 4000.0,
        "battery_level": 15.0,
        "power_source": "battery"
    }
    
    attributions = explain_health_classification(metrics)
    assert sum(attributions.values()) == pytest.approx(100.0)
    
    # Verify we got keys for the features
    for key in ["cpu_usage", "cpu_temperature", "memory_usage", "fan_rpm", "battery_level", "on_battery"]:
        assert key in attributions

def test_explain_temperature_forecast():
    """Assert lag attributions sum to 100% and provide all 10 lags."""
    attributions = explain_temperature_forecast()
    
    assert len(attributions) == 10
    assert sum(attributions.values()) == pytest.approx(100.0)
    for i in range(10):
        assert f"lag_{i+1}" in attributions

def test_explain_prediction_fallback():
    """Assert explain_prediction works even when no DB snapshots exist (uses default fallbacks)."""
    db = MagicMock()
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
    
    result = explain_prediction("test-laptop", db)
    
    assert "health_score_attributions" in result
    assert "classification_attributions" in result
    assert "forecast_attributions" in result
    assert "predicted_tier" in result
    assert "health_score" in result
    
    assert sum(result["health_score_attributions"].values()) == pytest.approx(100.0)
    assert sum(result["classification_attributions"].values()) == pytest.approx(100.0)
    assert sum(result["forecast_attributions"].values()) == pytest.approx(100.0)
