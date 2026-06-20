from sqlalchemy import Column, String, Float, Boolean, DateTime, ForeignKey, Text
from datetime import datetime
from app.core.database import Base


class TelemetryAlert(Base):
    __tablename__ = "telemetry_alerts"

    id               = Column(String(36),  primary_key=True)
    device_id        = Column(String(255), nullable=False, index=True)
    snapshot_id      = Column(String(36),  ForeignKey("telemetry_snapshots.id", ondelete="SET NULL"), nullable=True)
    category         = Column(String(30),  nullable=False)
    severity         = Column(String(10),  nullable=False)
    rule_id          = Column(String(60),  nullable=False)
    message          = Column(Text,        nullable=False)
    metric_name      = Column(String(60),  nullable=False)
    metric_value     = Column(Float,       nullable=False)
    threshold_value  = Column(Float,       nullable=False)
    triggered_at     = Column(DateTime,    default=datetime.utcnow, nullable=False)
    acknowledged     = Column(Boolean,     default=False, nullable=False)
    acknowledged_at  = Column(DateTime,    nullable=True)
