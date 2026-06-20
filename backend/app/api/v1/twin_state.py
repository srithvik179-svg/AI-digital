from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import Dict, Any, List
from app.core.database import get_db
from app.core.logging import logger
from app.models.telemetry import TelemetrySnapshot
from app.schemas.telemetry import SimulationRequest, WhatIfRequest
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


@router.get("/replay", response_model=List[Dict[str, Any]])
def get_historical_replay(
    device_id: str,
    limit: int = 60,
    db: Session = Depends(get_db)
):
    """
    Retrieves a chronological list of historical telemetry snapshots (oldest to newest)
    along with their corresponding digital twin states for playback on the frontend.
    """
    snapshots = (
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
        .limit(limit)
        .all()
    )
    
    # We queried desc to apply the limit, now reverse to chronological order
    snapshots.reverse()
    
    from app.api.v1.telemetry import flatten_snapshot
    
    # Instantiate a VirtualLaptop that accumulates states over the chronological sequence
    laptop = VirtualLaptop(device_id)
    
    replay_data = []
    for s in snapshots:
        laptop.update_state(s)
        flat = flatten_snapshot(s)
        # Override twin_state to match the running accumulated state of VirtualLaptop
        flat["twin_state"] = laptop.get_state_dict()
        replay_data.append(flat)
        
    return replay_data


@router.post("/what-if", response_model=List[Dict[str, Any]])
def simulate_what_if_scenario(
    payload: WhatIfRequest,
    db: Session = Depends(get_db)
):
    """
    Simulates a 'What-If' scenario branching off from a specific historical snapshot.
    Runs a multi-step simulation at 1-minute intervals and returns the projected states.
    """
    # 1. Fetch starting snapshot
    query = (
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
    )
    
    if payload.start_timestamp:
        # Find snapshot closest to start_timestamp
        snapshot = query.filter(TelemetrySnapshot.timestamp <= payload.start_timestamp).order_by(TelemetrySnapshot.timestamp.desc()).first()
        if not snapshot:
            snapshot = query.filter(TelemetrySnapshot.timestamp >= payload.start_timestamp).order_by(TelemetrySnapshot.timestamp.asc()).first()
    else:
        snapshot = query.order_by(TelemetrySnapshot.timestamp.desc()).first()
        
    if not snapshot:
        raise HTTPException(
            status_code=404,
            detail=f"No telemetry data found for device '{payload.device_id}' to seed the scenario simulation."
        )

    # 2. Run simulation steps
    laptop = VirtualLaptop(payload.device_id)
    laptop.update_state(snapshot)
    
    import datetime
    start_dt = snapshot.timestamp
    
    states = laptop.simulate_time_series_workload(
        cpu_load=payload.cpu_load,
        gpu_load=payload.gpu_load,
        duration_mins=payload.duration_minutes,
        power_source=payload.power_source
    )
    
    # 3. Format projected path
    projected_path = []
    for idx, state in enumerate(states):
        step_time = start_dt + datetime.timedelta(minutes=idx + 1)
        projected_path.append({
            "timestamp": step_time.isoformat(),
            # Flatten/simplify key indicators for easier frontend consumption
            "cpu_usage": state["components"]["cpu"]["current_usage"],
            "cpu_temperature": state["components"]["thermal"]["cpu_temperature"],
            "battery_level": state["components"]["battery"]["level"],
            "fan_speed": state["components"]["thermal"]["fan_speed_rpm"],
            "cpu_frequency_mhz": state["components"]["cpu"]["frequency_mhz"],
            "state": state
        })
        
    return projected_path
