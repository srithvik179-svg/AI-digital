from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel

from app.core.database import get_db
from app.core.logging import logger
from app.models.alert import TelemetryAlert
from app.services.alert_engine import (
    evaluate_alerts, AlertSeverity, AlertCategory,
    group_alerts_by_category, RULES
)

router = APIRouter()


# ─── Pydantic schemas ─────────────────────────────────────────────────

class AlertOut(BaseModel):
    id: str
    device_id: str
    snapshot_id: Optional[str] = None
    category: str
    severity: str
    rule_id: str
    message: str
    metric_name: str
    metric_value: float
    threshold_value: float
    triggered_at: datetime
    acknowledged: bool
    acknowledged_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AlertStatsOut(BaseModel):
    device_id: str
    total_alerts: int
    unacknowledged: int
    critical_count: int
    warning_count: int
    by_category: dict
    oldest_unack: Optional[datetime] = None
    latest_alert: Optional[datetime] = None


class ComputeAlertsRequest(BaseModel):
    device_id: str = "test-device"
    cpu_temperature: float
    battery_level: float
    battery_health: float
    disk_usage: float
    gpu_temperature: Optional[float] = None
    battery_temperature: Optional[float] = None
    cycle_count: Optional[int] = None
    write_bytes_sec: Optional[int] = None
    signal_strength_dbm: Optional[float] = None
    link_speed_mbps: Optional[int] = None
    thermal_state: Optional[str] = None
    power_source: str = "ac"


# ─── Utility: persist a list of Alert objects ─────────────────────────

def save_alerts(db: Session, alerts, snapshot_id: str = "") -> None:
    """Bulk-insert Alert dataclass instances into the DB."""
    for a in alerts:
        row = TelemetryAlert(
            id=a.id,
            device_id=a.device_id,
            snapshot_id=snapshot_id or a.snapshot_id or None,
            category=a.category,
            severity=a.severity,
            rule_id=a.rule_id,
            message=a.message,
            metric_name=a.metric_name,
            metric_value=a.metric_value,
            threshold_value=a.threshold_value,
            triggered_at=a.triggered_at,
            acknowledged=False,
        )
        db.add(row)
    if alerts:
        db.commit()


# ─── Endpoints ────────────────────────────────────────────────────────

@router.post("/compute", tags=["alerts"])
def compute_alerts_endpoint(body: ComputeAlertsRequest):
    """
    Evaluate alert rules against arbitrary telemetry inputs without touching
    the database. Ideal for testing rules or pre-flight checks.
    """
    alerts = evaluate_alerts(
        cpu_temperature=body.cpu_temperature,
        battery_level=body.battery_level,
        battery_health=body.battery_health,
        disk_usage=body.disk_usage,
        gpu_temperature=body.gpu_temperature,
        battery_temperature=body.battery_temperature,
        cycle_count=body.cycle_count,
        write_bytes_sec=body.write_bytes_sec,
        signal_strength_dbm=body.signal_strength_dbm,
        link_speed_mbps=body.link_speed_mbps,
        thermal_state=body.thermal_state,
        power_source=body.power_source,
        device_id=body.device_id,
    )
    return {
        "alert_count": len(alerts),
        "alerts": [
            {
                "rule_id": a.rule_id,
                "category": a.category,
                "severity": a.severity,
                "message": a.message,
                "metric_name": a.metric_name,
                "metric_value": a.metric_value,
                "threshold_value": a.threshold_value,
            }
            for a in alerts
        ],
        "by_category": {
            cat: [a.rule_id for a in lst]
            for cat, lst in group_alerts_by_category(alerts).items()
            if lst
        },
    }


@router.get("/rules", tags=["alerts"])
def list_rules():
    """Return all configured detection rules (for dashboard display)."""
    return [
        {
            "rule_id": r.rule_id,
            "category": r.category,
            "severity": r.severity,
            "metric_name": r.metric_name,
            "threshold": r.threshold,
        }
        for r in RULES
    ]


