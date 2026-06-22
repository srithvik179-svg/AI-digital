"""
Phase 47 — Multi-Device Fleet Management API.

Provides a unified view across all registered devices:

  GET  /fleet/summary               — fleet-level KPI aggregates
  GET  /fleet/devices               — per-device health cards (sorted by score)
  GET  /fleet/device/{device_id}    — deep single-device profile
  GET  /fleet/ranking               — health score ranking across all devices
  GET  /fleet/anomalies             — devices with active alerts or critical scores
  POST /fleet/bulk-action           — apply a copilot action to one or all devices
  GET  /fleet/comparison            — side-by-side metric comparison for N devices

All data is assembled from:
  1. The in-memory agent registry (Phase 46 live-stream)
  2. PostgreSQL TelemetrySnapshot (last N readings per device)
  3. The health score engine (Phase 5)
  4. The alert engine (Phase 6)

Responses are optimised for the Fleet Dashboard frontend component.
"""

from __future__ import annotations

import socket
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from pydantic import BaseModel

from app.core.database import get_db
from app.core.logging import logger
from app.models.telemetry import (
    TelemetrySnapshot, CPUMetrics, MemoryMetrics,
    ThermalMetrics, BatteryMetrics, DiskMetrics,
    WiFiMetrics, GPUMetrics, PowerMetrics,
)
from app.services.health_score import compute_health_score
from app.services.alert_engine import evaluate_alerts
from app.api.v1.live_stream import _agent_registry

router = APIRouter()

# ─────────────────────────────────────────────────────────────────────────────
# Pydantic response schemas
# ─────────────────────────────────────────────────────────────────────────────

class DeviceHealthCard(BaseModel):
    device_id:        str
    source:           str           # 'mac' | 'windows-ohm' | 'linux' | …
    online:           bool
    last_seen:        Optional[str]
    age_seconds:      float
    ticks_received:   int

    # Latest telemetry snapshot
    cpu_usage:        Optional[float]
    memory_usage:     Optional[float]
    cpu_temperature:  Optional[float]
    battery_level:    Optional[float]
    battery_health:   Optional[float]
    power_source:     Optional[str]
    fan_speed:        Optional[int]
    gpu_usage:        Optional[float]
    signal_strength_dbm: Optional[int]

    # Computed scores
    health_score:     Optional[float]
    health_category:  Optional[str]
    active_alert_count: int
    recommendations:  List[str]


class FleetSummary(BaseModel):
    total_devices:    int
    online_devices:   int
    offline_devices:  int
    fleet_avg_health: Optional[float]
    fleet_min_health: Optional[float]
    healthy_count:    int
    warning_count:    int
    critical_count:   int
    total_alerts:     int
    sources:          Dict[str, int]   # { 'mac': 2, 'windows-ohm': 1 }
    generated_at:     str


class FleetRanking(BaseModel):
    rank:          int
    device_id:     str
    health_score:  float
    health_category: str
    online:        bool
    source:        str


class FleetAnomaly(BaseModel):
    device_id:    str
    reason:       str
    severity:     str           # 'critical' | 'warning'
    metric:       str
    value:        Optional[float]
    threshold:    Optional[float]


class BulkActionRequest(BaseModel):
    action:     str              # 'ECO_MODE' | 'KILL_HIGH_CPU' | 'DISABLE_ECO_MODE'
    device_ids: Optional[List[str]] = None   # None = all online devices


class ComparisonRequest(BaseModel):
    device_ids: List[str]


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

_ONLINE_THRESHOLD_SEC = 30.0


def _is_online(agent) -> bool:
    age = (datetime.utcnow() - agent.last_heartbeat).total_seconds()
    return age <= _ONLINE_THRESHOLD_SEC


def _latest_snapshot(db: Session, device_id: str) -> Optional[TelemetrySnapshot]:
    return (
        db.query(TelemetrySnapshot)
        .options(
            joinedload(TelemetrySnapshot.cpu),
            joinedload(TelemetrySnapshot.gpu),
            joinedload(TelemetrySnapshot.memory),
            joinedload(TelemetrySnapshot.battery),
            joinedload(TelemetrySnapshot.disk),
            joinedload(TelemetrySnapshot.wifi),
            joinedload(TelemetrySnapshot.thermal),
            joinedload(TelemetrySnapshot.power),
        )
        .filter(TelemetrySnapshot.device_id == device_id)
        .order_by(TelemetrySnapshot.timestamp.desc())
        .first()
    )


