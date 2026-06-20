import numpy as np
from typing import Dict, Any, List

class ConfidenceScorer:
    """
    Phase 29: Confidence Scoring Engine
    Calculates statistical confidence percentages, margin-of-error bounds,
    and variance horizons for all model predictions and classifications.
    """
    def __init__(self):
        pass

    def calculate_classification_confidence(self, base_prob: float, input_metrics: Dict[str, Any]) -> float:
        """Adjusts classifier probability based on input value bounds (out-of-bound inputs lower confidence)."""
        cpu_usage = float(input_metrics.get("cpu_usage", 0.0))
        cpu_temp = float(input_metrics.get("cpu_temperature", 0.0))
        
        # Heuristic penalty for extremely out-of-normal-bound data points
        penalty = 0.0
        if cpu_usage > 98.0 or cpu_usage < 1.0:
            penalty += 5.0
        if cpu_temp > 98.0 or cpu_temp < 30.0:
            penalty += 10.0
            
        final_confidence = max(10.0, base_prob - penalty)
        return round(final_confidence, 1)

    def calculate_forecast_bounds(self, predictions: List[float], metric_name: str) -> Dict[str, Any]:
        """
        Calculates error bounds (upper/lower margin) and confidence intervals.
        Error increases over the forecast horizon.
        """
        bounds = []
        confidences = []
        
        # Base standard deviation (typical variance in stable states)
        if metric_name == "cpu_temperature":
            base_std = 2.5
            z_score = 1.96 # 95% confidence interval
        else: # battery_level
            base_std = 0.8
            z_score = 1.96
            
        for i, val in enumerate(predictions):
            step = i + 1
            # Standard error increases with root of step count in autoregressive walk
            std_err = base_std * np.sqrt(step)
            margin = z_score * std_err
            
            upper_bound = val + margin
            lower_bound = val - margin
            
            # Clamp limits to physical ranges
            if metric_name == "cpu_temperature":
                upper_bound = min(110.0, upper_bound)
                lower_bound = max(25.0, lower_bound)
            elif metric_name == "battery_level":
                upper_bound = min(100.0, upper_bound)
                lower_bound = max(0.0, lower_bound)
                
            # Confidence decays as horizon deepens
            step_confidence = max(45.0, 96.0 - (step * 3.5))
            
            bounds.append({
                "tick": step,
                "value": val,
                "upper_bound": round(float(upper_bound), 1),
                "lower_bound": round(float(lower_bound), 1),
                "margin_of_error": round(float(margin), 2)
            })
            confidences.append(round(step_confidence, 1))

        return {
            "forecast_bounds": bounds,
            "mean_confidence": round(float(np.mean(confidences)), 1)
        }

    def calculate_rul_confidence(self, history_len: int) -> float:
        """Confidence in remaining useful life scales with available historical baseline points."""
        # Minimum baseline confidence is 55.0%
        # Increases with historical snapshots to a maximum of 95.0%
        base = 55.0
        increment = min(40.0, history_len * 1.5)
        return round(base + increment, 1)