@router.get("/active", response_model=List[AlertOut], tags=["alerts"])
def get_active_alerts(
    severity: Optional[str] = Query(default=None, description="Filter: Warning | Critical"),
    category: Optional[str] = Query(default=None, description="Filter: Overheating | Battery | Disk | Network"),
    device_id: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """All unacknowledged alerts across all devices, most recent first."""
    q = db.query(TelemetryAlert).filter(TelemetryAlert.acknowledged == False)
    if device_id:
        q = q.filter(TelemetryAlert.device_id == device_id)
    if severity:
        q = q.filter(TelemetryAlert.severity == severity)
    if category:
        q = q.filter(TelemetryAlert.category == category)
    return q.order_by(desc(TelemetryAlert.triggered_at)).limit(limit).all()


@router.get("/device/{device_id}", response_model=List[AlertOut], tags=["alerts"])
def get_device_alerts(
    device_id: str,
    hours: int = Query(default=24, ge=1, le=168),
    severity: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    acknowledged: Optional[bool] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Alerts for a specific device in the last N hours."""
    since = datetime.utcnow() - timedelta(hours=hours)
    q = (
        db.query(TelemetryAlert)
        .filter(TelemetryAlert.device_id == device_id)
        .filter(TelemetryAlert.triggered_at >= since)
    )
    if severity:
        q = q.filter(TelemetryAlert.severity == severity)
    if category:
        q = q.filter(TelemetryAlert.category == category)
    if acknowledged is not None:
        q = q.filter(TelemetryAlert.acknowledged == acknowledged)
    return q.order_by(desc(TelemetryAlert.triggered_at)).limit(limit).all()


@router.get("/device/{device_id}/stats", response_model=AlertStatsOut, tags=["alerts"])
def get_alert_stats(
    device_id: str,
    hours: int = Query(default=24, ge=1, le=168),
    db: Session = Depends(get_db),
):
    """24h alert statistics for a device: counts by severity and category."""
    since = datetime.utcnow() - timedelta(hours=hours)
    base = db.query(TelemetryAlert).filter(
        TelemetryAlert.device_id == device_id,
        TelemetryAlert.triggered_at >= since,
    )

    total        = base.count()
    unacknowledged = base.filter(TelemetryAlert.acknowledged == False).count()
    critical_n   = base.filter(TelemetryAlert.severity == AlertSeverity.CRITICAL).count()
    warning_n    = base.filter(TelemetryAlert.severity == AlertSeverity.WARNING).count()

    by_category = {}
    for cat in [AlertCategory.OVERHEATING, AlertCategory.BATTERY, AlertCategory.DISK, AlertCategory.NETWORK]:
        by_category[cat] = base.filter(TelemetryAlert.category == cat).count()

    oldest_row = (
        base.filter(TelemetryAlert.acknowledged == False)
        .order_by(TelemetryAlert.triggered_at.asc())
        .first()
    )
    latest_row = base.order_by(desc(TelemetryAlert.triggered_at)).first()

    return AlertStatsOut(
        device_id=device_id,
        total_alerts=total,
        unacknowledged=unacknowledged,
        critical_count=critical_n,
        warning_count=warning_n,
        by_category=by_category,
        oldest_unack=oldest_row.triggered_at if oldest_row else None,
        latest_alert=latest_row.triggered_at if latest_row else None,
    )


@router.post("/acknowledge/{alert_id}", tags=["alerts"])
def acknowledge_alert(alert_id: str, db: Session = Depends(get_db)):
    """Mark a single alert as acknowledged."""
    alert = db.query(TelemetryAlert).filter(TelemetryAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found.")
    alert.acknowledged = True
    alert.acknowledged_at = datetime.utcnow()
    db.commit()
    return {"status": "acknowledged", "alert_id": alert_id, "acknowledged_at": alert.acknowledged_at}


@router.post("/acknowledge/device/{device_id}/all", tags=["alerts"])
def acknowledge_all_device_alerts(device_id: str, db: Session = Depends(get_db)):
    """Bulk-acknowledge all unacknowledged alerts for a device."""
    now = datetime.utcnow()
    updated = (
        db.query(TelemetryAlert)
        .filter(TelemetryAlert.device_id == device_id, TelemetryAlert.acknowledged == False)
        .update({"acknowledged": True, "acknowledged_at": now})
    )
    db.commit()
    return {"status": "acknowledged", "device_id": device_id, "count": updated, "acknowledged_at": now}


@router.get("/feed", tags=["alerts"])
def global_alert_feed(
    hours: int = Query(default=1, ge=1, le=72),
    limit: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    Global real-time alert feed: all unacknowledged Critical alerts in
    the last N hours across all devices. Used by the live dashboard ticker.
    """
    since = datetime.utcnow() - timedelta(hours=hours)
    rows = (
        db.query(TelemetryAlert)
        .filter(
            TelemetryAlert.triggered_at >= since,
            TelemetryAlert.acknowledged == False,
        )
        .order_by(desc(TelemetryAlert.triggered_at))
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "device_id": r.device_id,
            "category": r.category,
            "severity": r.severity,
            "rule_id": r.rule_id,
            "message": r.message,
            "metric_name": r.metric_name,
            "metric_value": r.metric_value,
            "triggered_at": r.triggered_at.isoformat(),
        }
        for r in rows
    ]
