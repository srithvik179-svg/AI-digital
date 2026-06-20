import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import uuid
from datetime import datetime

from app.main import app
from app.core.database import Base, get_db
from app.models.telemetry import (
    TelemetrySnapshot,
    CPUMetrics,
    GPUMetrics,
    MemoryMetrics,
    BatteryMetrics,
    DiskMetrics,
    WiFiMetrics,
    ThermalMetrics,
    PowerMetrics
)
from app.models.reasoning import ReasoningRule
from app.services.reasoning_engine import (
    get_metric_value,
    compare_values,
    evaluate_rule,
    evaluate_all_rules,
    seed_default_rules_if_empty
)

# Setup local SQLite database for fast unit testing, avoiding postgres interference
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_reasoning.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    app.dependency_overrides[get_db] = override_get_db
    # Create tables
    Base.metadata.create_all(bind=engine)
    yield
    # Drop tables
    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.pop(get_db, None)


def create_test_snapshot(device_id: str = "test-laptop-123") -> TelemetrySnapshot:
    """Helper to create a telemetry snapshot populated with known metrics."""
    snapshot = TelemetrySnapshot(
        id=str(uuid.uuid4()),
        device_id=device_id,
        timestamp=datetime.utcnow(),
        health_score=85.0,
        health_category="Healthy"
    )
    snapshot.cpu = CPUMetrics(
        cpu_usage=85.5,
        active_process_count=120,
        cpu_frequency_mhz=2900.0
    )
    snapshot.gpu = GPUMetrics(
        gpu_usage=45.0,
        gpu_temperature=72.0,
        gpu_memory_usage=15.0
    )
    snapshot.memory = MemoryMetrics(memory_usage=70.0, total_mb=16384.0, used_mb=11468.0)
    snapshot.battery = BatteryMetrics(
        battery_level=15.0,
        battery_health=90.0,
        battery_temperature=32.0,
        cycle_count=150
    )
    snapshot.disk = DiskMetrics(disk_usage=60.0, read_bytes_sec=1000, write_bytes_sec=5000)
    snapshot.wifi = WiFiMetrics(signal_strength_dbm=-75, ssid="Test_WiFi", link_speed_mbps=150)
    snapshot.thermal = ThermalMetrics(
        cpu_temperature=88.0,
        fan_speed_rpm=3500,
        thermal_state="serious"
    )
    snapshot.power = PowerMetrics(power_source="battery", power_draw_watts=15.0, voltage_mv=11200.0)
    return snapshot


# ─── VALUE EXTRACTION TESTS ───────────────────────────────────────────

def test_get_metric_value_flat():
    snapshot = create_test_snapshot()
    assert get_metric_value(snapshot, "cpu_usage") == 85.5
    assert get_metric_value(snapshot, "cpu_temperature") == 88.0
    assert get_metric_value(snapshot, "power_source") == "battery"
    assert get_metric_value(snapshot, "health_score") == 85.0


def test_get_metric_value_dotted():
    snapshot = create_test_snapshot()
    assert get_metric_value(snapshot, "cpu.cpu_usage") == 85.5
    assert get_metric_value(snapshot, "thermal.cpu_temperature") == 88.0
    assert get_metric_value(snapshot, "power.power_source") == "battery"
    assert get_metric_value(snapshot, "battery.cycle_count") == 150


def test_get_metric_value_missing():
    snapshot = create_test_snapshot()
    snapshot.gpu = None
    assert get_metric_value(snapshot, "gpu_usage") is None
    assert get_metric_value(snapshot, "gpu.gpu_temperature") is None
    assert get_metric_value(snapshot, "nonexistent_metric") is None


# ─── OPERATOR COMPARISON TESTS ────────────────────────────────────────

def test_compare_values_numeric():
    assert compare_values(85.0, ">", 80.0) is True
    assert compare_values(85.0, ">", 90.0) is False
    assert compare_values(15.0, "<", 20.0) is True
    assert compare_values(15.0, "<=", 15.0) is True
    assert compare_values(15.0, ">=", 15.0) is True
    assert compare_values(15.0, "==", 15.0) is True
    assert compare_values(15.0, "!=", 10.0) is True


def test_compare_values_string():
    assert compare_values("battery", "==", "battery") is True
    assert compare_values("AC", "==", "ac") is True  # Case insensitive
    assert compare_values("battery", "!=", "ac") is True
    assert compare_values("serious", "==", "serious") is True


# ─── RULE EVALUATION TESTS ────────────────────────────────────────────

