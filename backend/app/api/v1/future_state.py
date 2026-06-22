"""
Phase 45 — Future-State Prediction API Router.

Exposes a single POST endpoint that triggers all three ML forecasters
(XGBoost Thermal, LSTM Battery, Prophet Network) and returns a unified
multi-domain prediction payload.
"""

from fastapi import APIRouter
from app.schemas.future_state import (
    FutureStatePredictionRequest,
    FutureStatePredictionResponse,
)
from app.services.ai_reasoning.future_state import run_future_state_prediction

router = APIRouter()


@router.post(
    "/predict",
    response_model=FutureStatePredictionResponse,
    summary="Run multi-domain future-state prediction",
    description=(
        "Accepts recent telemetry history for CPU/GPU temps, battery SoC, "
        "and WiFi signal, then runs the XGBoost Thermal, LSTM Battery, and "
        "Prophet Network forecasters to produce a unified 30-tick lookahead."
    ),
)
def predict_future_state(body: FutureStatePredictionRequest) -> FutureStatePredictionResponse:
    result = run_future_state_prediction(
        cpu_temp_history=body.cpu_temp_history,
        gpu_temp_history=body.gpu_temp_history,
        cpu_usage_history=body.cpu_usage_history,
        gpu_usage_history=body.gpu_usage_history,
        fan_rpm_history=body.fan_rpm_history,
        ambient_temp=body.ambient_temp,
        battery_soc_history=body.battery_soc_history,
        cpu_watts_history=body.cpu_watts_history,
        gpu_watts_history=body.gpu_watts_history,
        is_charging=body.is_charging,
        wifi_rssi_history=body.wifi_rssi_history,
        packet_loss_history=body.packet_loss_history,
        horizon=body.horizon,
    )
    return FutureStatePredictionResponse(**result)
