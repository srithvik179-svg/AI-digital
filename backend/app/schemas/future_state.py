"""
Pydantic schemas for Phase 42-45 Future-State Prediction API.
"""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------

class FutureStatePredictionRequest(BaseModel):
    """
    Full request body for /future-state/predict.
    Each history list is optional — defaults will be used if omitted.
    """

    # --- Thermal inputs ---
    cpu_temp_history:  List[float] = Field(default_factory=list, description="Recent CPU temps (°C)")
    gpu_temp_history:  List[float] = Field(default_factory=list, description="Recent GPU temps (°C)")
    cpu_usage_history: List[float] = Field(default_factory=list, description="Recent CPU utilisation (%)")
    gpu_usage_history: List[float] = Field(default_factory=list, description="Recent GPU utilisation (%)")
    fan_rpm_history:   List[float] = Field(default_factory=list, description="Recent fan RPM readings")
    ambient_temp:      float       = Field(default=25.0, ge=0.0, le=60.0, description="Ambient temperature (°C)")

    # --- Battery inputs ---
    battery_soc_history: List[float] = Field(default_factory=list, description="Recent battery SoC (%)")
    cpu_watts_history:   List[float] = Field(default_factory=list, description="Recent CPU power draw (W)")
    gpu_watts_history:   List[float] = Field(default_factory=list, description="Recent GPU power draw (W)")
    is_charging:         bool        = Field(default=False, description="True when AC adapter is connected")

    # --- Network inputs ---
    wifi_rssi_history:    List[float]          = Field(default_factory=list, description="Recent WiFi RSSI (dBm)")
    packet_loss_history:  Optional[List[float]] = Field(default=None, description="Recent packet-loss (%)")

    # --- Forecast config ---
    horizon: int = Field(default=30, ge=1, le=120, description="Number of 5-second ticks to forecast")


# ---------------------------------------------------------------------------
# Sub-responses
# ---------------------------------------------------------------------------

class ThermalForecastResult(BaseModel):
    cpu_temperature_forecast: List[float]
    gpu_temperature_forecast: List[float]
    tick_seconds:  int
    horizon_ticks: int
    model: str


class BatteryForecastResult(BaseModel):
    battery_soc_forecast:  List[float]
    battery_temp_forecast: List[float]
    tick_seconds:  int
    horizon_ticks: int
    model: str


class NetworkForecastResult(BaseModel):
    wifi_rssi_forecast:    List[float]
    packet_loss_forecast:  List[float]
    wifi_quality_forecast: List[str]
    tick_seconds:  int
    horizon_ticks: int
    model: str


# ---------------------------------------------------------------------------
# Unified response
# ---------------------------------------------------------------------------

class FutureStatePredictionResponse(BaseModel):
    thermal:         ThermalForecastResult
    battery:         BatteryForecastResult
    network:         NetworkForecastResult
    horizon_ticks:   int
    tick_seconds:    int
    horizon_minutes: float
