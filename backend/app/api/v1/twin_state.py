from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import Dict, Any
from app.core.database import get_db
from app.core.logging import logger
from app.models.telemetry import TelemetrySnapshot
from app.schemas.telemetry import SimulationRequest
from app.services.digital_twin_model import VirtualLaptop

router = APIRouter()

@router.get("", response_model=Dict[str, Any])
def get_digital_twin_state(
    device_id: str,
    db: Session = Depends(get_db)
):
    """
    Get the complete, unified object-oriented virtual state of the laptop twin.
    Includes sub-system analytics, battery degradation trends, and fan curves.
    """
    snapshot = (
        db.query(TelemetrySnapshot)
        .options(
            joinedload(TelemetrySnapshot.cpu),
            joinedload(TelemetrySnapshot.gpu),
            joinedload(TelemetrySnapshot.memory),
            joinedload(TelemetrySnapshot.battery),
            joinedload(TelemetrySnapshot.disk),
            joinedload(TelemetrySnapshot.wifi),
            joinedload(TelemetrySnapshot.thermal),
            joinedload(TelemetrySnapshot.power)
        )
        .filter(TelemetrySnapshot.device_id == device_id)
        .order_by(TelemetrySnapshot.timestamp.desc())
        .first()
    )

    if not snapshot:
        raise HTTPException(
            status_code=404, 
            detail=f"No telemetry data found for device '{device_id}' to initialize the Virtual Digital Twin."
        )

    laptop = VirtualLaptop(device_id)
    laptop.update_state(snapshot)
    return laptop.get_state_dict()


@router.post("/simulate", response_model=Dict[str, Any])
def simulate_digital_twin_workload(
    payload: SimulationRequest,
    db: Session = Depends(get_db)
):
    """
    Simulate a custom CPU/GPU workload for a specific duration on the virtual laptop.
    Returns thermodynamic projections (temperature rise, fan speed, battery level drain).
    Does not modify real historical database log states.
    """
    snapshot = (
        db.query(TelemetrySnapshot)
        .options(
            joinedload(TelemetrySnapshot.cpu),
            joinedload(TelemetrySnapshot.gpu),
            joinedload(TelemetrySnapshot.memory),
            joinedload(TelemetrySnapshot.battery),
            joinedload(TelemetrySnapshot.disk),
            joinedload(TelemetrySnapshot.wifi),
            joinedload(TelemetrySnapshot.thermal),
            joinedload(TelemetrySnapshot.power)
        )
        .filter(TelemetrySnapshot.device_id == payload.device_id)
        .order_by(TelemetrySnapshot.timestamp.desc())
        .first()
    )

    if not snapshot:
        raise HTTPException(
            status_code=404, 
            detail=f"No telemetry data found for device '{payload.device_id}' to initialize the Virtual Digital Twin."
        )

    laptop = VirtualLaptop(payload.device_id)
    laptop.update_state(snapshot)
    
    projection = laptop.simulate_workload(
        cpu_load=payload.cpu_load,
        gpu_load=payload.gpu_load,
        duration_mins=payload.duration_minutes
    )
    return projection
