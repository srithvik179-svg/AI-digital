"""
Explainable AI Service — Phase 38.
Computes feature attributions explaining:
1. Static Health Score Engine penalties.
2. Decision Tree health classification splits.
3. XGBoost CPU temperature regressor lags.
"""
from typing import Dict, Any, List, Optional
from app.services.health_score import compute_health_score
from app.services.ai_reasoning.classifier import HealthClassifier
from app.services.ai_reasoning.predictor import TrendPredictor
from app.models.telemetry import TelemetrySnapshot

# Shared instances to avoid training models repeatedly
_classifier_instance = None
_predictor_instance = None

def get_classifier() -> HealthClassifier:
    global _classifier_instance
    if _classifier_instance is None:
        _classifier_instance = HealthClassifier()
    return _classifier_instance

def get_predictor() -> TrendPredictor:
    global _predictor_instance
    if _predictor_instance is None:
        _predictor_instance = TrendPredictor()
    return _predictor_instance

def explain_health_score(metrics: Dict[str, Any]) -> Dict[str, float]:
    """
    Computes penalty-based feature attributions for the 7-component Health Score Engine.
    For each component, the penalty is (100.0 - sub_score) * weight.
    Returns normalized attributions (summing to 100.0%).
    """
    cpu_usage = float(metrics.get("cpu_usage", 0.0))
    memory_usage = float(metrics.get("memory_usage", 0.0))
    disk_usage = float(metrics.get("disk_usage", 0.0))
    cpu_temperature = float(metrics.get("cpu_temperature", 0.0))
    battery_level = float(metrics.get("battery_level", 100.0))
    battery_health = float(metrics.get("battery_health", 100.0))
    gpu_usage = metrics.get("gpu_usage")
    signal_strength_dbm = metrics.get("signal_strength_dbm")
    power_source = metrics.get("power_source", "ac")
    thermal_state = metrics.get("thermal_state")

    # Compute health score breakdown
    score_obj = compute_health_score(
        cpu_usage=cpu_usage,
        memory_usage=memory_usage,
        disk_usage=disk_usage,
        cpu_temperature=cpu_temperature,
        battery_level=battery_level,
        battery_health=battery_health,
        gpu_usage=gpu_usage,
        signal_strength_dbm=signal_strength_dbm,
        power_source=power_source,
        thermal_state=thermal_state
    )

    weights = {
        "cpu":         0.22,
        "memory":      0.13,
        "gpu":         0.08,
        "temperature": 0.22,
        "battery":     0.15,
        "disk":        0.10,
        "wifi":        0.10,
    }

    penalties = {}
    total_penalty = 0.0

    for key, sub_score in score_obj.breakdown.items():
        weight = weights.get(key, 0.0)
        penalty = (100.0 - sub_score) * weight
        penalties[key] = penalty
        total_penalty += penalty

    attributions = {}
    if total_penalty > 0.0:
        for key, penalty in penalties.items():
            attributions[key] = round((penalty / total_penalty) * 100.0, 2)
    else:
        # Default to base weights if there are no penalties (perfect health score 100)
        for key, weight in weights.items():
            attributions[key] = round(weight * 100.0, 2)

    return attributions

def explain_health_classification(metrics: Dict[str, Any]) -> Dict[str, float]:
    """
    Computes local feature attributions for the Decision Tree classification model.
    Highlights features that were split on along the decision path, weighted by model importances.
    """
    classifier = get_classifier()
    classification_res = classifier.classify(metrics)
    splits = classification_res.get("splits", [])
    
    active_features = {s["feature"] for s in splits}
    global_importances = classifier.model.feature_importances_
    
    attributions = {}
    total_importance = 0.0
    
    for idx, name in enumerate(classifier.feature_names):
        if name in active_features:
            attributions[name] = float(global_importances[idx])
            total_importance += global_importances[idx]
        else:
            attributions[name] = 0.0
            
    if total_importance > 0.0:
        for name in attributions:
            attributions[name] = round((attributions[name] / total_importance) * 100.0, 2)
    else:
        # Fallback: if no active split features have global importance, use global importances directly
        sum_global = sum(global_importances)
        if sum_global > 0.0:
            for idx, name in enumerate(classifier.feature_names):
                attributions[name] = round((global_importances[idx] / sum_global) * 100.0, 2)
        else:
            # Fallback to equal weighting
            for name in classifier.feature_names:
                attributions[name] = round(100.0 / len(classifier.feature_names), 2)
                
    return attributions

