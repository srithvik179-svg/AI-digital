"""
Phase 46 — Live Ingestion Status & SSE Stream API.

Exposes endpoints for monitoring the live telemetry ingestion pipeline:

  GET  /live-stream/status        — pipeline health (last seen, tick rate, sources)
  GET  /live-stream/sse           — Server-Sent Event stream of raw telemetry ticks
  POST /live-stream/register      — agent self-registration (heartbeat)
  GET  /live-stream/devices       — all registered active agents
  POST /live-stream/disconnect    — agent graceful de-registration

The SSE endpoint proxies the stream from the WebSocket broadcast manager
so the same data that flows to the dashboard can also be consumed by any
HTTP client (browser EventSource, curl, etc.) without needing WebSocket.
"""

from __future__ import annotations

import json
import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, AsyncGenerator

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter()

# ─────────────────────────────────────────────────────────────────────────────
# In-memory agent registry
# ─────────────────────────────────────────────────────────────────────────────

class _AgentInfo(BaseModel):
    device_id:   str
    source:      str          # 'mac' | 'windows-ohm' | 'windows-wmi' | 'linux'
    api_version: str = "1"
    registered_at: datetime = datetime.utcnow()
    last_heartbeat: datetime = datetime.utcnow()
    ticks_received: int = 0
    last_payload:   Optional[Dict[str, Any]] = None


# Global registry: device_id → _AgentInfo
_agent_registry: Dict[str, _AgentInfo] = {}

# Global SSE subscriber queues
_sse_queues: list[asyncio.Queue] = []
_sse_queues_lock = asyncio.Lock()

# ─────────────────────────────────────────────────────────────────────────────
# Pydantic schemas
# ─────────────────────────────────────────────────────────────────────────────

class AgentRegistrationRequest(BaseModel):
    device_id:   str
    source:      str
    api_version: str = "1"


class AgentRegistrationResponse(BaseModel):
    status:    str
    device_id: str
    message:   str


class AgentHeartbeatRequest(BaseModel):
    device_id: str
    payload:   Optional[Dict[str, Any]] = None


class PipelineStatusResponse(BaseModel):
    total_agents:       int
    active_agents:      int
    inactive_agents:    int
    agents:             list


# ─────────────────────────────────────────────────────────────────────────────
# SSE queue management (called from telemetry.py WebSocket broadcaster)
# ─────────────────────────────────────────────────────────────────────────────

async def push_to_sse_queues(payload: Dict[str, Any]) -> None:
    """
    Called by the telemetry ingestion endpoint after a successful POST
    to fan out the payload to all SSE subscribers.
    """
    async with _sse_queues_lock:
        dead = []
        for q in _sse_queues:
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            _sse_queues.remove(q)


def update_agent_registry(payload: Dict[str, Any]) -> None:
    """
    Synchronous update called from `create_telemetry` in telemetry.py
    to track per-agent heartbeat and tick count.
    """
    device_id = payload.get("device_id", "unknown")
    if device_id in _agent_registry:
        _agent_registry[device_id].last_heartbeat = datetime.utcnow()
        _agent_registry[device_id].ticks_received += 1
        _agent_registry[device_id].last_payload = payload
    else:
        # Auto-register on first telemetry post
        source = payload.get("metadata_info", {}) or {}
        _agent_registry[device_id] = _AgentInfo(
            device_id=device_id,
            source=source.get("source", "unknown"),
        )
        _agent_registry[device_id].ticks_received = 1
        _agent_registry[device_id].last_payload = payload


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/register",
    response_model=AgentRegistrationResponse,
    summary="Register a new telemetry agent",
)
def register_agent(body: AgentRegistrationRequest) -> AgentRegistrationResponse:
    """
    Called by the telemetry agent on startup to self-register.
    Subsequent telemetry POSTs update the heartbeat automatically.
    """
    existing = _agent_registry.get(body.device_id)
    if existing:
        existing.last_heartbeat = datetime.utcnow()
        existing.source = body.source
        msg = f"Agent '{body.device_id}' reconnected (source: {body.source})"
    else:
        _agent_registry[body.device_id] = _AgentInfo(
            device_id   = body.device_id,
            source      = body.source,
            api_version = body.api_version,
        )
        msg = f"Agent '{body.device_id}' registered (source: {body.source})"

    return AgentRegistrationResponse(
        status    = "ok",
        device_id = body.device_id,
        message   = msg,
    )


