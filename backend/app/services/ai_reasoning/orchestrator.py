from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from datetime import datetime

from app.models.telemetry import TelemetrySnapshot
from app.services.ai_reasoning.multi_factor import MultiFactorReasoning
from app.services.ai_reasoning.recommender import RecommendationEngine
from app.services.ai_reasoning.classifier import HealthClassifier
from app.services.ai_reasoning.predictor import TrendPredictor
from app.services.ai_reasoning.anomaly import AnomalyDetector
from app.services.ai_reasoning.failure_prediction import FailurePredictor
from app.services.ai_reasoning.confidence import ConfidenceScorer

class AIReasoningOrchestrator:
    """
    Phase 30: AI Reasoning Orchestrator
    Consolidates and orchestrates all AI/ML reasoning services (Multi-Factor,
    Recommendation, Classification, Forecasting, Anomaly, Failure prediction)
    into a unified pipeline and formats the response for frontend consumption.
    """
    def __init__(self):
        # Instantiate services (which will train/load models on demand)
        self.multi_factor = MultiFactorReasoning()
        self.recommender = RecommendationEngine()
        self.classifier = HealthClassifier()
        self.predictor = TrendPredictor()
        self.anomaly = AnomalyDetector()
        self.failure = FailurePredictor()
        self.confidence = ConfidenceScorer()

    def get_unified_reasoning_state(self, device_id: str, db: Session) -> Dict[str, Any]:
        # Fetch the latest snapshot for active state
        latest_snapshot = (
            db.query(TelemetrySnapshot)
            .filter(TelemetrySnapshot.device_id == device_id)
            .order_by(TelemetrySnapshot.timestamp.desc())
            .first()
        )

        if not latest_snapshot:
            raise ValueError(f"No telemetry snapshots found for device '{device_id}'")

        # Fetch historical snapshots (up to 60) for time-series models
        history_snapshots = (
            db.query(TelemetrySnapshot)
            .filter(TelemetrySnapshot.device_id == device_id)
            .order_by(TelemetrySnapshot.timestamp.desc())
            .limit(60)
            .all()
        )
        # Reverse to chronological order (oldest first)
        history_snapshots = history_snapshots[::-1]

        # Extract latest metrics dictionary
        latest_metrics = {
            "cpu_usage": latest_snapshot.cpu.cpu_usage if latest_snapshot.cpu else 0.0,
            "cpu_temperature": latest_snapshot.thermal.cpu_temperature if latest_snapshot.thermal else 45.0,
            "gpu_usage": latest_snapshot.gpu.gpu_usage if latest_snapshot.gpu else 0.0,
            "gpu_temperature": latest_snapshot.gpu.gpu_temperature if latest_snapshot.gpu else 40.0,
            "battery_level": latest_snapshot.battery.battery_level if latest_snapshot.battery else 100.0,
            "battery_health": latest_snapshot.battery.battery_health if latest_snapshot.battery else 100.0,
            "battery_cycle_count": latest_snapshot.battery.cycle_count if latest_snapshot.battery else 0.0,
            "write_bytes_sec": latest_snapshot.disk.write_bytes_sec if latest_snapshot.disk else 0.0,
            "power_source": latest_snapshot.power.power_source if latest_snapshot.power else "AC",
            "fan_rpm": latest_snapshot.thermal.fan_speed_rpm if latest_snapshot.thermal else 0.0,
            "memory_usage": latest_snapshot.memory.memory_usage if latest_snapshot.memory else 0.0,
            "wifi_signal": latest_snapshot.wifi.signal_strength_dbm if latest_snapshot.wifi else -50.0
        }

        # 1. Multi-Factor Reasoning
        mf_out = self.multi_factor.analyze(latest_metrics)
        system_stress_index = mf_out["system_stress_index"]
        diagnoses = mf_out["diagnoses"]

        # 2. Recommendation Engine
        recommendations = self.recommender.generate_recommendations(latest_metrics, diagnoses)

        # 3. Health Classification Model
        class_out = self.classifier.classify(latest_metrics)
        # Score confidence through confidence scorer
        class_confidence = self.confidence.calculate_classification_confidence(
            class_out["confidence"] / 100.0, latest_metrics
        ) * 100.0
        classification = {
            "predicted_tier": class_out["predicted_tier"],
            "confidence": round(class_confidence, 1),
            "decision_path": class_out["splits"]
        }

        # 4. XGBoost Prediction & Confidence Bounds
        cpu_history = [s.thermal.cpu_temperature for s in history_snapshots if s.thermal]
        bat_history = [s.battery.battery_level for s in history_snapshots if s.battery]
        
        forecast_out = self.predictor.predict_trajectories(cpu_history, bat_history)
        
        cpu_bounds = self.confidence.calculate_forecast_bounds(
            forecast_out["cpu_temperature_forecast"], "cpu_temperature"
        )
        bat_bounds = self.confidence.calculate_forecast_bounds(
            forecast_out["battery_level_forecast"], "battery_level"
        )

        forecast = {
            "cpu_temperature": cpu_bounds["forecast_bounds"],
            "cpu_forecast_confidence": cpu_bounds["mean_confidence"],
            "battery_level": bat_bounds["forecast_bounds"],
            "battery_forecast_confidence": bat_bounds["mean_confidence"]
        }

        # 5. Isolation Forest Anomaly Detection
        anomaly_out = self.anomaly.detect(latest_metrics)
        anomaly = {
            "is_anomaly": anomaly_out["is_anomaly"],
            "anomaly_score": anomaly_out["anomaly_score"],
            "anomaly_rating": anomaly_out["anomaly_rating"]
        }

        # 6. Failure Prediction (RUL & Weibull)
        history_data = []
        for s in history_snapshots:
            history_data.append({
                "battery_cycle_count": s.battery.cycle_count if s.battery else 0.0,
                "write_bytes_sec": s.disk.write_bytes_sec if s.disk else 0.0
            })
            
        fail_out = self.failure.predict_failure_horizon(latest_metrics, history_data)
        
        history_len = len(history_snapshots)
        battery_rul_confidence = self.confidence.calculate_rul_confidence(history_len)
        ssd_rul_confidence = self.confidence.calculate_rul_confidence(history_len)
        
        failure_prediction = {
            "battery_rul_days": fail_out["battery_rul_days"],
            "battery_rul_confidence": battery_rul_confidence,
            "battery_health_status": fail_out["battery_health_status"],
            "battery_failure_probability_trajectory": fail_out["battery_failure_probability_trajectory"],
            
            "ssd_rul_days": fail_out["ssd_rul_days"],
            "ssd_rul_confidence": ssd_rul_confidence,
            "ssd_health_status": fail_out["ssd_health_status"],
            "ssd_failure_probability_trajectory": fail_out["ssd_failure_probability_trajectory"]
        }

        # Combine all metrics and predictions into a unified output
        return {
            "device_id": device_id,
            "timestamp": latest_snapshot.timestamp.isoformat(),
            "active_metrics": latest_metrics,
            "system_stress_index": system_stress_index,
            "diagnoses": diagnoses,
            "recommendations": recommendations,
            "classification": classification,
            "forecast": forecast,
            "anomaly": anomaly,
            "failure_prediction": failure_prediction
        }
