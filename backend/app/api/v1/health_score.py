from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel

from app.core.database import get_db
from app.core.logging import logger
from app.models.telemetry import TelemetrySnapshot, CPUMetrics, MemoryMetrics, ThermalMetrics, BatteryMetrics, DiskMetrics, WiFiMetrics, GPUMetrics
from app.services.health_score import compute_health_score, CATEGORY_HEALTHY, CATEGORY_WARNING, CATEGORY_CRITICAL

router = APIRouter()


# ─── Response Schemas ─────────────────────────────────────────────────────────

class HealthScoreResponse(BaseModel):
    snapshot_id: str
    device_id: str
    timestamp: datetime
    score: float
    category: str
    breakdown: dict
    recommendations: list[str]

class HealthSummaryResponse(BaseModel):
    device_id: str
    latest_score: Optional[float]
    latest_category: Optional[str]
    avg_score_24h: Optional[float]
    min_score_24h: Optional[float]
    critical_count_24h: int
    warning_count_24h: int
    healthy_count_24h: int
    snapshot_count_24h: int
    recommendations: list[str]

class ComputeScoreResponse(BaseModel):
    score: float
    category: str
    breakdown: dict
    recommendations: list[str]


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/compute", response_model=ComputeScoreResponse, tags=["health-score"])
def compute_score_endpoint(
    cpu_usage: float = Query(..., ge=0, le=100, description="CPU utilization %"),
    memory_usage: float = Query(..., ge=0, le=100, description="Memory usage %"),
    disk_usage: float = Query(..., ge=0, le=100, description="Disk usage %"),
    cpu_temperature: float = Query(..., description="CPU temperature °C"),
    battery_level: float = Query(..., ge=0, le=100, description="Battery charge %"),
    battery_health: float = Query(..., ge=0, le=100, description="Battery health %"),
    gpu_usage: Optional[float] = Query(default=None, ge=0, le=100),
    signal_strength_dbm: Optional[float] = Query(default=None, ge=-100, le=0),
    power_source: str = Query(default="ac"),
    thermal_state: Optional[str] = Query(default=None),
):
    """
    Compute a real-time health score from raw telemetry inputs without storing
    anything. Useful for quick debugging or testing the scoring formula.
    """
    result = compute_health_score(
        cpu_usage=cpu_usage,
        memory_usage=memory_usage,
        disk_usage=disk_usage,
        cpu_temperature=cpu_temperature,
        battery_level=battery_level,
        battery_health=battery_health,
        gpu_usage=gpu_usage,
        signal_strength_dbm=signal_strength_dbm,
        power_source=power_source,
        thermal_state=thermal_state,
    )
    return ComputeScoreResponse(
        score=result.score,
        category=result.category,
        breakdown=result.breakdown,
        recommendations=result.recommendations,
    )


@router.get("/device/{device_id}/latest", response_model=HealthScoreResponse, tags=["health-score"])
def get_latest_health_score(device_id: str, db: Session = Depends(get_db)):
    """
    Returns the most recent health score snapshot for a device.
    Re-computes live if the stored score is missing.
    """
    snapshot = (
        db.query(TelemetrySnapshot)
        .filter(TelemetrySnapshot.device_id == device_id)
        .order_by(TelemetrySnapshot.timestamp.desc())
        .first()
    )
    if not snapshot:
        raise HTTPException(status_code=404, detail=f"No telemetry found for device '{device_id}'")

    # If score was stored use it, otherwise compute on the fly
    if snapshot.health_score is not None:
        result = compute_health_score(
            cpu_usage=snapshot.cpu.cpu_usage if snapshot.cpu else 0,
            memory_usage=snapshot.memory.memory_usage if snapshot.memory else 0,
            disk_usage=snapshot.disk.disk_usage if snapshot.disk else 0,
            cpu_temperature=snapshot.thermal.cpu_temperature if snapshot.thermal else 45,
            battery_level=snapshot.battery.battery_level if snapshot.battery else 100,
            battery_health=snapshot.battery.battery_health if snapshot.battery else 100,
            gpu_usage=snapshot.gpu.gpu_usage if snapshot.gpu else None,
            signal_strength_dbm=snapshot.wifi.signal_strength_dbm if snapshot.wifi else None,
            power_source=snapshot.power.power_source if snapshot.power else "ac",
            thermal_state=snapshot.thermal.thermal_state if snapshot.thermal else None,
        )
        return HealthScoreResponse(
            snapshot_id=snapshot.id,
            device_id=snapshot.device_id,
            timestamp=snapshot.timestamp,
            score=snapshot.health_score,
            category=snapshot.health_category or result.category,
            breakdown=result.breakdown,
            recommendations=result.recommendations,
        )

    # Compute and return without storing (snapshot may lack child rows from old seed data)
    result = compute_health_score(
        cpu_usage=snapshot.cpu.cpu_usage if snapshot.cpu else 50,
        memory_usage=snapshot.memory.memory_usage if snapshot.memory else 50,
        disk_usage=snapshot.disk.disk_usage if snapshot.disk else 40,
        cpu_temperature=snapshot.thermal.cpu_temperature if snapshot.thermal else 55,
        battery_level=snapshot.battery.battery_level if snapshot.battery else 80,
        battery_health=snapshot.battery.battery_health if snapshot.battery else 90,
        gpu_usage=snapshot.gpu.gpu_usage if snapshot.gpu else None,
        signal_strength_dbm=snapshot.wifi.signal_strength_dbm if snapshot.wifi else None,
        power_source=snapshot.power.power_source if snapshot.power else "ac",
        thermal_state=snapshot.thermal.thermal_state if snapshot.thermal else None,
    )
    return HealthScoreResponse(
        snapshot_id=snapshot.id,
        device_id=snapshot.device_id,
        timestamp=snapshot.timestamp,
        score=result.score,
        category=result.category,
        breakdown=result.breakdown,
        recommendations=result.recommendations,
    )


