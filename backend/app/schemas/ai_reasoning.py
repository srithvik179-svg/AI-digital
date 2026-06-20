from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime

class ActiveMetrics(BaseModel):
    cpu_usage: float
    cpu_temperature: float
    gpu_usage: float
    gpu_temperature: float
    battery_level: float
    battery_health: float
    battery_cycle_count: float
    write_bytes_sec: float
    power_source: str
    fan_rpm: float
    memory_usage: float
    wifi_signal: float

class Diagnosis(BaseModel):
    condition: str
    severity: str
    evidence: str
    confidence: float

class Recommendation(BaseModel):
    action: str
    trigger: str
    estimated_cooling_c: float
    estimated_battery_extension_mins: int
    description: str
    priority: str

class DecisionSplit(BaseModel):
    feature: str
    value: float
    threshold: float
    comparison: str
    split_rule: str

class Classification(BaseModel):
    predicted_tier: str
    confidence: float
    decision_path: List[DecisionSplit]

class ForecastTick(BaseModel):
    tick: int
    value: float
    upper_bound: float
    lower_bound: float
    margin_of_error: float

class Forecast(BaseModel):
    cpu_temperature: List[ForecastTick]
    cpu_forecast_confidence: float
    battery_level: List[ForecastTick]
    battery_forecast_confidence: float

class AnomalyState(BaseModel):
    is_anomaly: bool
    anomaly_score: float
    anomaly_rating: float

class FailureTimepoint(BaseModel):
    day: int
    failure_probability: float
    survival_probability: float

class FailurePrediction(BaseModel):
    battery_rul_days: int
    battery_rul_confidence: float
    battery_health_status: str
    battery_failure_probability_trajectory: List[FailureTimepoint]
    ssd_rul_days: int
    ssd_rul_confidence: float
    ssd_health_status: str
    ssd_failure_probability_trajectory: List[FailureTimepoint]

class AIReasoningStateResponse(BaseModel):
    device_id: str
    timestamp: datetime
    active_metrics: ActiveMetrics
    system_stress_index: float
    diagnoses: List[Diagnosis]
    recommendations: List[Recommendation]
    classification: Classification
    forecast: Forecast
    anomaly: AnomalyState
    failure_prediction: FailurePrediction

    class Config:
        json_schema_extra = {
            "example": {
                "device_id": "laptop-mac-001",
                "timestamp": "2026-06-20T20:00:00Z",
                "system_stress_index": 35.4,
                "anomaly": {
                    "is_anomaly": False,
                    "anomaly_score": 0.1245,
                    "anomaly_rating": 24.5
                }
            }
        }
