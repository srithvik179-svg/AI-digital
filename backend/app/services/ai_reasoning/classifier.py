import numpy as np
from sklearn.tree import DecisionTreeClassifier
from typing import Dict, Any, List, Tuple

class HealthClassifier:
    """
    Phase 25: Health Classification Model
    Trains and executes a DecisionTreeClassifier to categorize laptop state
    into Fine-Grained Health Tiers: Nominal, High Load, Thermal Throttling, Critical Warning.
    Exposes the decision split path taken for explanation generation.
    """
    def __init__(self):
        self.model = DecisionTreeClassifier(max_depth=3, random_state=42)
        self.feature_names = ["cpu_usage", "cpu_temperature", "memory_usage", "fan_rpm", "battery_level", "on_battery"]
        self.target_names = ["Nominal", "High Load", "Thermal Throttling", "Critical Warning"]
        self.is_trained = False
        self._bootstrap_and_train()

    def _bootstrap_and_train(self):
        """Generates synthetic training data to boot up the decision tree classifier."""
        # Generate 1000 synthetic samples
        np.random.seed(42)
        n_samples = 1200
        
        # Features: cpu_usage (0-100), cpu_temp (35-98), memory_usage (10-100), fan_rpm (0-6000), battery_level (0-100), on_battery (0 or 1)
        cpu_usage = np.random.uniform(5, 100, n_samples)
        cpu_temp = np.random.uniform(35, 98, n_samples)
        memory_usage = np.random.uniform(15, 95, n_samples)
        fan_rpm = np.random.uniform(0, 5800, n_samples)
        battery_level = np.random.uniform(2, 100, n_samples)
        on_battery = np.random.choice([0, 1], size=n_samples, p=[0.6, 0.4])
        
        X = np.column_stack([cpu_usage, cpu_temp, memory_usage, fan_rpm, battery_level, on_battery])
        y = np.zeros(n_samples, dtype=int)
        
        for i in range(n_samples):
            # Class rules:
            # Class 3: Critical Warning
            if X[i, 1] >= 90.0 or (X[i, 4] < 8.0 and X[i, 5] == 1):
                y[i] = 3
            # Class 2: Thermal Throttling
            elif X[i, 0] >= 75.0 and X[i, 1] >= 79.0:
                y[i] = 2
            # Class 1: High Load
            elif X[i, 0] >= 55.0 or X[i, 2] >= 75.0:
                y[i] = 1
            # Class 0: Nominal
            else:
                y[i] = 0

        self.model.fit(X, y)
        self.is_trained = True

    def classify(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Classifies the health tier and returns the tree decision path splits."""
        if not self.is_trained:
            self._bootstrap_and_train()
            
        cpu_usage = float(metrics.get("cpu_usage", 0.0))
        cpu_temp = float(metrics.get("cpu_temperature", 0.0))
        memory_usage = float(metrics.get("memory_usage", 0.0))
        fan_rpm = float(metrics.get("fan_rpm", 0.0))
        battery_level = float(metrics.get("battery_level", 100.0))
        
        power_source = str(metrics.get("power_source", "AC")).lower()
        on_battery = 1.0 if power_source == "battery" else 0.0
        
        features = np.array([[cpu_usage, cpu_temp, memory_usage, fan_rpm, battery_level, on_battery]])
        
        # Predict class
        class_idx = int(self.model.predict(features)[0])
        probabilities = self.model.predict_proba(features)[0]
        confidence = float(probabilities[class_idx])
        predicted_tier = self.target_names[class_idx]
        
        # Walk decision path
        decision_path = self.model.decision_path(features)
        node_indices = decision_path.indices
        
        # Generate decision split explanation based on path
        tree = self.model.tree_
        splits = []
        for node_id in node_indices:
            # If it's a leaf node, skip
            if tree.children_left[node_id] == -1 and tree.children_right[node_id] == -1:
                continue
                
            feature_idx = tree.feature[node_id]
            threshold = float(tree.threshold[node_id])
            feature_name = self.feature_names[feature_idx]
            val = float(features[0, feature_idx])
            
            # Did we go left (<= threshold) or right (> threshold)?
            left_child = tree.children_left[node_id]
            # Find which child node is in our path
            went_left = left_child in node_indices
            
            comparison = "<=" if went_left else ">"
            splits.append({
                "feature": feature_name,
                "value": round(val, 2),
                "threshold": round(threshold, 2),
                "comparison": comparison,
                "split_rule": f"{feature_name} ({val:.1f}) {comparison} {threshold:.1f}"
            })
            
        return {
            "predicted_tier": predicted_tier,
            "confidence": round(confidence * 100.0, 1),
            "splits": splits
        }
