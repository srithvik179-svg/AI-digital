"""
Pydantic Schemas for Phase 41 What-If Simulation Engine.
"""
from pydantic import BaseModel, Field
from typing import Optional

class WhatIfSimulationRequest(BaseModel):
    cpu_usage: float = Field(..., ge=0.0, le=100.0, description="Hypothetical CPU load %", example=95.0)
    gpu_usage: float = Field(default=10.0, ge=0.0, le=100.0, description="Hypothetical GPU load %", example=30.0)
    memory_usage: float = Field(default=50.0, ge=0.0, le=100.0, description="Hypothetical RAM load %", example=65.0)
    battery_level: float = Field(default=80.0, ge=0.0, le=100.0, description="Hypothetical Battery charge %", example=80.0)
    battery_health: float = Field(default=90.0, ge=0.0, le=100.0, description="Hypothetical Battery condition %", example=92.0)
    power_source: str = Field(default="battery", description="AC vs Battery Power Source", example="battery")
    ambient_temperature: float = Field(default=25.0, description="Ambient room temperature in °C", example=25.0)

class TemperaturePrediction(BaseModel):
    cpu_temperature: float
    fan_speed_rpm: int
    thermal_state: str
    is_throttling: bool
    throttle_ratio: float

class PowerPrediction(BaseModel):
    total_power_draw_watts: float
    cpu_power_draw_watts: float
    gpu_power_draw_watts: float
    aux_power_draw_watts: float
    base_power_draw_watts: float
    charging_power_draw_watts: float

class BatteryPrediction(BaseModel):
    battery_status: str
    battery_drain_rate_percent_per_hour: float
    battery_charge_rate_percent_per_hour: float
    battery_remaining_minutes: float
    battery_temperature: float

class WhatIfSimulationResponse(BaseModel):
    temperature: TemperaturePrediction
    power: PowerPrediction
    battery: BatteryPrediction
