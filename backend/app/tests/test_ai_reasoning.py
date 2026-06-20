import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import uuid
from datetime import datetime, timedelta

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
from app.services.ai_reasoning.multi_factor import MultiFactorReasoning
from app.services.ai_reasoning.recommender import RecommendationEngine
from app.services.ai_reasoning.classifier import HealthClassifier
from app.services.ai_reasoning.predictor import TrendPredictor
from app.services.ai_reasoning.anomaly import AnomalyDetector
from app.services.ai_reasoning.failure_prediction import FailurePredictor
from app.services.ai_reasoning.confidence import ConfidenceScorer
from app.services.ai_reasoning.orchestrator import AIReasoningOrchestrator

# Setup local SQLite database for fast unit testing, avoiding postgres interference
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_ai_reasoning.db"
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
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.pop(get_db, None)

def create_test_snapshot(
    device_id="test-laptop-ai",
    timestamp=None,
    cpu_usage=30.0,
    cpu_temp=50.0,
    gpu_usage=10.0,
    gpu_temp=45.0,
    fan_speed=2000.0,
    battery_level=80.0,
    battery_health=90.0,
    cycle_count=150,
    write_bytes_sec=1000000.0,
    memory_usage=45.0,
    wifi_rssi=-50.0,
    power_source="AC"
) -> TelemetrySnapshot:
    """Helper to create a telemetry snapshot populated with custom metrics."""
    snapshot = TelemetrySnapshot(
        id=str(uuid.uuid4()),
        device_id=device_id,
        timestamp=timestamp or datetime.utcnow(),
        health_score=85.0,
        health_category="Healthy"
    )
    snapshot.cpu = CPUMetrics(cpu_usage=cpu_usage, active_process_count=120, cpu_frequency_mhz=2900.0)
    snapshot.gpu = GPUMetrics(gpu_usage=gpu_usage, gpu_temperature=gpu_temp, gpu_memory_usage=5.0)
    snapshot.memory = MemoryMetrics(memory_usage=memory_usage, total_mb=16384.0, used_mb=7372.0)
    snapshot.battery = BatteryMetrics(
        battery_level=battery_level,
        battery_health=battery_health,
        battery_temperature=32.0,
        cycle_count=cycle_count
    )
    snapshot.disk = DiskMetrics(disk_usage=60.0, read_bytes_sec=1000, write_bytes_sec=write_bytes_sec)
    snapshot.wifi = WiFiMetrics(signal_strength_dbm=wifi_rssi, ssid="Test_WiFi", link_speed_mbps=150.0)
    snapshot.thermal = ThermalMetrics(
        cpu_temperature=cpu_temp,
        fan_speed_rpm=fan_speed,
        thermal_state="nominal"
    )
    snapshot.power = PowerMetrics(power_source=power_source, power_draw_watts=15.0, voltage_mv=11200.0)
    return snapshot

# ─── CORE ML SERVICES TESTS ──────────────────────────────────────────

def test_multi_factor_reasoning():
    engine = MultiFactorReasoning()
    
    # Test Workload Thermal Coupling
    res_coupling = engine.analyze({
        "cpu_usage": 85.0,
        "cpu_temperature": 85.0,
        "gpu_usage": 10.0,
        "power_source": "AC",
        "fan_rpm": 3000,
        "memory_usage": 50.0,
        "wifi_signal": -50.0
    })
    
    diagnoses = [d["condition"] for d in res_coupling["diagnoses"]]
    assert "Workload Thermal Coupling" in diagnoses
    assert res_coupling["system_stress_index"] > 60.0

    # Test Power Draw Stress
    res_power = engine.analyze({
        "cpu_usage": 80.0,
        "cpu_temperature": 55.0,
        "gpu_usage": 10.0,
        "power_source": "battery",
        "battery_level": 50.0,
        "fan_rpm": 2000,
        "memory_usage": 50.0,
        "wifi_signal": -50.0
    })
    diagnoses_power = [d["condition"] for d in res_power["diagnoses"]]
    assert "Power Draw Stress" in diagnoses_power


def test_recommendation_engine():
    engine = RecommendationEngine()
    
    # CPU usage elevated, AC power
    recs_ac = engine.generate_recommendations(
        metrics={"cpu_usage": 75.0, "cpu_temperature": 80.0, "power_source": "AC", "battery_level": 100.0, "fan_rpm": 2500.0},
        diagnoses=[{"condition": "Workload Thermal Coupling"}]
    )
    actions = [r["action"] for r in recs_ac]
    assert "Terminate High-CPU Background Processes" in actions
    assert "Increase Fan Speed Profile (Performance/Turbo)" in actions

    # Running on battery
    recs_bat = engine.generate_recommendations(
        metrics={"cpu_usage": 75.0, "cpu_temperature": 60.0, "power_source": "battery", "battery_level": 40.0, "fan_rpm": 2000.0},
        diagnoses=[]
    )
    actions_bat = [r["action"] for r in recs_bat]
    assert "Activate System Eco/Power-Saver Mode" in actions_bat
    assert "Reduce Display Brightness to 50%" in actions_bat


