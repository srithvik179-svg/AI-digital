from sqlalchemy import Column, String, Float, DateTime, Text
from datetime import datetime
from app.core.database import Base

class TelemetryRelationship(Base):
    """
    SQLAlchemy database model for storing computed telemetry dependencies and correlations.
    """
    __tablename__ = "telemetry_relationships"

    id = Column(String(36), primary_key=True)
    device_id = Column(String(255), nullable=False, index=True)
    source_node = Column(String(50), nullable=False)
    target_node = Column(String(50), nullable=False)
    relationship_type = Column(String(50), nullable=False)
    correlation_strength = Column(Float, nullable=False)
    dependency_description = Column(Text, nullable=False)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