@router.post("/heartbeat", summary="Agent heartbeat + optional payload update")
def agent_heartbeat(body: AgentHeartbeatRequest):
    """
    Lightweight heartbeat endpoint.  The agent can POST this instead of
    a full telemetry payload to signal that it is alive.
    """
    if body.device_id not in _agent_registry:
        raise HTTPException(status_code=404, detail=f"Unknown device: {body.device_id}. Register first.")
    agent = _agent_registry[body.device_id]
    agent.last_heartbeat = datetime.utcnow()
    if body.payload:
        agent.last_payload = body.payload
        agent.ticks_received += 1
    return {"status": "ok", "device_id": body.device_id}


@router.post("/disconnect", summary="Agent graceful de-registration")
def disconnect_agent(device_id: str):
    """Removes an agent from the registry on clean shutdown."""
    if device_id in _agent_registry:
        del _agent_registry[device_id]
    return {"status": "disconnected", "device_id": device_id}


@router.get(
    "/status",
    response_model=PipelineStatusResponse,
    summary="Live ingestion pipeline health",
)
def pipeline_status() -> PipelineStatusResponse:
    """
    Returns health information for all registered agents.
    An agent is considered 'active' if it sent a heartbeat within the last 30 s.
    """
    now = datetime.utcnow()
    threshold = timedelta(seconds=30)

    agent_list = []
    active   = 0
    inactive = 0

    for info in _agent_registry.values():
        age_sec = (now - info.last_heartbeat).total_seconds()
        is_active = age_sec <= threshold.total_seconds()
        if is_active:
            active += 1
        else:
            inactive += 1

        agent_list.append({
            "device_id":     info.device_id,
            "source":        info.source,
            "active":        is_active,
            "ticks_received":info.ticks_received,
            "last_heartbeat": info.last_heartbeat.isoformat(),
            "age_seconds":   round(age_sec, 1),
            "registered_at": info.registered_at.isoformat(),
        })

    return PipelineStatusResponse(
        total_agents   = len(agent_list),
        active_agents  = active,
        inactive_agents= inactive,
        agents         = agent_list,
    )


@router.get("/devices", summary="List all registered telemetry agent devices")
def list_devices():
    """Returns a compact list of all registered device IDs and their sources."""
    return [
        {"device_id": v.device_id, "source": v.source, "ticks": v.ticks_received}
        for v in _agent_registry.values()
    ]


@router.get(
    "/sse",
    summary="Server-Sent Event stream of live telemetry ticks",
    description=(
        "Subscribe to this endpoint with EventSource to receive a real-time "
        "stream of telemetry JSON objects as they are ingested. "
        "Each event has type 'telemetry_tick'. "
        "Compatible with browser EventSource API and curl."
    ),
)
async def sse_stream(request: Request):
    """
    Returns a streaming HTTP response with Content-Type: text/event-stream.
    Each telemetry tick POSTed to /telemetry/ is forwarded here within ~10 ms.
    """
    queue: asyncio.Queue = asyncio.Queue(maxsize=120)

    async with _sse_queues_lock:
        _sse_queues.append(queue)

    async def event_generator() -> AsyncGenerator[str, None]:
        # Send connection acknowledgement
        yield "event: connected\ndata: {\"status\":\"streaming\"}\n\n"
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=25.0)
                    payload_str = json.dumps(payload, default=str)
                    yield f"event: telemetry_tick\ndata: {payload_str}\n\n"
                except asyncio.TimeoutError:
                    # Keep-alive comment
                    yield ": keep-alive\n\n"
        except Exception:
            pass
        finally:
            async with _sse_queues_lock:
                if queue in _sse_queues:
                    _sse_queues.remove(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":               "no-cache",
            "X-Accel-Buffering":           "no",
            "Access-Control-Allow-Origin": "*",
        },
    )
