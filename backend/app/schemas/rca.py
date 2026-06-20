from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class RCARequest(BaseModel):
    snapshot_id: Optional[str] = Field(None, description="Optional snapshot ID to analyze. If omitted, analyzes the latest snapshot.")

class RCADiagnosis(BaseModel):
    cause: str = Field(..., description="The likely root cause of the alert profile")
    confidence: float = Field(..., description="Confidence score between 0.0 and 1.0")
    evidence: List[str] = Field(..., description="Telemetry parameters acting as evidence")
    remedy: str = Field(..., description="Actionable recommendation to resolve the root cause")
    path: List[str] = Field(..., description="Trace of the decision pathway and dependency influence")

class RCAResponse(BaseModel):
    device_id: str = Field(..., description="Target laptop device ID")
    snapshot_id: str = Field(..., description="Evaluated snapshot UUID")
    timestamp: datetime = Field(..., description="Telemetry snapshot timestamp")
    active_alerts: List[str] = Field(..., description="List of rule IDs triggered at this snapshot")
    diagnoses: List[RCADiagnosis] = Field(..., description="Ranked likely causes mapped to confidences")
