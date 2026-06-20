from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Dict, Any

class TelemetryCreate(BaseModel):
    device_id: str = Field(..., example="laptop-mac-001")
    cpu_usage: float = Field(..., ge=0.0, le=100.0, example=24.5)
    memory_usage: float = Field(..., ge=0.0, le=100.0, example=68.2)
    disk_usage: float = Field(..., ge=0.0, le=100.0, example=45.1)
    cpu_temperature: float = Field(..., example=55.0)
    battery_level: float = Field(..., ge=0.0, le=100.0, example=85.0)
    battery_health: float = Field(..., ge=0.0, le=100.0, example=92.0)
    fan_speed: int = Field(..., ge=0, example=2400)
    power_source: str = Field(..., example="ac") # 'battery' or 'ac'
    active_process_count: int = Field(..., ge=0, example=112)
    metadata_info: Optional[Dict[str, Any]] = None

class TelemetryResponse(TelemetryCreate):
    id: int
    timestamp: datetime

    class Config:
        from_attributes = True

class TwinQuery(BaseModel):
    device_id: str = Field(..., example="laptop-mac-001")
    query: str = Field(..., example="Is my battery health declining or stable?")

class TwinResponse(BaseModel):
    query: str
    response: str
    source_documents: list[str] = []
    timestamp: datetime = Field(default_factory=datetime.utcnow)
