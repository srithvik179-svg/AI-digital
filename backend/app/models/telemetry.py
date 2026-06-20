from sqlalchemy import Column, Integer, Float, String, DateTime, JSON
from datetime import datetime
from app.core.database import Base

class TelemetryRecord(Base):
    __tablename__ = "telemetry_records"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String, index=True, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Core performance metrics
    cpu_usage = Column(Float, nullable=False)
    memory_usage = Column(Float, nullable=False)
    disk_usage = Column(Float, nullable=False)
    
    # Thermal and power metrics
    cpu_temperature = Column(Float, nullable=False)
    battery_level = Column(Float, nullable=False)
    battery_health = Column(Float, nullable=False)
    fan_speed = Column(Integer, nullable=False)
    
    # Status and environment metrics
    power_source = Column(String, nullable=False) # 'battery' or 'ac'
    active_process_count = Column(Integer, nullable=False)
    
    # Raw logs or extra metadata
    metadata_info = Column(JSON, nullable=True)