def _build_device_card(agent, snap: Optional[TelemetrySnapshot]) -> DeviceHealthCard:
    """Assembles a DeviceHealthCard from agent registry + DB snapshot."""
    online    = _is_online(agent)
    age       = (datetime.utcnow() - agent.last_heartbeat).total_seconds()
    last_seen = agent.last_heartbeat.isoformat()

    # Pull raw metrics from snapshot (or last payload)
    payload   = agent.last_payload or {}
    cpu_usage    = snap.cpu.cpu_usage    if snap and snap.cpu    else payload.get("cpu_usage")
    mem_usage    = snap.memory.memory_usage if snap and snap.memory else payload.get("memory_usage")
    cpu_temp     = snap.thermal.cpu_temperature if snap and snap.thermal else payload.get("cpu_temperature")
    bat_level    = snap.battery.battery_level   if snap and snap.battery else payload.get("battery_level")
    bat_health   = snap.battery.battery_health  if snap and snap.battery else payload.get("battery_health")
    power_src    = snap.power.power_source       if snap and snap.power   else payload.get("power_source", "unknown")
    fan          = snap.thermal.fan_speed_rpm    if snap and snap.thermal else payload.get("fan_speed")
    gpu_usage    = snap.gpu.gpu_usage            if snap and snap.gpu     else payload.get("gpu_usage")
    wifi_dbm     = snap.wifi.signal_strength_dbm if snap and snap.wifi    else payload.get("signal_strength_dbm")
    disk_usage   = snap.disk.disk_usage          if snap and snap.disk    else payload.get("disk_usage", 0.0)

    # Compute health score
    hs = None
    alerts_list = []
    recs: List[str] = []
    if cpu_usage is not None and mem_usage is not None:
        try:
            hs = compute_health_score(
                cpu_usage         = cpu_usage,
                memory_usage      = mem_usage,
                disk_usage        = disk_usage or 0.0,
                cpu_temperature   = cpu_temp or 45.0,
                battery_level     = bat_level or 100.0,
                battery_health    = bat_health or 95.0,
                gpu_usage         = gpu_usage,
                signal_strength_dbm = wifi_dbm,
                power_source      = power_src or "ac",
            )
            recs = hs.recommendations
        except Exception as e:
            logger.debug(f"Health score error for {agent.device_id}: {e}")

    # Evaluate alerts
    try:
        alerts_list = evaluate_alerts(
            cpu_temperature     = cpu_temp or 45.0,
            battery_level       = bat_level or 100.0,
            battery_health      = bat_health or 95.0,
            disk_usage          = disk_usage or 0.0,
            gpu_temperature     = None,
            battery_temperature = None,
            cycle_count         = None,
            write_bytes_sec     = None,
            signal_strength_dbm = wifi_dbm,
            link_speed_mbps     = None,
            thermal_state       = "nominal",
            power_source        = power_src or "ac",
            device_id           = agent.device_id,
        )
    except Exception:
        pass

    return DeviceHealthCard(
        device_id          = agent.device_id,
        source             = agent.source,
        online             = online,
        last_seen          = last_seen,
        age_seconds        = round(age, 1),
        ticks_received     = agent.ticks_received,
        cpu_usage          = round(cpu_usage, 1)   if cpu_usage    is not None else None,
        memory_usage       = round(mem_usage, 1)   if mem_usage    is not None else None,
        cpu_temperature    = round(cpu_temp, 1)    if cpu_temp     is not None else None,
        battery_level      = round(bat_level, 1)   if bat_level    is not None else None,
        battery_health     = round(bat_health, 1)  if bat_health   is not None else None,
        power_source       = power_src,
        fan_speed          = int(fan) if fan else None,
        gpu_usage          = round(gpu_usage, 1)   if gpu_usage    is not None else None,
        signal_strength_dbm= int(wifi_dbm) if wifi_dbm is not None else None,
        health_score       = round(hs.score, 1) if hs else None,
        health_category    = hs.category if hs else None,
        active_alert_count = len(alerts_list),
        recommendations    = recs,
    )


def _send_command(host: str, port: int, command: str, timeout: float = 2.0) -> bool:
    """Send a TCP command to an agent's command socket. Returns True on ACK."""
    try:
        with socket.create_connection((host, port), timeout=timeout) as s:
            s.sendall(command.encode())
            ack = s.recv(16)
            return ack == b"ACK"
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/summary", response_model=FleetSummary, summary="Fleet-wide health KPIs")
def fleet_summary(db: Session = Depends(get_db)) -> FleetSummary:
    """
    Returns aggregated fleet-level health metrics across all registered agents.
    Combines live agent registry with latest DB snapshots.
    """
    cards = []
    sources: Dict[str, int] = {}

    for agent in _agent_registry.values():
        snap = _latest_snapshot(db, agent.device_id)
        card = _build_device_card(agent, snap)
        cards.append(card)
        sources[agent.source] = sources.get(agent.source, 0) + 1

    scores    = [c.health_score for c in cards if c.health_score is not None]
    online    = sum(1 for c in cards if c.online)
    healthy   = sum(1 for c in cards if c.health_category == "Healthy")
    warning   = sum(1 for c in cards if c.health_category == "Warning")
    critical  = sum(1 for c in cards if c.health_category == "Critical")
    tot_alerts= sum(c.active_alert_count for c in cards)

    return FleetSummary(
        total_devices    = len(cards),
        online_devices   = online,
        offline_devices  = len(cards) - online,
        fleet_avg_health = round(sum(scores) / len(scores), 1) if scores else None,
        fleet_min_health = round(min(scores), 1) if scores else None,
        healthy_count    = healthy,
        warning_count    = warning,
        critical_count   = critical,
        total_alerts     = tot_alerts,
        sources          = sources,
        generated_at     = datetime.utcnow().isoformat(),
    )


