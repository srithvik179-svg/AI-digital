"""
What-If Simulation API Router — Phase 41.
Exposes instant steady-state simulations of CPU, GPU, Battery, and Disk.
"""
from fastapi import APIRouter, HTTPException
from app.schemas.what_if import WhatIfSimulationRequest, WhatIfSimulationResponse
from app.services.ai_reasoning.what_if_simulator import simulate_what_if
from app.core.logging import logger

router = APIRouter()

@router.post("/simulate", response_model=WhatIfSimulationResponse)
def simulate_hypothetical_scenario(payload: WhatIfSimulationRequest):
    """
    Instantly runs the steady-state physics, power, and battery model of the laptop twin.
    """
    try:
        result = simulate_what_if(
            cpu_usage=payload.cpu_usage,
            gpu_usage=payload.gpu_usage,
            memory_usage=payload.memory_usage,
            battery_level=payload.battery_level,
            battery_health=payload.battery_health,
            power_source=payload.power_source,
            ambient_temperature=payload.ambient_temperature
        )
        return WhatIfSimulationResponse(**result)
    except Exception as e:
        logger.error(f"Error executing What-If simulation: {e}")
        raise HTTPException(status_code=500, detail=str(e))
