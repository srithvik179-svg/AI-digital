"""
Unit tests for Phase 50 — Evidence-Driven Chatbot Engine.

Tests cover:
  1. Question classification across categories (Current Status, Diagnostics, RCA, Health Assessment, etc.)
  2. Rule engine deterministic condition evaluations.
  3. Prediction RUL degradation results over 7/30 days.
  4. Simulation converging temperature and fan speed.
  5. Format output parsing (Answer, Evidence, Reasoning, Confidence).
"""

from __future__ import annotations
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from app.models.telemetry import (
    TelemetrySnapshot, CPUMetrics, GPUMetrics, BatteryMetrics,
    DiskMetrics, PowerMetrics, ThermalMetrics, WiFiMetrics
)
from app.services.evidence_chatbot import (
    classify_question, run_rule_engine, query_evidence_chatbot
)

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def create_mock_snapshot(
    device_id: str = "test-laptop",
    cpu_usage: float = 22.0,
    cpu_temperature: float = 48.0,
    fan_speed: float = 1500.0,
    battery_level: float = 90.0,
    battery_health: float = 95.0,
    disk_usage: float = 40.0,
    wifi_rssi: float = -50.0,
    power_source: str = "ac",
    cycle_count: int = 150
) -> TelemetrySnapshot:
    snap = TelemetrySnapshot(
        id="mock-snapshot-123",
        device_id=device_id,
        timestamp=datetime.utcnow()
    )
    snap.cpu = CPUMetrics(cpu_usage=cpu_usage, active_process_count=85, cpu_frequency_mhz=2400.0)
    snap.gpu = GPUMetrics(gpu_usage=12.0, gpu_temperature=45.0, gpu_memory_usage=15.0)
    snap.battery = BatteryMetrics(battery_level=battery_level, battery_health=battery_health, cycle_count=cycle_count)
    snap.disk = DiskMetrics(disk_usage=disk_usage, read_bytes_sec=1048576, write_bytes_sec=524288)
    snap.power = PowerMetrics(power_source=power_source)
    snap.thermal = ThermalMetrics(cpu_temperature=cpu_temperature, fan_speed_rpm=fan_speed)
    snap.wifi = WiFiMetrics(signal_strength_dbm=wifi_rssi, link_speed_mbps=150.0)
    return snap


def _mock_db(snapshots: list = None):
    db = MagicMock()
    if snapshots is None:
        snapshots = [create_mock_snapshot()]
    
    # Configure mock chains
    db.query.return_value.options.return_value.filter.return_value.order_by.return_value.first.return_value = snapshots[0]
    db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = snapshots
    db.query.return_value.filter.return_value.all.return_value = []
    return db


# ─────────────────────────────────────────────────────────────────────────────
# 1. Question Classification Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestQuestionClassification:

    def test_current_status_queries(self):
        assert classify_question("What is CPU usage?") == "Current Status"
        assert classify_question("get battery level") == "Current Status"
        assert classify_question("show wifi strength") == "Current Status"

    def test_diagnostics_queries(self):
        assert classify_question("Why is my laptop slow?") == "Diagnostics"
        assert classify_question("why is battery draining?") == "Diagnostics"

    def test_rca_queries(self):
        assert classify_question("Why is my laptop overheating?") == "Root Cause Analysis"
        assert classify_question("what is the root cause of high temp?") == "Root Cause Analysis"

    def test_health_queries(self):
        assert classify_question("How healthy is my laptop?") == "Health Assessment"
        assert classify_question("what is the laptop health score?") == "Health Assessment"

    def test_recommendation_queries(self):
        assert classify_question("How can I improve battery life?") == "Recommendations"
        assert classify_question("What are the recommendations to reduce temp?") == "Recommendations"

    def test_correlation_queries(self):
        assert classify_question("Does CPU affect temperature?") == "Correlation Analysis"
        assert classify_question("does temp affect fan speed?") == "Correlation Analysis"

    def test_prediction_queries(self):
        assert classify_question("How will my laptop condition be after 30 days?") == "Prediction"
        assert classify_question("battery health forecast") == "Prediction"

    def test_simulation_queries(self):
        assert classify_question("What happens if CPU reaches 95%?") == "Simulation"
        assert classify_question("What if battery health drops below 60%?") == "Simulation"