@router.get("/devices", response_model=List[DeviceHealthCard], summary="All device health cards")
def fleet_devices(
    online_only: bool = Query(False, description="Return only currently active devices"),
    sort_by:     str  = Query("health_score", description="Sort key: health_score | cpu_usage | ticks"),
    db: Session = Depends(get_db),
) -> List[DeviceHealthCard]:
    """
    Returns a health card for every registered device.
    Cards include computed health score, alert count, and recommendations.
    """
    cards = []
    for agent in _agent_registry.values():
        snap = _latest_snapshot(db, agent.device_id)
        card = _build_device_card(agent, snap)
        if online_only and not card.online:
            continue
        cards.append(card)

    # Sort
    if sort_by == "health_score":
        cards.sort(key=lambda c: c.health_score or 0.0)  # worst first
    elif sort_by == "cpu_usage":
        cards.sort(key=lambda c: c.cpu_usage or 0.0, reverse=True)
    elif sort_by == "ticks":
        cards.sort(key=lambda c: c.ticks_received, reverse=True)

    return cards


@router.get("/device/{device_id}", response_model=DeviceHealthCard, summary="Single device deep profile")
def fleet_device_profile(device_id: str, db: Session = Depends(get_db)) -> DeviceHealthCard:
    """Returns the full health card for a single device."""
    agent = _agent_registry.get(device_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Device '{device_id}' not registered")
    snap = _latest_snapshot(db, device_id)
    return _build_device_card(agent, snap)


@router.get("/ranking", response_model=List[FleetRanking], summary="Health score ranking across all devices")
def fleet_ranking(db: Session = Depends(get_db)) -> List[FleetRanking]:
    """
    Returns all devices ranked by health score (worst first).
    Useful for identifying the most at-risk machines in the fleet.
    """
    ranks = []
    for agent in _agent_registry.values():
        snap = _latest_snapshot(db, agent.device_id)
        card = _build_device_card(agent, snap)
        ranks.append(FleetRanking(
            rank           = 0,     # filled below
            device_id      = card.device_id,
            health_score   = card.health_score or 0.0,
            health_category= card.health_category or "Unknown",
            online         = card.online,
            source         = card.source,
        ))

    ranks.sort(key=lambda r: r.health_score)   # worst first
    for i, r in enumerate(ranks):
        r.rank = i + 1

    return ranks


@router.get("/anomalies", response_model=List[FleetAnomaly], summary="Devices with critical health or active alerts")
def fleet_anomalies(db: Session = Depends(get_db)) -> List[FleetAnomaly]:
    """
    Scans all registered devices and returns anomaly entries for any device
    whose health score is Critical or whose latest readings breach thresholds.
    """
    anomalies: List[FleetAnomaly] = []

    for agent in _agent_registry.values():
        snap = _latest_snapshot(db, agent.device_id)
        card = _build_device_card(agent, snap)

        payload = agent.last_payload or {}
        cpu_temp  = card.cpu_temperature or 0.0
        bat_level = card.battery_level   or 100.0
        cpu_usage = card.cpu_usage       or 0.0
        mem_usage = card.memory_usage    or 0.0

        if card.health_category == "Critical":
            anomalies.append(FleetAnomaly(
                device_id = agent.device_id,
                reason    = f"Health score critically low ({card.health_score:.1f})",
                severity  = "critical",
                metric    = "health_score",
                value     = card.health_score,
                threshold = 50.0,
            ))

        if cpu_temp > 85.0:
            anomalies.append(FleetAnomaly(
                device_id = agent.device_id,
                reason    = f"CPU temperature dangerously high ({cpu_temp:.1f}°C)",
                severity  = "critical",
                metric    = "cpu_temperature",
                value     = cpu_temp,
                threshold = 85.0,
            ))

        if bat_level < 10.0:
            anomalies.append(FleetAnomaly(
                device_id = agent.device_id,
                reason    = f"Battery critically low ({bat_level:.1f}%)",
                severity  = "critical",
                metric    = "battery_level",
                value     = bat_level,
                threshold = 10.0,
            ))

        if cpu_usage > 90.0:
            anomalies.append(FleetAnomaly(
                device_id = agent.device_id,
                reason    = f"CPU overloaded ({cpu_usage:.1f}%)",
                severity  = "warning",
                metric    = "cpu_usage",
                value     = cpu_usage,
                threshold = 90.0,
            ))

        if mem_usage > 90.0:
            anomalies.append(FleetAnomaly(
                device_id = agent.device_id,
                reason    = f"Memory pressure high ({mem_usage:.1f}%)",
                severity  = "warning",
                metric    = "memory_usage",
                value     = mem_usage,
                threshold = 90.0,
            ))

        if not card.online:
            anomalies.append(FleetAnomaly(
                device_id = agent.device_id,
                reason    = f"Device offline for {card.age_seconds:.0f}s",
                severity  = "warning",
                metric    = "connectivity",
                value     = card.age_seconds,
                threshold = _ONLINE_THRESHOLD_SEC,
            ))

    anomalies.sort(key=lambda a: 0 if a.severity == "critical" else 1)
    return anomalies


@router.post("/bulk-action", summary="Apply a copilot action to one or all devices")
def fleet_bulk_action(body: BulkActionRequest) -> dict:
    """
    Sends a TCP command (ECO_MODE, KILL_HIGH_CPU, etc.) to the command socket
    of one or all registered online agents.

    Each agent runs a TCP listener on port 9090 (Phase 46 telemetry_agent.py).
    The action is sent as a raw text command; the agent responds with ACK.
    """
    ALLOWED = {"ECO_MODE", "KILL_HIGH_CPU", "DISABLE_ECO_MODE"}
    if body.action not in ALLOWED:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown action '{body.action}'. Allowed: {ALLOWED}",
        )

    targets = body.device_ids or [
        a.device_id for a in _agent_registry.values() if _is_online(a)
    ]

    results = {}
    for device_id in targets:
        agent = _agent_registry.get(device_id)
        if not agent:
            results[device_id] = "not_registered"
            continue
        if not _is_online(agent):
            results[device_id] = "offline"
            continue
        # Agent command socket runs on the host — use localhost for same-machine
        # or agent IP if available from last_payload
        host = "localhost"
        ok = _send_command(host, 9090, body.action)
        results[device_id] = "ack" if ok else "no_response"

    return {
        "action":  body.action,
        "results": results,
        "sent_at": datetime.utcnow().isoformat(),
    }


