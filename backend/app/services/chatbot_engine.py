"""
Rule-Based Telemetry Chatbot Engine — Phase 8
Retrieves the latest telemetry snapshot from PostgreSQL database and provides template-based status answers.
Strictly answers from telemetry data. Zero LLM.
"""

from __future__ import annotations
import time
from typing import Dict, Any, List
from sqlalchemy.orm import Session, joinedload
from app.models.telemetry import TelemetrySnapshot
from datetime import datetime

# Intent Keywords
INTENTS = {
    "cpu": ["cpu", "processor", "load", "utilization", "cores", "process", "processes", "frequency", "mhz", "speed"],
    "gpu": ["gpu", "graphics", "card", "video", "vram", "gpu_usage", "gpu_temp"],
    "battery": ["battery", "charge", "power", "capacity", "plugged", "ac", "cycle", "cycles", "health", "drain"],
    "disk": ["disk", "storage", "drive", "space", "hdd", "ssd", "io", "write", "read", "bytes"]
}

def generate_chatbot_response(device_id: str, query: str, db_session: Session) -> Dict[str, Any]:
    """
    Analyzes the query for telemetry intents, fetches latest snapshot from database,
    and returns a structured response matching the telemetry stats.
    """
    t0 = time.perf_counter()
    query_lower = query.lower().strip()
    
    # Intent mapping by keyword matching
    matched_intents = []
    for intent, keywords in INTENTS.items():
        if any(kw in query_lower for kw in keywords):
            matched_intents.append(intent)
            
    # If no intent keywords matched, we return the fallback explanation of capabilities
    if not matched_intents:
        elapsed_ms = (time.perf_counter() - t0) * 1000
        return {
            "query": query,
            "response": "I can only answer questions related to your device's telemetry data (CPU, GPU, battery, and disk status) using real-time snapshots. Please ask me about one of these capabilities.",
            "source_documents": [],
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        
    # Retrieve the latest telemetry snapshot
    snapshot = (
        db_session.query(TelemetrySnapshot)
        .options(
            joinedload(TelemetrySnapshot.cpu),
            joinedload(TelemetrySnapshot.gpu),
            joinedload(TelemetrySnapshot.battery),
            joinedload(TelemetrySnapshot.disk),
            joinedload(TelemetrySnapshot.power),
            joinedload(TelemetrySnapshot.thermal)
        )
        .filter(TelemetrySnapshot.device_id == device_id)
        .order_by(TelemetrySnapshot.timestamp.desc())
        .first()
    )
    
    if not snapshot:
        return {
            "query": query,
            "response": f"I couldn't find any telemetry data for device '{device_id}'. Please ensure the device is active and streaming telemetry data.",
            "source_documents": [],
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        
    responses = []
    source_parts = []
    
    # 1. CPU status
    if "cpu" in matched_intents:
        cpu_usage = snapshot.cpu.cpu_usage if (snapshot.cpu and snapshot.cpu.cpu_usage is not None) else 0.0
        active_processes = snapshot.cpu.active_process_count if (snapshot.cpu and snapshot.cpu.active_process_count is not None) else 0
        frequency = snapshot.cpu.cpu_frequency_mhz if (snapshot.cpu and snapshot.cpu.cpu_frequency_mhz is not None) else None
        
        freq_str = f" running at {frequency:.0f} MHz" if frequency else ""
        cpu_str = f"CPU Status: Utilization is {cpu_usage:.1f}% with {active_processes} active processes{freq_str}."
        if cpu_usage > 85:
            cpu_str += " The CPU is highly utilized, which might cause sluggishness or increased heat."
        elif cpu_usage > 50:
            cpu_str += " The CPU is under moderate load."
        else:
            cpu_str += " The CPU is running cool and idle."
        responses.append(cpu_str)
        source_parts.append(f"CPU={cpu_usage:.1f}% (Processes: {active_processes})")
        
    # 2. GPU status
    if "gpu" in matched_intents:
        gpu_usage = snapshot.gpu.gpu_usage if (snapshot.gpu and snapshot.gpu.gpu_usage is not None) else 0.0
        gpu_temp = snapshot.gpu.gpu_temperature if (snapshot.gpu and snapshot.gpu.gpu_temperature is not None) else None
        gpu_mem = snapshot.gpu.gpu_memory_usage if (snapshot.gpu and snapshot.gpu.gpu_memory_usage is not None) else None
        
        temp_str = f", temperature is {gpu_temp:.1f}°C" if gpu_temp is not None else ""
        mem_str = f", and VRAM usage is {gpu_mem:.1f}%" if gpu_mem is not None else ""
        gpu_str = f"GPU Status: Utilization is {gpu_usage:.1f}%{temp_str}{mem_str}."
        if gpu_usage > 80:
            gpu_str += " The GPU is heavily loaded."
        else:
            gpu_str += " The GPU load is normal."
        responses.append(gpu_str)
        source_parts.append(f"GPU={gpu_usage:.1f}% (Temp: {gpu_temp}°C)")
        
    # 3. Battery status
    if "battery" in matched_intents:
        level = snapshot.battery.battery_level if (snapshot.battery and snapshot.battery.battery_level is not None) else 0.0
        health = snapshot.battery.battery_health if (snapshot.battery and snapshot.battery.battery_health is not None) else 100.0
        temp = snapshot.battery.battery_temperature if (snapshot.battery and snapshot.battery.battery_temperature is not None) else None
        cycles = snapshot.battery.cycle_count if (snapshot.battery and snapshot.battery.cycle_count is not None) else 0
        power_src = snapshot.power.power_source if (snapshot.power and snapshot.power.power_source is not None) else "ac"
        
        temp_str = f", temperature is {temp:.1f}°C" if temp is not None else ""
        bat_str = f"Battery Status: Charge level is {level:.1f}% (health: {health:.1f}%) with {cycles} cycles. Power source: {power_src.upper()}{temp_str}."
        if power_src == "battery" and level < 20:
            bat_str += " Battery is low. Recommend connecting to power source."
        elif health < 80:
            bat_str += " Battery health has degraded below 80%. Consider service replacement."
        else:
            bat_str += " Battery is in healthy condition."
        responses.append(bat_str)
        source_parts.append(f"Battery={level:.1f}% (Health: {health:.1f}%, Power: {power_src})")
        
    # 4. Disk status
    if "disk" in matched_intents:
        usage = snapshot.disk.disk_usage if (snapshot.disk and snapshot.disk.disk_usage is not None) else 0.0
        read_b = snapshot.disk.read_bytes_sec if (snapshot.disk and snapshot.disk.read_bytes_sec is not None) else 0
        write_b = snapshot.disk.write_bytes_sec if (snapshot.disk and snapshot.disk.write_bytes_sec is not None) else 0
        
        disk_str = f"Disk Status: Space used is {usage:.1f}%. Current I/O activity: read {read_b / 1024 / 1024:.2f} MB/s, write {write_b / 1024 / 1024:.2f} MB/s."
        if usage > 90:
            disk_str += " Disk storage is critical (<10% free space). Please free up space immediately."
        elif usage > 75:
            disk_str += " Disk storage is elevated."
        else:
            disk_str += " Disk space is sufficient."
        responses.append(disk_str)
        source_parts.append(f"Disk={usage:.1f}% (Read/Write activity active)")
        
    elapsed_ms = (time.perf_counter() - t0) * 1000
    
    timestamp_str = snapshot.timestamp.isoformat() if hasattr(snapshot.timestamp, "isoformat") else str(snapshot.timestamp)
    source_docs = [f"At {timestamp_str}, device '{device_id}' reported: " + ", ".join(source_parts)]
    
    return {
        "query": query,
        "response": " ".join(responses),
        "source_documents": source_docs,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
