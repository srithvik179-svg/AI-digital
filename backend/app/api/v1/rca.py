from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from typing import Optional

from app.core.database import get_db
from app.models.telemetry import TelemetrySnapshot
from app.schemas.rca import RCAResponse
from app.services.rca_engine import run_rca_analysis, get_snapshot_alerts

router = APIRouter()

@router.post("/analyze/{device_id}", response_model=RCAResponse)
def analyze_root_cause(
    device_id: str,
    snapshot_id: Optional[str] = Query(None, description="Snapshot UUID to analyze. If omitted, gets latest snapshot."),
    db: Session = Depends(get_db)
):
    """
    Run Root Cause Analysis for a device state.
    Queries active alerts, runs decision trees, traverses graph influences, and returns ranked diagnoses.
    """
    query = db.query(TelemetrySnapshot).options(
        joinedload(TelemetrySnapshot.cpu),
        joinedload(TelemetrySnapshot.gpu),
        joinedload(TelemetrySnapshot.memory),
        joinedload(TelemetrySnapshot.battery),
        joinedload(TelemetrySnapshot.disk),
        joinedload(TelemetrySnapshot.wifi),
        joinedload(TelemetrySnapshot.thermal),
        joinedload(TelemetrySnapshot.power)
    )

    if snapshot_id:
        snapshot = query.filter(TelemetrySnapshot.id == snapshot_id).first()
        if not snapshot:
            raise HTTPException(status_code=404, detail="Snapshot not found")
    else:
        snapshot = (
            query.filter(TelemetrySnapshot.device_id == device_id)
            .order_by(TelemetrySnapshot.timestamp.desc())
            .first()
        )
        if not snapshot:
            raise HTTPException(
                status_code=404,
                detail=f"No telemetry snapshots found for device {device_id}"
            )

    diagnoses = run_rca_analysis(snapshot, db)
    alerts = get_snapshot_alerts(snapshot, db)

    return {
        "device_id": snapshot.device_id,
        "snapshot_id": snapshot.id,
        "timestamp": snapshot.timestamp,
        "active_alerts": [a["rule_id"] for a in alerts],
        "diagnoses": diagnoses
    }
