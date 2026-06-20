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
from app.models.relationship import TelemetryRelationship
from app.services.rca_engine import (
    get_snapshot_alerts,
    run_dependency_graph_rca,
    run_rca_analysis
)

# Setup local SQLite database for fast unit testing, avoiding postgres interference
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_rca.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    # Setup override inside fixture for clean session teardown
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.pop(get_db, None)


def create_test_snapshot(
    cpu_usage=30.0, 
    cpu_temp=50.0, 
    fan_speed=2000, 
    battery_level=80.0,
    battery_health=90.0,
    power_draw=15.0,
    wifi_speed=150,
    wifi_rssi=-50
) -> TelemetrySnapshot:
    """Helper to create a telemetry snapshot populated with custom metrics."""
    snapshot = TelemetrySnapshot(
        id=str(uuid.uuid4()),
        device_id="test-laptop-rca",
        timestamp=datetime.utcnow(),
        health_score=85.0,
        health_category="Healthy"
    )
    snapshot.cpu = CPUMetrics(cpu_usage=cpu_usage, active_process_count=120, cpu_frequency_mhz=2900.0)
    snapshot.gpu = GPUMetrics(gpu_usage=10.0, gpu_temperature=45.0, gpu_memory_usage=5.0)
    snapshot.memory = MemoryMetrics(memory_usage=70.0, total_mb=16384.0, used_mb=11468.0)
    snapshot.battery = BatteryMetrics(
        battery_level=battery_level,
        battery_health=battery_health,
        battery_temperature=32.0,
        cycle_count=150
    )
    snapshot.disk = DiskMetrics(disk_usage=60.0, read_bytes_sec=1000, write_bytes_sec=5000)
    snapshot.wifi = WiFiMetrics(signal_strength_dbm=wifi_rssi, ssid="Test_WiFi", link_speed_mbps=wifi_speed)
    snapshot.thermal = ThermalMetrics(
        cpu_temperature=cpu_temp,
        fan_speed_rpm=fan_speed,
        thermal_state="nominal"
    )
    snapshot.power = PowerMetrics(power_source="battery", power_draw_watts=power_draw, voltage_mv=11200.0)
    return snapshot


# ─── DECISION TREE PROFILE TESTS ──────────────────────────────────────

def test_rca_nominal_operation():
    db = TestingSessionLocal()
    snapshot = create_test_snapshot()
    diagnoses = run_rca_analysis(snapshot, db)
    db.close()

    assert len(diagnoses) == 1
    assert diagnoses[0]["cause"] == "Normal Operation"
    assert diagnoses[0]["confidence"] == 1.0


def test_rca_cpu_workload_storm():
    db = TestingSessionLocal()
    # High CPU usage and high CPU temp will trigger alerts
    snapshot = create_test_snapshot(cpu_usage=85.0, cpu_temp=89.0, fan_speed=4000)
    diagnoses = run_rca_analysis(snapshot, db)
    db.close()

    # Should diagnose CPU Workload Storm
    cpu_diag = next(d for d in diagnoses if d["cause"] == "CPU Workload Storm")
    assert cpu_diag["confidence"] >= 0.8
    assert "CPU Load is elevated" in cpu_diag["evidence"][1]


def test_rca_cooling_fan_failure():
    db = TestingSessionLocal()
    # High CPU temp but fan speed is critically low
    snapshot = create_test_snapshot(cpu_usage=20.0, cpu_temp=89.0, fan_speed=800)
    diagnoses = run_rca_analysis(snapshot, db)
    db.close()

    fan_diag = next(d for d in diagnoses if d["cause"] == "Cooling Fan Mechanical Failure")
    assert fan_diag["confidence"] == 0.90
    assert "Fan Speed is critically low" in fan_diag["evidence"][1]


def test_rca_battery_cell_degradation():
    db = TestingSessionLocal()
    # Battery health alert will trigger at health < 75%
    snapshot = create_test_snapshot(battery_health=60.0)
    diagnoses = run_rca_analysis(snapshot, db)
    db.close()

    bat_diag = next(d for d in diagnoses if d["cause"] == "Battery Cell Degradation")
    assert bat_diag["confidence"] == 0.95


# ─── CORRELATION GRAPH TESTS ──────────────────────────────────────────

def test_rca_dependency_graph_traversal():
    db = TestingSessionLocal()
    # Insert relationships: cpu_usage influences cpu_temperature
    rel = TelemetryRelationship(
        id=str(uuid.uuid4()),
        device_id="test-laptop-rca",
        source_node="cpu_usage",
        target_node="cpu_temperature",
        relationship_type="influences",
        correlation_strength=0.85,
        dependency_description="CPU load drives heat generation"
    )
    db.add(rel)
    db.commit()

    # Active metrics CPU Usage and CPU Temp both alerted
    scores = run_dependency_graph_rca(["cpu_usage", "cpu_temperature"], "test-laptop-rca", db)
    db.close()

    # cpu_usage is source -> score should increase (1.0 + 0.85 = 1.85)
    # cpu_temperature is target -> score should decrease (1.0 - 0.425 = 0.575)
    assert scores["cpu_usage"] == 1.85
    assert scores["cpu_temperature"] == 0.575


# ─── REST ENDPOINT TESTS ───────────────────────────────────────────────

def test_api_rca_endpoint():
    db = TestingSessionLocal()
    # 1. Create a snapshot in the db (causing cooling fan failure)
    snapshot = create_test_snapshot(cpu_usage=20.0, cpu_temp=89.0, fan_speed=800)
    db.add(snapshot)
    db.commit()
    db.close()

    # Call endpoint
    response = client.post("/api/v1/rca/analyze/test-laptop-rca")
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["device_id"] == "test-laptop-rca"
    assert len(res_data["diagnoses"]) >= 1

    fan_diag = next(d for d in res_data["diagnoses"] if d["cause"] == "Cooling Fan Mechanical Failure")
    assert fan_diag["confidence"] == 0.90
    assert "Cooling Fan Mechanical Failure" in fan_diag["cause"]