def test_health_classifier():
    engine = HealthClassifier()
    assert engine.is_trained

    # Nominal check
    res_nom = engine.classify({
        "cpu_usage": 15.0,
        "cpu_temperature": 45.0,
        "memory_usage": 30.0,
        "fan_rpm": 1200.0,
        "battery_level": 95.0,
        "power_source": "AC"
    })
    assert res_nom["predicted_tier"] == "Nominal"
    assert len(res_nom["splits"]) > 0

    # Critical check
    res_crit = engine.classify({
        "cpu_usage": 95.0,
        "cpu_temperature": 95.0,
        "memory_usage": 80.0,
        "fan_rpm": 5500.0,
        "battery_level": 5.0,
        "power_source": "battery"
    })
    assert res_crit["predicted_tier"] == "Critical Warning"


def test_trend_predictor():
    engine = TrendPredictor()
    assert engine.is_trained
    
    cpu_history = [50.0, 52.0, 55.0, 58.0, 60.0, 63.0, 65.0, 68.0, 72.0, 75.0]
    battery_history = [90.0, 89.0, 88.0, 87.0, 86.0, 85.0, 84.0, 83.0, 82.0, 81.0]
    
    res = engine.predict_trajectories(cpu_history, battery_history)
    assert len(res["cpu_temperature_forecast"]) == 10
    assert len(res["battery_level_forecast"]) == 10
    
    # Assert battery is decreasing and cpu temp is increasing (or at least predicted)
    assert res["battery_level_forecast"][0] <= 81.0
    assert res["cpu_temperature_forecast"][0] >= 70.0


def test_anomaly_detector():
    engine = AnomalyDetector()
    assert engine.is_trained
    
    # Test nominal metrics should NOT be flagged as anomaly
    res_norm = engine.detect({
        "cpu_usage": 20.0,
        "cpu_temperature": 50.0,
        "memory_usage": 40.0,
        "fan_rpm": 1500.0,
        "battery_level": 80.0
    })
    assert not res_norm["is_anomaly"]
    
    # Test extreme outlier metrics (high cpu, high temp, but fan_rpm 0)
    res_anom = engine.detect({
        "cpu_usage": 99.0,
        "cpu_temperature": 99.0,
        "memory_usage": 99.0,
        "fan_rpm": 0.0,
        "battery_level": 100.0
    })
    assert res_anom["is_anomaly"]
    assert res_anom["anomaly_rating"] > 50.0


def test_failure_predictor():
    engine = FailurePredictor()
    
    # Stable state, low cycle counts, low disk writes
    res = engine.predict_failure_horizon(
        current_state={
            "battery_health": 95.0,
            "battery_cycle_count": 100.0,
            "write_bytes_sec": 1000.0
        }
    )
    assert res["battery_rul_days"] > 365
    assert res["ssd_rul_days"] > 365
    assert len(res["battery_failure_probability_trajectory"]) == 5
    assert len(res["ssd_failure_probability_trajectory"]) == 5
    
    # High wear-out state
    res_wear = engine.predict_failure_horizon(
        current_state={
            "battery_health": 72.0,
            "battery_cycle_count": 950.0,
            "write_bytes_sec": 50000000.0 # ~50 MB/s continuous writing
        }
    )
    assert res_wear["battery_rul_days"] < 150
    assert res_wear["ssd_rul_days"] < 100


def test_confidence_scorer():
    scorer = ConfidenceScorer()
    
    # Classification confidence adjustments
    conf = scorer.calculate_classification_confidence(0.9, {"cpu_usage": 99.0, "cpu_temperature": 99.0})
    assert conf < 90.0
    
    # Forecast bounds check
    forecast_results = scorer.calculate_forecast_bounds([60.0, 62.0, 64.0], "cpu_temperature")
    bounds = forecast_results["forecast_bounds"]
    assert len(bounds) == 3
    assert bounds[0]["upper_bound"] > bounds[0]["value"]
    assert bounds[2]["upper_bound"] - bounds[2]["value"] > bounds[0]["upper_bound"] - bounds[0]["value"] # error increases
    
    # RUL confidence check
    assert scorer.calculate_rul_confidence(5) < scorer.calculate_rul_confidence(50)


# ─── INTEGRATION / ENDPOINT TESTS ─────────────────────────────────────

def test_api_ai_reasoning_state():
    db = TestingSessionLocal()
    device_id = "test-laptop-ai"
    
    # Insert multiple sequential snapshots to populate history
    now = datetime.utcnow()
    for i in range(15):
        t = now - timedelta(minutes=(15 - i))
        snapshot = create_test_snapshot(
            device_id=device_id,
            timestamp=t,
            cpu_usage=20.0 + (i * 2.0),
            cpu_temp=45.0 + (i * 1.5),
            battery_level=100.0 - (i * 1.0)
        )
        db.add(snapshot)
    
    db.commit()
    db.close()
    
    # Query api
    response = client.get(f"/api/v1/ai-reasoning/state/{device_id}")
    assert response.status_code == 200
    res_data = response.json()
    
    assert res_data["device_id"] == device_id
    assert res_data["system_stress_index"] > 0
    assert "anomaly" in res_data
    assert "forecast" in res_data
    assert "classification" in res_data
    assert "failure_prediction" in res_data
    
    # Verify forecast ticks count
    assert len(res_data["forecast"]["cpu_temperature"]) == 10
    assert len(res_data["forecast"]["battery_level"]) == 10
    assert len(res_data["failure_prediction"]["battery_failure_probability_trajectory"]) == 5


def test_api_ai_reasoning_not_found():
    response = client.get("/api/v1/ai-reasoning/state/non-existent-device")
    assert response.status_code == 404
