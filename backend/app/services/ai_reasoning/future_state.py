"""
Phase 45 — Unified Future-State Prediction Engine.

Orchestrates the three specialized predictors (Phase 42–44) under a single
interface that accepts a raw telemetry snapshot and returns a merged
multi-domain forecast object.
"""

from __future__ import annotations

from typing import List, Dict, Any, Optional

from app.services.ai_reasoning.thermal_predictor import thermal_predictor
from app.services.ai_reasoning.battery_predictor import battery_predictor
from app.services.ai_reasoning.network_predictor import network_predictor


def run_future_state_prediction(
    # Thermal inputs
    cpu_temp_history:  List[float],
    gpu_temp_history:  List[float],
    cpu_usage_history: List[float],
    gpu_usage_history: List[float],
    fan_rpm_history:   List[float],
    ambient_temp:      float = 25.0,
    # Battery inputs
    battery_soc_history:  List[float] = None,
    cpu_watts_history:    List[float] = None,
    gpu_watts_history:    List[float] = None,
    is_charging:          bool = False,
    # Network inputs
    wifi_rssi_history:         List[float] = None,
    packet_loss_history:       Optional[List[float]] = None,
    # Forecast config
    horizon: int = 30,
) -> Dict[str, Any]:
    """
    Runs all three forecasters and returns a unified future-state payload.

    Parameters
    ----------
    (see individual predictor docstrings for field descriptions)
    horizon : number of ticks (default 30 × 5s = 2.5 min lookahead)

    Returns
    -------
    {
      "thermal":  { ...XGBoost thermal forecast... },
      "battery":  { ...LSTM battery forecast... },
      "network":  { ...Prophet network forecast... },
      "horizon_ticks": int,
      "tick_seconds":  int,
      "horizon_minutes": float,
    }
    """
    thermal = thermal_predictor.forecast(
        cpu_temp_history=cpu_temp_history  or [55.0] * 10,
        gpu_temp_history=gpu_temp_history  or [50.0] * 10,
        cpu_usage_history=cpu_usage_history or [30.0] * 10,
        gpu_usage_history=gpu_usage_history or [20.0] * 10,
        fan_rpm_history=fan_rpm_history    or [1800.0] * 10,
        ambient_temp=ambient_temp,
        horizon=horizon,
    )

    battery = battery_predictor.forecast(
        battery_history=battery_soc_history   or [80.0] * 10,
        cpu_watts_history=cpu_watts_history   or [8.0] * 10,
        gpu_watts_history=gpu_watts_history   or [3.0] * 10,
        is_charging=is_charging,
        horizon=horizon,
    )

    network = network_predictor.forecast(
        rssi_history=wifi_rssi_history       or [-65.0] * 10,
        packet_loss_history=packet_loss_history,
        horizon=horizon,
    )

    tick_sec = thermal.get("tick_seconds", 5)
    horizon_minutes = round(horizon * tick_sec / 60.0, 1)

    return {
        "thermal":        thermal,
        "battery":        battery,
        "network":        network,
        "horizon_ticks":  horizon,
        "tick_seconds":   tick_sec,
        "horizon_minutes": horizon_minutes,
    }
