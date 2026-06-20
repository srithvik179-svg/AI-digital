from sqlalchemy import Column, String, Text, Boolean, DateTime, JSON
from datetime import datetime
from app.core.database import Base

class ReasoningRule(Base):
    """
    SQLAlchemy database model for storing user-defined dynamic rules
    for the Phase 21 Rule-Based Reasoning Engine.
    """
    __tablename__ = "reasoning_rules"

    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    conditions = Column(JSON, nullable=False)          # Structure: [{'metric': 'cpu_usage', 'operator': '>', 'value': 80.0}]
    logical_operator = Column(String(10), nullable=False, default="AND") # 'AND' or 'OR'
    conclusion = Column(String(255), nullable=False)
    severity = Column(String(20), nullable=False, default="info")        # 'info', 'warning', 'critical'
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