# ─────────────────────────────────────────────────────────────────────────────
# 2. Rule Engine Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestDeterministicRules:

    def test_rules_dont_trigger_when_nominal(self):
        snap = create_mock_snapshot(cpu_temperature=55.0, battery_health=95.0, disk_usage=40.0, wifi_rssi=-40)
        triggered = run_rule_engine(snap)
        assert len(triggered) == 0

    def test_rules_trigger_on_elevated_temperature(self):
        snap = create_mock_snapshot(cpu_temperature=92.0)
        triggered = run_rule_engine(snap)
        assert any("Thermal Stress" in r for r in triggered)

    def test_rules_trigger_on_degraded_battery(self):
        snap = create_mock_snapshot(battery_health=70.0)
        triggered = run_rule_engine(snap)
        assert any("Battery Risk" in r for r in triggered)

    def test_rules_trigger_on_disk_exhaustion(self):
        snap = create_mock_snapshot(disk_usage=95.0)
        triggered = run_rule_engine(snap)
        assert any("Storage Failure Risk" in r for r in triggered)

    def test_rules_trigger_on_poor_wifi(self):
        # RSSI = -85 -> Strength = 2*(15) = 30% (< 50%)
        snap = create_mock_snapshot(wifi_rssi=-85.0)
        triggered = run_rule_engine(snap)
        assert any("Connectivity Risk" in r for r in triggered)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Chatbot Integration & Response Formatting Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestEvidenceChatbotResponse:

    def test_response_format_structure(self):
        db = _mock_db()
        result = query_evidence_chatbot("test-device", "What is CPU usage?", db)
        
        response = result["response"]
        assert response.startswith("Answer:")
        assert "Evidence:" in response
        assert "Reasoning:" in response
        assert "Confidence:" in response

    def test_current_status_response_grounding(self):
        db = _mock_db([create_mock_snapshot(cpu_usage=78.2)])
        result = query_evidence_chatbot("test-device", "What is CPU usage?", db)
        response = result["response"]
        
        assert "78.2%" in response
        assert "Confidence:\n100%" in response

    def test_simulation_response_calculation(self):
        db = _mock_db()
        # "What happens if CPU reaches 95%?" -> simulation engine calculates steady state temperature
        result = query_evidence_chatbot("test-device", "What happens if CPU reaches 95%?", db)
        response = result["response"]
        
        assert "Simulation projections:" in response
        assert "Confidence:\n90%" in response

    def test_prediction_response_degradation(self):
        db = _mock_db([create_mock_snapshot(battery_health=90.0)])
        # "How will battery condition be after 30 days?"
        # expected Battery Health projection: 90 - (0.02 * 30) = 89.4%
        result = query_evidence_chatbot("test-device", "How will my laptop condition be after 30 days?", db)
        response = result["response"]
        
        assert "Battery Health is projected to decline to 89.4%" in response

    def test_insufficient_data_safe_refusal(self):
        db = _mock_db()
        # Querying an unknown out-of-scope query
        result = query_evidence_chatbot("test-device", "Tell me a joke about laptops", db)
        response = result["response"]
        
        assert "Insufficient telemetry data available" in response
        assert "Confidence:\n0%" in response

    def test_historical_mode_isolation(self):
        db = _mock_db()
        # Historical mode must refuse predictions, simulations, and current status
        r1 = query_evidence_chatbot("test-device", "How will battery condition be after 30 days?", db, mode="historical")
        assert "Predictions, simulations, and live status are only available in the Live AI Digital Twin" in r1["response"]

        r2 = query_evidence_chatbot("test-device", "What happens if CPU reaches 95%?", db, mode="historical")
        assert "Predictions, simulations, and live status are only available in the Live AI Digital Twin" in r2["response"]

        r3 = query_evidence_chatbot("test-device", "What is CPU usage?", db, mode="historical")
        assert "Predictions, simulations, and live status are only available in the Live AI Digital Twin" in r3["response"]

    def test_live_mode_isolation(self):
        db = _mock_db()
        # Live mode must refuse trend analysis, correlation analysis, and root cause analysis
        r1 = query_evidence_chatbot("test-device", "what is the root cause of high temp?", db, mode="live")
        assert "Historical trends, correlations, and root cause analysis are only available in the Historical Telemetry Intelligence" in r1["response"]

        r2 = query_evidence_chatbot("test-device", "show me the wear trend", db, mode="live")
        assert "Historical trends, correlations, and root cause analysis are only available in the Historical Telemetry Intelligence" in r2["response"]

        r3 = query_evidence_chatbot("test-device", "Does CPU affect temperature?", db, mode="live")
        assert "Historical trends, correlations, and root cause analysis are only available in the Historical Telemetry Intelligence" in r3["response"]