@router.get("/device/{device_id}/history", response_model=List[dict], tags=["health-score"])
def get_health_score_history(
    device_id: str,
    hours: int = Query(default=24, ge=1, le=168),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """
    Returns a time-series of health scores for a device over the last N hours.
    Ordered chronologically (oldest first) for charting.
    """
    since = datetime.utcnow() - timedelta(hours=hours)
    snapshots = (
        db.query(
            TelemetrySnapshot.id,
            TelemetrySnapshot.timestamp,
            TelemetrySnapshot.health_score,
            TelemetrySnapshot.health_category,
        )
        .filter(
            TelemetrySnapshot.device_id == device_id,
            TelemetrySnapshot.timestamp >= since,
            TelemetrySnapshot.health_score.isnot(None),
        )
        .order_by(TelemetrySnapshot.timestamp.asc())
        .limit(limit)
        .all()
    )
    return [
        {
            "snapshot_id": s.id,
            "timestamp": s.timestamp.isoformat(),
            "score": s.health_score,
            "category": s.health_category,
        }
        for s in snapshots
    ]


@router.get("/device/{device_id}/summary", response_model=HealthSummaryResponse, tags=["health-score"])
def get_health_summary(device_id: str, db: Session = Depends(get_db)):
    """
    24-hour summary: latest score, average, min, category distribution counts.
    """
    since = datetime.utcnow() - timedelta(hours=24)

    latest = (
        db.query(TelemetrySnapshot)
        .filter(TelemetrySnapshot.device_id == device_id)
        .order_by(TelemetrySnapshot.timestamp.desc())
        .first()
    )
    if not latest:
        raise HTTPException(status_code=404, detail=f"No telemetry found for device '{device_id}'")

    # Aggregate over last 24h
    agg = (
        db.query(
            func.avg(TelemetrySnapshot.health_score).label("avg_score"),
            func.min(TelemetrySnapshot.health_score).label("min_score"),
            func.count(TelemetrySnapshot.id).label("total"),
        )
        .filter(
            TelemetrySnapshot.device_id == device_id,
            TelemetrySnapshot.timestamp >= since,
            TelemetrySnapshot.health_score.isnot(None),
        )
        .first()
    )

    def count_category(cat: str) -> int:
        return (
            db.query(func.count(TelemetrySnapshot.id))
            .filter(
                TelemetrySnapshot.device_id == device_id,
                TelemetrySnapshot.timestamp >= since,
                TelemetrySnapshot.health_category == cat,
            )
            .scalar() or 0
        )

    critical_n = count_category(CATEGORY_CRITICAL)
    warning_n  = count_category(CATEGORY_WARNING)
    healthy_n  = count_category(CATEGORY_HEALTHY)

    # Build live recommendations from latest snapshot
    result = compute_health_score(
        cpu_usage=latest.cpu.cpu_usage if latest.cpu else 50,
        memory_usage=latest.memory.memory_usage if latest.memory else 50,
        disk_usage=latest.disk.disk_usage if latest.disk else 40,
        cpu_temperature=latest.thermal.cpu_temperature if latest.thermal else 55,
        battery_level=latest.battery.battery_level if latest.battery else 80,
        battery_health=latest.battery.battery_health if latest.battery else 90,
        gpu_usage=latest.gpu.gpu_usage if latest.gpu else None,
        signal_strength_dbm=latest.wifi.signal_strength_dbm if latest.wifi else None,
        power_source=latest.power.power_source if latest.power else "ac",
        thermal_state=latest.thermal.thermal_state if latest.thermal else None,
    )

    return HealthSummaryResponse(
        device_id=device_id,
        latest_score=latest.health_score,
        latest_category=latest.health_category,
        avg_score_24h=round(agg.avg_score, 2) if agg.avg_score else None,
        min_score_24h=round(agg.min_score, 2) if agg.min_score else None,
        critical_count_24h=critical_n,
        warning_count_24h=warning_n,
        healthy_count_24h=healthy_n,
        snapshot_count_24h=agg.total or 0,
        recommendations=result.recommendations,
    )


@router.get("/alerts", tags=["health-score"])
def get_critical_alerts(
    hours: int = Query(default=1, ge=1, le=72),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    Returns all Critical-category snapshots across all devices in the last N hours.
    Used by monitoring dashboards to surface active alerts.
    """
    since = datetime.utcnow() - timedelta(hours=hours)
    rows = (
        db.query(
            TelemetrySnapshot.id,
            TelemetrySnapshot.device_id,
            TelemetrySnapshot.timestamp,
            TelemetrySnapshot.health_score,
            TelemetrySnapshot.health_category,
        )
        .filter(
            TelemetrySnapshot.timestamp >= since,
            TelemetrySnapshot.health_category == CATEGORY_CRITICAL,
        )
        .order_by(TelemetrySnapshot.timestamp.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "snapshot_id": r.id,
            "device_id": r.device_id,
            "timestamp": r.timestamp.isoformat(),
            "score": r.health_score,
            "category": r.health_category,
        }
        for r in rows
    ]