def test_evaluate_rule_and_trigger():
    snapshot = create_test_snapshot()  # cpu_usage=85.5, cpu_temperature=88.0
    rule = ReasoningRule(
        id="test-thermal",
        name="Thermal Stress",
        conditions=[
            {"metric": "cpu_usage", "operator": ">", "value": 80.0},
            {"metric": "cpu_temperature", "operator": ">", "value": 85.0}
        ],
        logical_operator="AND",
        conclusion="Thermal Stress Throttling Required",
        severity="critical"
    )
    result = evaluate_rule(snapshot, rule)
    assert result["triggered"] is True
    assert "Thermal Stress" in result["explanation"]
    assert "cpu_usage" in result["evidence"]
    assert result["evidence"]["cpu_usage"] == 85.5
    assert result["severity"] == "critical"


def test_evaluate_rule_and_no_trigger():
    snapshot = create_test_snapshot()  # cpu_usage=85.5, cpu_temperature=88.0
    rule = ReasoningRule(
        id="test-thermal",
        name="Thermal Stress",
        conditions=[
            {"metric": "cpu_usage", "operator": ">", "value": 90.0},  # Fails
            {"metric": "cpu_temperature", "operator": ">", "value": 85.0}  # Passes
        ],
        logical_operator="AND",
        conclusion="Thermal Stress Throttling Required",
        severity="critical"
    )
    result = evaluate_rule(snapshot, rule)
    assert result["triggered"] is False
    assert "did not trigger" in result["explanation"]


def test_evaluate_rule_or_trigger():
    snapshot = create_test_snapshot()  # cpu_usage=85.5, battery_level=15.0
    rule = ReasoningRule(
        id="test-or-rule",
        name="Resource Warning",
        conditions=[
            {"metric": "cpu_usage", "operator": ">", "value": 90.0},  # Fails
            {"metric": "battery_level", "operator": "<", "value": 20.0}  # Passes
        ],
        logical_operator="OR",
        conclusion="Attention Required",
        severity="warning"
    )
    result = evaluate_rule(snapshot, rule)
    assert result["triggered"] is True
    assert "Resource Warning" in result["explanation"]


# ─── API ENDPOINT TESTS ───────────────────────────────────────────────

def test_api_list_rules_seeds_defaults():
    response = client.get("/api/v1/reasoning/rules")
    assert response.status_code == 200
    res_data = response.json()
    assert len(res_data) == 4
    rule_names = [r["name"] for r in res_data]
    assert "Thermal Stress Detection" in rule_names
    assert "System Overload" in rule_names


def test_api_create_rule():
    payload = {
        "name": "Excessive Fan Speed",
        "description": "Checks for excessive cooling requirements",
        "conditions": [
            {"metric": "fan_speed", "operator": ">", "value": 4000.0}
        ],
        "logical_operator": "AND",
        "conclusion": "High Heat Load",
        "severity": "warning",
        "is_active": True
    }
    response = client.post("/api/v1/reasoning/rules", json=payload)
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["name"] == "Excessive Fan Speed"
    assert res_data["id"].startswith("rule-")
    assert len(res_data["conditions"]) == 1


def test_api_update_rule():
    # First seed rules
    client.get("/api/v1/reasoning/rules")

    update_payload = {
        "name": "Modified Thermal Stress",
        "severity": "warning"
    }
    response = client.put("/api/v1/reasoning/rules/rule-thermal-stress", json=update_payload)
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["name"] == "Modified Thermal Stress"
    assert res_data["severity"] == "warning"


def test_api_delete_rule():
    # Seed rules
    client.get("/api/v1/reasoning/rules")

    response = client.delete("/api/v1/reasoning/rules/rule-thermal-stress")
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    # Confirm it is deleted
    db = TestingSessionLocal()
    rule = db.query(ReasoningRule).filter(ReasoningRule.id == "rule-thermal-stress").first()
    assert rule is None
    db.close()


def test_api_evaluate_rules():
    db = TestingSessionLocal()
    # 1. Create a snapshot in the db
    snapshot = create_test_snapshot(device_id="test-eval-laptop")
    db.add(snapshot)
    db.commit()
    db.close()

    # Call evaluate
    response = client.post("/api/v1/reasoning/evaluate/test-eval-laptop")
    assert response.status_code == 200
    res_data = response.json()
    assert len(res_data) >= 4  # Includes evaluated default rules

    # Thermal Stress should trigger for this snapshot because cpu_usage=85.5 (>80) and cpu_temperature=88.0 (>85)
    thermal_res = next(r for r in res_data if r["rule_id"] == "rule-thermal-stress")
    assert thermal_res["triggered"] is True
    assert "triggered" in thermal_res["explanation"]
    assert thermal_res["evidence"]["cpu_usage"] == 85.5
