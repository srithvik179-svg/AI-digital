from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from typing import Optional
from pydantic import BaseModel

from app.core.database import get_db
from app.core.logging import logger
from app.models.telemetry import TelemetrySnapshot
from app.services.summary_engine import generate_summary, NLSummary

router = APIRouter()


# ─── Pydantic schemas ─────────────────────────────────────────────────

class SummaryRequest(BaseModel):
    """Direct telemetry input for on-the-fly summary generation."""
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    cpu_temperature: float
    battery_level: float
    battery_health: float
    fan_speed: Optional[int] = None
    gpu_usage: Optional[float] = None
    signal_strength_dbm: Optional[float] = None
    power_source: str = "ac"
    health_score: Optional[float] = None
    health_category: Optional[str] = None
    active_process_count: Optional[int] = None
    thermal_state: Optional[str] = None
    link_speed_mbps: Optional[int] = None


class SummaryResponse(BaseModel):
    headline: str
    paragraph: str
    observations: list[str]
    severity: str
    generated_in_ms: float


def _summary_to_response(s: NLSummary) -> dict:
    return {
        "headline": s.headline,
        "paragraph": s.paragraph,
        "observations": s.observations,
        "severity": s.severity,
        "generated_in_ms": s.generated_in_ms,
    }


# ─── Endpoints ────────────────────────────────────────────────────────

@router.post("/generate", tags=["summary"])
def generate_summary_endpoint(body: SummaryRequest):
    """
    Generate a natural-language summary from arbitrary telemetry inputs.
    No database read/write — pure template engine. Sub-millisecond.
    """
    summary = generate_summary(
        cpu_usage=body.cpu_usage,
        memory_usage=body.memory_usage,
        disk_usage=body.disk_usage,
        cpu_temperature=body.cpu_temperature,
        battery_level=body.battery_level,
        battery_health=body.battery_health,
        fan_speed=body.fan_speed,
        gpu_usage=body.gpu_usage,
        signal_strength_dbm=body.signal_strength_dbm,
        power_source=body.power_source,
        health_score=body.health_score,
        health_category=body.health_category,
        active_process_count=body.active_process_count,
        thermal_state=body.thermal_state,
        link_speed_mbps=body.link_speed_mbps,
    )
    return _summary_to_response(summary)


@router.get("/device/{device_id}/latest", tags=["summary"])
def get_latest_device_summary(device_id: str, db: Session = Depends(get_db)):
    """
    Generate a natural-language summary from the most recent telemetry
    snapshot stored in the database for the given device.
    """
    snapshot = (
        db.query(TelemetrySnapshot)
        .filter(TelemetrySnapshot.device_id == device_id)
        .options(
            joinedload(TelemetrySnapshot.cpu),
            joinedload(TelemetrySnapshot.memory),
            joinedload(TelemetrySnapshot.thermal),
            joinedload(TelemetrySnapshot.battery),
            joinedload(TelemetrySnapshot.disk),
            joinedload(TelemetrySnapshot.wifi),
            joinedload(TelemetrySnapshot.gpu),
            joinedload(TelemetrySnapshot.power),
        )
        .order_by(TelemetrySnapshot.timestamp.desc())
        .first()
    )
    if not snapshot:
        raise HTTPException(status_code=404, detail=f"No snapshots found for device '{device_id}'")

    summary = generate_summary(
        cpu_usage=snapshot.cpu.cpu_usage if snapshot.cpu else 0,
        memory_usage=snapshot.memory.memory_usage if snapshot.memory else 0,
        disk_usage=snapshot.disk.disk_usage if snapshot.disk else 0,
        cpu_temperature=snapshot.thermal.cpu_temperature if snapshot.thermal else 45,
        battery_level=snapshot.battery.battery_level if snapshot.battery else 100,
        battery_health=snapshot.battery.battery_health if snapshot.battery else 100,
        fan_speed=snapshot.thermal.fan_speed_rpm if snapshot.thermal else None,
        gpu_usage=snapshot.gpu.gpu_usage if snapshot.gpu else None,
        signal_strength_dbm=snapshot.wifi.signal_strength_dbm if snapshot.wifi else None,
        power_source=snapshot.power.power_source if snapshot.power else "ac",
        health_score=snapshot.health_score,
        health_category=snapshot.health_category,
        active_process_count=snapshot.cpu.active_process_count if snapshot.cpu else None,
        thermal_state=snapshot.thermal.thermal_state if snapshot.thermal else None,
        link_speed_mbps=snapshot.wifi.link_speed_mbps if snapshot.wifi else None,
    )
    return {
        "device_id": device_id,
        "snapshot_id": snapshot.id,
        "snapshot_timestamp": snapshot.timestamp.isoformat(),
        **_summary_to_response(summary),
    }
