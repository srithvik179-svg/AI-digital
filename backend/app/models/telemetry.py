from sqlalchemy import Column, Integer, Float, String, DateTime, ForeignKey, BigInteger
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base

class TelemetrySnapshot(Base):
    __tablename__ = "telemetry_snapshots"

    id = Column(String(36), primary_key=True)
    device_id = Column(String(255), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # 1-to-1 relationships to child entities
    cpu = relationship("CPUMetrics", back_populates="snapshot", uselist=False, cascade="all, delete-orphan")
    gpu = relationship("GPUMetrics", back_populates="snapshot", uselist=False, cascade="all, delete-orphan")
    memory = relationship("MemoryMetrics", back_populates="snapshot", uselist=False, cascade="all, delete-orphan")
    battery = relationship("BatteryMetrics", back_populates="snapshot", uselist=False, cascade="all, delete-orphan")
    disk = relationship("DiskMetrics", back_populates="snapshot", uselist=False, cascade="all, delete-orphan")
    wifi = relationship("WiFiMetrics", back_populates="snapshot", uselist=False, cascade="all, delete-orphan")
    thermal = relationship("ThermalMetrics", back_populates="snapshot", uselist=False, cascade="all, delete-orphan")
    power = relationship("PowerMetrics", back_populates="snapshot", uselist=False, cascade="all, delete-orphan")


class CPUMetrics(Base):
    __tablename__ = "cpu_metrics"

    snapshot_id = Column(String(36), ForeignKey("telemetry_snapshots.id", ondelete="CASCADE"), primary_key=True)
    cpu_usage = Column(Float, nullable=False)
    active_process_count = Column(Integer, nullable=False)
    cpu_frequency_mhz = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    snapshot = relationship("TelemetrySnapshot", back_populates="cpu")


class GPUMetrics(Base):
    __tablename__ = "gpu_metrics"

    snapshot_id = Column(String(36), ForeignKey("telemetry_snapshots.id", ondelete="CASCADE"), primary_key=True)
    gpu_usage = Column(Float, nullable=False)
    gpu_temperature = Column(Float, nullable=True)
    gpu_memory_usage = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    snapshot = relationship("TelemetrySnapshot", back_populates="gpu")


class MemoryMetrics(Base):
    __tablename__ = "memory_metrics"

    snapshot_id = Column(String(36), ForeignKey("telemetry_snapshots.id", ondelete="CASCADE"), primary_key=True)
    memory_usage = Column(Float, nullable=False)
    total_mb = Column(Float, nullable=True)
    used_mb = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    snapshot = relationship("TelemetrySnapshot", back_populates="memory")


class BatteryMetrics(Base):
    __tablename__ = "battery_metrics"

    snapshot_id = Column(String(36), ForeignKey("telemetry_snapshots.id", ondelete="CASCADE"), primary_key=True)
    battery_level = Column(Float, nullable=False)
    battery_health = Column(Float, nullable=False)
    battery_temperature = Column(Float, nullable=True)
    cycle_count = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    snapshot = relationship("TelemetrySnapshot", back_populates="battery")


class DiskMetrics(Base):
    __tablename__ = "disk_metrics"

    snapshot_id = Column(String(36), ForeignKey("telemetry_snapshots.id", ondelete="CASCADE"), primary_key=True)
    disk_usage = Column(Float, nullable=False)
    read_bytes_sec = Column(BigInteger, nullable=True)
    write_bytes_sec = Column(BigInteger, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    snapshot = relationship("TelemetrySnapshot", back_populates="disk")


class WiFiMetrics(Base):
    __tablename__ = "wifi_metrics"

    snapshot_id = Column(String(36), ForeignKey("telemetry_snapshots.id", ondelete="CASCADE"), primary_key=True)
    signal_strength_dbm = Column(Integer, nullable=True)
    ssid = Column(String(255), nullable=True)
    link_speed_mbps = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    snapshot = relationship("TelemetrySnapshot", back_populates="wifi")


class ThermalMetrics(Base):
    __tablename__ = "thermal_metrics"

    snapshot_id = Column(String(36), ForeignKey("telemetry_snapshots.id", ondelete="CASCADE"), primary_key=True)
    cpu_temperature = Column(Float, nullable=False)
    fan_speed_rpm = Column(Integer, nullable=False)
    thermal_state = Column(String(50), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    snapshot = relationship("TelemetrySnapshot", back_populates="thermal")


class PowerMetrics(Base):
    __tablename__ = "power_metrics"

    snapshot_id = Column(String(36), ForeignKey("telemetry_snapshots.id", ondelete="CASCADE"), primary_key=True)
    power_source = Column(String(50), nullable=False)  # 'battery' or 'ac'
    power_draw_watts = Column(Float, nullable=True)
    voltage_mv = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    snapshot = relationship("TelemetrySnapshot", back_populates="power")
