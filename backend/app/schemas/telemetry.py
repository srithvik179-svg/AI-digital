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
    power_source: str = Field(..., example="ac")  # 'battery' or 'ac'
    active_process_count: int = Field(..., ge=0, example=112)
    
    # Extended optional metrics for normalized schema
    cpu_frequency_mhz: Optional[float] = Field(default=None, example=2400.0)
    gpu_usage: Optional[float] = Field(default=None, ge=0.0, le=100.0, example=12.5)
    gpu_temperature: Optional[float] = Field(default=None, example=58.0)
    gpu_memory_usage: Optional[float] = Field(default=None, ge=0.0, le=100.0, example=15.0)
    battery_temperature: Optional[float] = Field(default=None, example=32.5)
    cycle_count: Optional[int] = Field(default=None, ge=0, example=145)
    read_bytes_sec: Optional[int] = Field(default=None, ge=0, example=102400)
    write_bytes_sec: Optional[int] = Field(default=None, ge=0, example=40960)
    signal_strength_dbm: Optional[int] = Field(default=None, le=0, ge=-100, example=-45)
    ssid: Optional[str] = Field(default=None, example="Dell_Guest_WiFi")
    link_speed_mbps: Optional[int] = Field(default=None, ge=0, example=866)
    thermal_state: Optional[str] = Field(default=None, example="nominal")
    power_draw_watts: Optional[float] = Field(default=None, example=12.5)
    voltage_mv: Optional[float] = Field(default=None, example=12000.0)
    
    metadata_info: Optional[Dict[str, Any]] = None


class TelemetryResponse(BaseModel):
    id: str
    device_id: str
    timestamp: datetime
    
    # Core performance metrics
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    
    # Thermal and power metrics
    cpu_temperature: float
    battery_level: float
    battery_health: float
    fan_speed: int
    
    # Status and environment metrics
    power_source: str
    active_process_count: int
    
    # Extended metrics
    cpu_frequency_mhz: Optional[float] = None
    gpu_usage: Optional[float] = None
    gpu_temperature: Optional[float] = None
    gpu_memory_usage: Optional[float] = None
    battery_temperature: Optional[float] = None
    cycle_count: Optional[int] = None
    read_bytes_sec: Optional[int] = None
    write_bytes_sec: Optional[int] = None
    signal_strength_dbm: Optional[int] = None
    ssid: Optional[str] = None
    link_speed_mbps: Optional[int] = None
    thermal_state: Optional[str] = None
    power_draw_watts: Optional[float] = None
    voltage_mv: Optional[float] = None

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
