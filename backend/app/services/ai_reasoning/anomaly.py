import numpy as np
from sklearn.ensemble import IsolationForest
from typing import Dict, Any, List

class AnomalyDetector:
    """
    Phase 27: Isolation Forest Anomaly Detection Engine
    Detects multi-dimensional out-of-distribution telemetry anomalies.
    Exposes an anomaly score and a binary outlier flag.
    """
    def __init__(self):
        # contamination represents the expected proportion of outliers in the data
        self.model = IsolationForest(contamination=0.05, random_state=42)
        self.feature_names = ["cpu_usage", "cpu_temperature", "memory_usage", "fan_rpm", "battery_level"]
        self.is_trained = False
        self._bootstrap_and_train()

    def _bootstrap_and_train(self):
        """Generates synthetic multi-dimensional normal dataset and trains the IsolationForest."""
        np.random.seed(123)
        n_samples = 600
        
        # Normal operations: CPU (10-45%), Temp (40-65C), RAM (30-60%), Fan (1000-2500 RPM), Battery (20-100%)
        cpu_usage = np.random.uniform(10.0, 45.0, n_samples)
        cpu_temp = np.random.uniform(40.0, 65.0, n_samples)
        memory_usage = np.random.uniform(30.0, 60.0, n_samples)
        fan_rpm = np.random.uniform(1000.0, 2500.0, n_samples)
        battery_level = np.random.uniform(20.0, 100.0, n_samples)
        
        X = np.column_stack([cpu_usage, cpu_temp, memory_usage, fan_rpm, battery_level])
        
        # Fit model on clean distribution
        self.model.fit(X)
        self.is_trained = True

    def detect(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Runs anomaly detection for a single telemetry snapshot."""
        if not self.is_trained:
            self._bootstrap_and_train()

        cpu_usage = float(metrics.get("cpu_usage", 0.0))
        cpu_temp = float(metrics.get("cpu_temperature", 0.0))
        memory_usage = float(metrics.get("memory_usage", 0.0))
        fan_rpm = float(metrics.get("fan_rpm", 0.0))
        battery_level = float(metrics.get("battery_level", 100.0))

        features = np.array([[cpu_usage, cpu_temp, memory_usage, fan_rpm, battery_level]])
        
        # Predict: 1 = normal, -1 = anomaly
        pred = int(self.model.predict(features)[0])
        is_anomaly = (pred == -1)
        
        # decision_function: negative is anomaly, positive is normal
        decision_score = float(self.model.decision_function(features)[0])
        
        # Normalization: Map to a user-friendly anomaly rating (0-100%)
        # Lower decision_score means more anomalous.
        # Typically, decision_score ranges from -0.5 to 0.5.
        # We want high anomaly rating (e.g. > 70%) for anomalous states
        anomaly_rating = 0.0
        if is_anomaly:
            # Scale from decision_score [-0.5, 0.0] -> [50.0, 100.0]
            anomaly_rating = 50.0 + min(50.0, abs(decision_score) * 100.0)
        else:
            # Scale from decision_score [0.0, 0.5] -> [0.0, 50.0]
            anomaly_rating = max(0.0, 50.0 - (decision_score * 100.0))
            
        return {
            "is_anomaly": is_anomaly,
            "anomaly_score": round(decision_score, 4),
            "anomaly_rating": round(anomaly_rating, 1)
        }
