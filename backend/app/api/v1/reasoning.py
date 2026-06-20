from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
import uuid
from datetime import datetime

from app.core.database import get_db
from app.models.reasoning import ReasoningRule
from app.models.telemetry import TelemetrySnapshot
from app.schemas.reasoning import RuleCreate, RuleUpdate, RuleResponse, EvaluationResult
from app.services.reasoning_engine import evaluate_all_rules, seed_default_rules_if_empty

router = APIRouter()

@router.get("/rules", response_model=List[RuleResponse])
def list_rules(db: Session = Depends(get_db)):
    """
    List all reasoning rules.
    """
    seed_default_rules_if_empty(db)
    return db.query(ReasoningRule).order_by(ReasoningRule.created_at.asc()).all()


@router.post("/rules", response_model=RuleResponse)
def create_rule(payload: RuleCreate, db: Session = Depends(get_db)):
    """
    Create a new dynamic reasoning rule.
    """
    rule_id = f"rule-{str(uuid.uuid4())[:8]}"
    db_rule = ReasoningRule(
        id=rule_id,
        name=payload.name,
        description=payload.description,
        conditions=[c.dict() for c in payload.conditions],
        logical_operator=payload.logical_operator,
        conclusion=payload.conclusion,
        severity=payload.severity,
        is_active=payload.is_active,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(db_rule)
    db.commit()
    db.refresh(db_rule)
    return db_rule


@router.put("/rules/{rule_id}", response_model=RuleResponse)
def update_rule(rule_id: str, payload: RuleUpdate, db: Session = Depends(get_db)):
    """
    Update an existing reasoning rule.
    """
    db_rule = db.query(ReasoningRule).filter(ReasoningRule.id == rule_id).first()
    if not db_rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    update_data = payload.dict(exclude_unset=True)
    if "conditions" in update_data and update_data["conditions"] is not None:
        update_data["conditions"] = [c.dict() for c in update_data["conditions"]]

    for key, value in update_data.items():
        setattr(db_rule, key, value)

    db_rule.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_rule)
    return db_rule


@router.delete("/rules/{rule_id}")
def delete_rule(rule_id: str, db: Session = Depends(get_db)):
    """
    Delete a reasoning rule by ID.
    """
    db_rule = db.query(ReasoningRule).filter(ReasoningRule.id == rule_id).first()
    if not db_rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    db.delete(db_rule)
    db.commit()
    return {"status": "success", "message": f"Rule {rule_id} deleted successfully."}


@router.post("/evaluate/{device_id}", response_model=List[EvaluationResult])
def evaluate_rules(
    device_id: str,
    snapshot_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Evaluate all active rules against a device's telemetry snapshot.
    If snapshot_id is provided, evaluates against that snapshot, otherwise the latest snapshot.
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

    return evaluate_all_rules(snapshot, db)
