import numpy as np
from typing import Dict, Any, List

class FailurePredictor:
    """
    Phase 28: Failure Prediction Engine
    Estimates Remaining Useful Life (RUL) in days and calculates survival/failure probability
    trajectories using Weibull distribution hazard curves for Battery and SSD.
    """
    def __init__(self):
        # Constants
        self.BATTERY_CYCLE_LIMIT = 1000.0 # Standard design cycle life
        self.SSD_TBW_LIMIT = 300.0 # 300 Terabytes Written limit for SSD
        self.DEFAULT_CYCLES_PER_DAY = 0.35 # Default usage accumulation
        self.DEFAULT_SSD_GB_WRITTEN_PER_DAY = 15.0 # Default disk write rate

    def predict_failure_horizon(self, current_state: Dict[str, Any], history: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        # Extract active values
        battery_health = float(current_state.get("battery_health", 100.0))
        cycle_count = float(current_state.get("battery_cycle_count", 0.0))
        write_bytes_sec = float(current_state.get("write_bytes_sec", 0.0))
        
        # Estimate cumulative disk wear TB based on history or disk usage
        # If no history is available, we assume a baseline write count of 12.5 TB
        cumulative_tb_written = 12.5 
        
        # Estimate daily usage rates from history if available, otherwise fall back to defaults
        cycles_per_day = self.DEFAULT_CYCLES_PER_DAY
        ssd_gb_written_per_day = self.DEFAULT_SSD_GB_WRITTEN_PER_DAY
        if write_bytes_sec > 0:
            ssd_gb_written_per_day = max(ssd_gb_written_per_day, (write_bytes_sec * 86400.0) / (1024**3))

        if history and len(history) > 1:
            # Estimate battery cycle rate
            cycle_diffs = [history[i]["battery_cycle_count"] - history[i-1]["battery_cycle_count"] for i in range(1, len(history))]
            if sum(cycle_diffs) > 0:
                cycles_per_day = max(0.01, float(np.mean(cycle_diffs)))
                
            # Estimate SSD write speed and calculate daily throughput (bytes/sec to GB/day)
            write_speeds = [h.get("write_bytes_sec", 0.0) for h in history]
            mean_write_speed = float(np.mean(write_speeds)) if write_speeds else write_bytes_sec
            
            # If active writing is detected, compute daily rate: bytes/sec * 86400 seconds = bytes/day
            # Convert bytes/day to GB/day (divide by 10^9)
            if mean_write_speed > 0:
                ssd_gb_written_per_day = max(1.0, (mean_write_speed * 86400.0) / (1024**3))
                
            # Accumulate historical writes (assuming 10-second ticks)
            total_bytes_in_history = sum(h.get("write_bytes_sec", 0.0) * 10.0 for h in history)
            cumulative_tb_written += total_bytes_in_history / (1024**4)

        ssd_health = max(0.0, 100.0 * (1.0 - (cumulative_tb_written / self.SSD_TBW_LIMIT)))
        ssd_tb_written_per_day = ssd_gb_written_per_day / 1024.0 # TB per day

        # 1. Calculate Remaining Useful Life (RUL) in Days
        # Battery RUL: until health hits 70% or cycle limit is reached
        battery_health_rul_days = max(0.0, (battery_health - 70.0) / 0.02) # assuming 0.02% health decay per day
        battery_cycle_rul_days = max(0.0, (self.BATTERY_CYCLE_LIMIT - cycle_count) / cycles_per_day)
        battery_rul_days = int(min(battery_health_rul_days, battery_cycle_rul_days))
        battery_rul_days = max(1, battery_rul_days)

        # SSD RUL: until TBW limit is reached
        ssd_tb_remaining = max(0.0, self.SSD_TBW_LIMIT - cumulative_tb_written)
        ssd_rul_days = int(ssd_tb_remaining / ssd_tb_written_per_day)
        ssd_rul_days = max(1, ssd_rul_days)


        # 2. Weibull Survival / Failure Probability Curves
        # Weibull Cumulative Distribution Function for failure probability: F(t) = 1 - exp(-(t/lambda)^k)
        # where lambda = RUL (scale parameter), k = shape parameter (wear-out stage k=2.0)
        # We forecast over a 365-day scale (or monthly: 12 months)
        time_points_days = [30, 90, 180, 270, 365]
        
        def calculate_weibull_trajectory(rul_days: int) -> List[Dict[str, Any]]:
            trajectory = []
            shape_k = 2.0 # Progressively increasing failure rate over time
            scale_lambda = float(rul_days)
            
            for t in time_points_days:
                # Avoid division by zero
                if scale_lambda <= 0:
                    fail_prob = 1.0
                else:
                    fail_prob = 1.0 - np.exp(-((t / scale_lambda) ** shape_k))
                
                trajectory.append({
                    "day": t,
                    "failure_probability": round(float(fail_prob) * 100.0, 1),
                    "survival_probability": round((1.0 - float(fail_prob)) * 100.0, 1)
                })
            return trajectory

        battery_trajectory = calculate_weibull_trajectory(battery_rul_days)
        ssd_trajectory = calculate_weibull_trajectory(ssd_rul_days)

        return {
            "battery_rul_days": battery_rul_days,
            "battery_health_status": "Nominal" if battery_health > 85.0 else ("Warning" if battery_health > 75.0 else "Critical"),
            "battery_failure_probability_trajectory": battery_trajectory,
            
            "ssd_rul_days": ssd_rul_days,
            "ssd_health_status": "Nominal" if ssd_health > 85.0 else ("Warning" if ssd_health > 70.0 else "Critical"),
            "ssd_failure_probability_trajectory": ssd_trajectory
        }