def explain_temperature_forecast() -> Dict[str, float]:
    """
    Computes lag feature attributions for the XGBoost CPU temperature forecast model.
    """
    predictor = get_predictor()
    importances = predictor.cpu_model.feature_importances_
    total = sum(importances)
    
    attributions = {}
    for i in range(10):
        weight = (importances[i] / total) * 100.0 if total > 0 else 10.0
        # lag_1 is the most recent tick, lag_10 is the oldest tick
        attributions[f"lag_{i+1}"] = round(weight, 2)
        
    return attributions

def explain_prediction(device_id: str, db_session) -> Dict[str, Any]:
    """
    Orchestrates explainability for the latest system state and predictions.
    Queries the database to compile active telemetry metrics and history.
    """
    # Fetch latest snapshot to explain Health Score and classification
    latest_snap = db_session.query(TelemetrySnapshot).filter(
        TelemetrySnapshot.device_id == device_id
    ).order_by(TelemetrySnapshot.timestamp.desc()).first()

    if latest_snap:
        # Extract metrics dictionary
        metrics = {
            "cpu_usage": latest_snap.cpu.cpu_usage if latest_snap.cpu else 0.0,
            "cpu_temperature": latest_snap.thermal.cpu_temperature if latest_snap.thermal else 0.0,
            "memory_usage": latest_snap.memory.memory_usage if latest_snap.memory else 0.0,
            "fan_rpm": latest_snap.thermal.fan_speed_rpm if latest_snap.thermal else 0,
            "battery_level": latest_snap.battery.battery_level if latest_snap.battery else 100.0,
            "battery_health": latest_snap.battery.battery_health if latest_snap.battery else 100.0,
            "gpu_usage": latest_snap.gpu.gpu_usage if latest_snap.gpu else 0.0,
            "gpu_temperature": latest_snap.gpu.gpu_temperature if latest_snap.gpu else 0.0,
            "disk_usage": latest_snap.disk.disk_usage if latest_snap.disk else 0.0,
            "power_source": latest_snap.power.power_source if latest_snap.power else "ac",
            "thermal_state": latest_snap.thermal.thermal_state if latest_snap.thermal else "nominal",
            "signal_strength_dbm": latest_snap.wifi.signal_strength_dbm if latest_snap.wifi else -50
        }
    else:
        # Default mock metrics
        metrics = {
            "cpu_usage": 45.0,
            "cpu_temperature": 68.0,
            "memory_usage": 60.0,
            "fan_rpm": 2500,
            "battery_level": 80.0,
            "battery_health": 95.0,
            "gpu_usage": 15.0,
            "gpu_temperature": 52.0,
            "disk_usage": 40.0,
            "power_source": "ac",
            "thermal_state": "nominal",
            "signal_strength_dbm": -55
        }

    # Execute attributions
    health_score_attributions = explain_health_score(metrics)
    classification_attributions = explain_health_classification(metrics)
    forecast_attributions = explain_temperature_forecast()

    return {
        "health_score_attributions": health_score_attributions,
        "classification_attributions": classification_attributions,
        "forecast_attributions": forecast_attributions,
        "predicted_tier": get_classifier().classify(metrics)["predicted_tier"],
        "health_score": compute_health_score(
            cpu_usage=metrics["cpu_usage"],
            memory_usage=metrics["memory_usage"],
            disk_usage=metrics["disk_usage"],
            cpu_temperature=metrics["cpu_temperature"],
            battery_level=metrics["battery_level"],
            battery_health=metrics["battery_health"],
            gpu_usage=metrics["gpu_usage"],
            signal_strength_dbm=metrics["signal_strength_dbm"],
            power_source=metrics["power_source"],
            thermal_state=metrics["thermal_state"]
        ).score
    }