@router.get("/comparison", summary="Side-by-side metric comparison for multiple devices")
def fleet_comparison(
    device_ids: str = Query(..., description="Comma-separated device IDs"),
    db: Session = Depends(get_db),
) -> dict:
    """
    Returns a comparison table of key metrics for the requested devices.
    Useful for spotting outliers in a fleet of similar hardware.
    """
    ids = [d.strip() for d in device_ids.split(",") if d.strip()]
    if not ids:
        raise HTTPException(status_code=400, detail="device_ids must not be empty")
    if len(ids) > 20:
        raise HTTPException(status_code=400, detail="Maximum 20 devices per comparison")

    rows = []
    for device_id in ids:
        agent = _agent_registry.get(device_id)
        if not agent:
            rows.append({"device_id": device_id, "error": "not_registered"})
            continue
        snap = _latest_snapshot(db, device_id)
        card = _build_device_card(agent, snap)
        rows.append({
            "device_id":         card.device_id,
            "source":            card.source,
            "online":            card.online,
            "health_score":      card.health_score,
            "health_category":   card.health_category,
            "cpu_usage":         card.cpu_usage,
            "memory_usage":      card.memory_usage,
            "cpu_temperature":   card.cpu_temperature,
            "battery_level":     card.battery_level,
            "battery_health":    card.battery_health,
            "power_source":      card.power_source,
            "gpu_usage":         card.gpu_usage,
            "signal_strength_dbm": card.signal_strength_dbm,
            "active_alert_count":card.active_alert_count,
        })

    metrics = [
        "health_score", "cpu_usage", "memory_usage", "cpu_temperature",
        "battery_level", "battery_health", "gpu_usage",
    ]
    fleet_max = {
        m: max((r.get(m) or 0 for r in rows if isinstance(r.get(m), (int, float))), default=None)
        for m in metrics
    }
    fleet_min = {
        m: min((r.get(m) or 100 for r in rows if isinstance(r.get(m), (int, float))), default=None)
        for m in metrics
    }

    return {
        "devices":    rows,
        "fleet_max":  fleet_max,
        "fleet_min":  fleet_min,
        "generated_at": datetime.utcnow().isoformat(),
    }
