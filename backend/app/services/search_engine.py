"""
Natural Language Telemetry Search Engine — Phase 9
Parses search queries into SQLAlchemy query filters on normalized metrics tables.
Supports metric keywords, threshold qualifiers, and boolean combination (AND/OR).
"""

from __future__ import annotations
from typing import List
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, joinedload
from app.models.telemetry import (
    TelemetrySnapshot,
    CPUMetrics,
    GPUMetrics,
    MemoryMetrics,
    BatteryMetrics,
    DiskMetrics,
    WiFiMetrics,
    ThermalMetrics,
    PowerMetrics
)

def search_telemetry_records(device_id: str, query: str, db_session: Session, limit: int = 50) -> List[TelemetrySnapshot]:
    """
    Parses a natural language query, maps keywords/qualifiers to database filters,
    and returns a list of TelemetrySnapshot records matching the conditions.
    """
    query_lower = query.lower().strip()
    filters = []

    # 1. Temperature / Thermal state
    if any(k in query_lower for k in ["temp", "temperature", "hot", "heat", "thermal", "overheat", "throttle"]):
        if any(q in query_lower for q in ["high", "hot", "overheat", "critical", "serious"]):
            filters.append(
                or_(
                    ThermalMetrics.cpu_temperature >= 75.0,
                    ThermalMetrics.thermal_state.in_(["serious", "critical"])
                )
            )
        elif any(q in query_lower for q in ["low", "cool", "cold", "normal", "healthy"]):
            filters.append(ThermalMetrics.cpu_temperature <= 60.0)

    # 2. Battery
    if "battery" in query_lower or "power" in query_lower or "charge" in query_lower:
        if any(q in query_lower for q in ["low", "empty", "critical"]):
            filters.append(BatteryMetrics.battery_level <= 20.0)
        if any(q in query_lower for q in ["drain", "draining", "discharging", "discharge", "unplugged", "on battery"]):
            filters.append(PowerMetrics.power_source == "battery")
        elif any(q in query_lower for q in ["charging", "plugged", "ac", "power source"]):
            # Avoid matching just "power" queries unless AC-specific is asked
            if "ac" in query_lower or "charging" in query_lower or "plugged" in query_lower:
                filters.append(PowerMetrics.power_source == "ac")
        if any(q in query_lower for q in ["degraded", "poor", "bad", "health"]):
            # Check if health query specifies bad status
            if any(h in query_lower for h in ["poor", "bad", "degraded", "low"]):
                filters.append(BatteryMetrics.battery_health <= 80.0)

    # 3. CPU
    if "cpu" in query_lower or "processor" in query_lower or "cores" in query_lower or "load" in query_lower:
        # Avoid false positives on "load" matching GPU/Memory unless CPU is mentioned or implied
        if "cpu" in query_lower or "processor" in query_lower or "cores" in query_lower:
            if any(q in query_lower for q in ["high", "heavy", "elevated", "load", "spike"]):
                filters.append(CPUMetrics.cpu_usage >= 75.0)
            elif any(q in query_lower for q in ["low", "idle", "cool", "quiet"]):
                filters.append(CPUMetrics.cpu_usage <= 20.0)

    # 4. GPU
    if "gpu" in query_lower or "graphics" in query_lower or "vram" in query_lower:
        if any(q in query_lower for q in ["high", "heavy", "elevated", "load"]):
            filters.append(GPUMetrics.gpu_usage >= 75.0)
        elif any(q in query_lower for q in ["low", "idle"]):
            filters.append(GPUMetrics.gpu_usage <= 15.0)

    # 5. Memory
    if "memory" in query_lower or "ram" in query_lower:
        if any(q in query_lower for q in ["high", "full", "pressure", "elevated"]):
            filters.append(MemoryMetrics.memory_usage >= 75.0)
        elif any(q in query_lower for q in ["low", "free", "comfortable"]):
            filters.append(MemoryMetrics.memory_usage <= 35.0)

    # 6. Disk / Storage
    if "disk" in query_lower or "storage" in query_lower or "space" in query_lower or "drive" in query_lower:
        if any(q in query_lower for q in ["high", "full", "low space", "warning", "critical"]):
            filters.append(DiskMetrics.disk_usage >= 80.0)
        elif any(q in query_lower for q in ["low", "empty", "free"]):
            filters.append(DiskMetrics.disk_usage <= 40.0)

    # 7. WiFi / Network
    if any(k in query_lower for k in ["wifi", "network", "signal", "ssid", "connection"]):
        if any(q in query_lower for q in ["low", "weak", "poor", "unstable", "bad"]):
            filters.append(WiFiMetrics.signal_strength_dbm < -70)
        elif any(q in query_lower for q in ["strong", "excellent", "good"]):
            filters.append(WiFiMetrics.signal_strength_dbm >= -55)

    # 8. Health Category / Score
    if "health" in query_lower or "score" in query_lower or "status" in query_lower:
        if any(q in query_lower for q in ["critical", "bad", "poor", "low"]):
            filters.append(TelemetrySnapshot.health_score < 50.0)
        elif "warning" in query_lower:
            filters.append(TelemetrySnapshot.health_category == "Warning")
        elif any(q in query_lower for q in ["healthy", "good", "excellent"]):
            filters.append(TelemetrySnapshot.health_category == "Healthy")

    # Combine filters based on user request style
    # If " or " is in the query, combine filters with OR; otherwise default to AND.
    use_or = " or " in query_lower
    
    sqlalchemy_filter = None
    if filters:
        if use_or:
            sqlalchemy_filter = or_(*filters)
        else:
            sqlalchemy_filter = and_(*filters)

    # Build DB Query
    db_query = (
        db_session.query(TelemetrySnapshot)
        .join(TelemetrySnapshot.cpu)
        .join(TelemetrySnapshot.gpu)
        .join(TelemetrySnapshot.memory)
        .join(TelemetrySnapshot.battery)
        .join(TelemetrySnapshot.disk)
        .join(TelemetrySnapshot.wifi)
        .join(TelemetrySnapshot.thermal)
        .join(TelemetrySnapshot.power)
        .options(
            joinedload(TelemetrySnapshot.cpu),
            joinedload(TelemetrySnapshot.gpu),
            joinedload(TelemetrySnapshot.memory),
            joinedload(TelemetrySnapshot.battery),
            joinedload(TelemetrySnapshot.disk),
            joinedload(TelemetrySnapshot.wifi),
            joinedload(TelemetrySnapshot.thermal),
            joinedload(TelemetrySnapshot.power)
        )
        .filter(TelemetrySnapshot.device_id == device_id)
    )

    if sqlalchemy_filter is not None:
        db_query = db_query.filter(sqlalchemy_filter)

    # Sort and return matching results
    return db_query.order_by(TelemetrySnapshot.timestamp.desc()).limit(limit).all()
