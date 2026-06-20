import csv
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
from sqlalchemy.orm import Session

from app.core.logging import logger
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

# Header mappings (Standard Key -> List of case-insensitive aliases)
HEADER_ALIASES: Dict[str, List[str]] = {
    "device_id": ["device_id", "device", "hostname", "deviceid", "client_id", "client"],
    "cpu_usage": ["cpu_usage", "cpu", "cpu%", "cpu_util", "cpu_utilization"],
    "memory_usage": ["memory_usage", "memory", "ram", "ram%", "memory_util", "mem_usage"],
    "disk_usage": ["disk_usage", "disk", "disk%", "storage", "storage_usage"],
    "cpu_temperature": ["cpu_temperature", "temperature", "temp", "cpu_temp", "core_temp", "thermals"],
    "battery_level": ["battery_level", "battery", "charge", "battery%", "charge_level"],
    "battery_health": ["battery_health", "health", "battery_health%", "bat_health"],
    "fan_speed": ["fan_speed", "fan", "fanspeed", "rpm", "fan_rpm"],
    "power_source": ["power_source", "power", "source", "ac_battery", "power_state"],
    "active_process_count": ["active_process_count", "processes", "process_count", "active_processes"],
    "timestamp": ["timestamp", "time", "date", "recorded_at"],
    
    # Extended metrics
    "cpu_frequency_mhz": ["cpu_frequency_mhz", "cpu_freq", "freq_mhz", "cpu_frequency"],
    "gpu_usage": ["gpu_usage", "gpu", "gpu%", "gpu_util", "gpu_utilization"],
    "gpu_temperature": ["gpu_temperature", "gpu_temp", "gpu_core_temp"],
    "gpu_memory_usage": ["gpu_memory_usage", "gpu_ram", "gpu_memory"],
    "battery_temperature": ["battery_temperature", "battery_temp", "bat_temp"],
    "cycle_count": ["cycle_count", "cycles", "battery_cycles"],
    "read_bytes_sec": ["read_bytes_sec", "read_bytes", "disk_read", "read_speed"],
    "write_bytes_sec": ["write_bytes_sec", "write_bytes", "disk_write", "write_speed"],
    "signal_strength_dbm": ["signal_strength_dbm", "wifi_signal", "signal_dbm", "dbm"],
    "ssid": ["ssid", "wifi_ssid", "network_name", "network"],
    "link_speed_mbps": ["link_speed_mbps", "link_speed", "wifi_speed", "wifi_link_speed"],
    "thermal_state": ["thermal_state", "thermal_status", "throttling", "thermal_level"],
    "power_draw_watts": ["power_draw_watts", "power_draw", "wattage", "watts"],
    "voltage_mv": ["voltage_mv", "voltage", "volts_mv"]
}

# Default values for missing fields
FIELD_DEFAULTS: Dict[str, Any] = {
    "device_id": "laptop-generic",
    "cpu_usage": 15.0,
    "memory_usage": 50.0,
    "disk_usage": 40.0,
    "cpu_temperature": 45.0,
    "battery_level": 100.0,
    "battery_health": 100.0,
    "fan_speed": 1200,
    "power_source": "ac",
    "active_process_count": 95,
    
    # Extended defaults
    "cpu_frequency_mhz": 2400.0,
    "gpu_usage": 0.0,
    "gpu_temperature": 40.0,
    "gpu_memory_usage": 0.0,
    "battery_temperature": 30.0,
    "cycle_count": 120,
    "read_bytes_sec": 0,
    "write_bytes_sec": 0,
    "signal_strength_dbm": -50,
    "ssid": "Dell_Secure_WiFi",
    "link_speed_mbps": 866,
    "thermal_state": "nominal",
    "power_draw_watts": 15.0,
    "voltage_mv": 12000.0
}

def resolve_headers(headers: List[str]) -> Dict[str, str]:
    """
    Map raw CSV headers to standard database column keys based on alias list.
    Returns a dict mapping standard_key -> raw_csv_header.
    """
    mapping: Dict[str, str] = {}
    normalized_headers = {h.strip().lower().replace(" ", "_"): h for h in headers}
    
    for std_key, aliases in HEADER_ALIASES.items():
        for alias in aliases:
            if alias in normalized_headers:
                mapping[std_key] = normalized_headers[alias]
                break
                
    return mapping

def parse_float(val: Any, default: float) -> float:
    if val is None or str(val).strip() == "":
        return default
    try:
        clean_val = str(val).replace("%", "").replace("°C", "").replace("C", "").strip()
        return float(clean_val)
    except ValueError:
        return default

def parse_int(val: Any, default: int) -> int:
    if val is None or str(val).strip() == "":
        return default
    try:
        clean_val = str(val).replace("RPM", "").replace("rpm", "").strip()
        return int(float(clean_val))
    except ValueError:
        return default

def parse_datetime(val: Any) -> datetime:
    if val is None or str(val).strip() == "":
        return datetime.utcnow()
    
    val_str = str(val).strip()
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
        "%m/%d/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
        "%Y/%m/%d %H:%M:%S"
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(val_str, fmt)
        except ValueError:
            continue
            
    try:
        return datetime.fromtimestamp(float(val_str))
    except ValueError:
        pass
        
    logger.warning(f"Could not parse date string '{val_str}'. Defaulting to current timestamp.")
    return datetime.utcnow()

def clean_and_validate_row(
    raw_row: Dict[str, Any], 
    header_mapping: Dict[str, str]
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Cleans a raw CSV row dictionary using resolved headers mapping.
    Performs type coercion and handles missing values.
    Returns (cleaned_row_dict, error_message).
    """
    cleaned: Dict[str, Any] = {}
    
    # 1. Device ID
    raw_device_header = header_mapping.get("device_id")
    device_id = raw_row.get(raw_device_header) if raw_device_header else None
    if not device_id or str(device_id).strip() == "":
        device_id = FIELD_DEFAULTS["device_id"]
    cleaned["device_id"] = str(device_id).strip()
    
    # 2. Timestamp
    raw_time_header = header_mapping.get("timestamp")
    timestamp_val = raw_row.get(raw_time_header) if raw_time_header else None
    cleaned["timestamp"] = parse_datetime(timestamp_val)
    
    # 3. Core numeric metrics
    cleaned["cpu_usage"] = parse_float(raw_row.get(header_mapping.get("cpu_usage")), FIELD_DEFAULTS["cpu_usage"])
    cleaned["memory_usage"] = parse_float(raw_row.get(header_mapping.get("memory_usage")), FIELD_DEFAULTS["memory_usage"])
    cleaned["disk_usage"] = parse_float(raw_row.get(header_mapping.get("disk_usage")), FIELD_DEFAULTS["disk_usage"])
    cleaned["cpu_temperature"] = parse_float(raw_row.get(header_mapping.get("cpu_temperature")), FIELD_DEFAULTS["cpu_temperature"])
    cleaned["battery_level"] = parse_float(raw_row.get(header_mapping.get("battery_level")), FIELD_DEFAULTS["battery_level"])
    cleaned["battery_health"] = parse_float(raw_row.get(header_mapping.get("battery_health")), FIELD_DEFAULTS["battery_health"])
    cleaned["fan_speed"] = parse_int(raw_row.get(header_mapping.get("fan_speed")), FIELD_DEFAULTS["fan_speed"])
    cleaned["active_process_count"] = parse_int(raw_row.get(header_mapping.get("active_process_count")), FIELD_DEFAULTS["active_process_count"])
    
    # Extended metrics
    cleaned["cpu_frequency_mhz"] = parse_float(raw_row.get(header_mapping.get("cpu_frequency_mhz")), FIELD_DEFAULTS["cpu_frequency_mhz"])
    cleaned["gpu_usage"] = parse_float(raw_row.get(header_mapping.get("gpu_usage")), FIELD_DEFAULTS["gpu_usage"])
    cleaned["gpu_temperature"] = parse_float(raw_row.get(header_mapping.get("gpu_temperature")), FIELD_DEFAULTS["gpu_temperature"])
    cleaned["gpu_memory_usage"] = parse_float(raw_row.get(header_mapping.get("gpu_memory_usage")), FIELD_DEFAULTS["gpu_memory_usage"])
    cleaned["battery_temperature"] = parse_float(raw_row.get(header_mapping.get("battery_temperature")), FIELD_DEFAULTS["battery_temperature"])
    cleaned["cycle_count"] = parse_int(raw_row.get(header_mapping.get("cycle_count")), FIELD_DEFAULTS["cycle_count"])
    cleaned["read_bytes_sec"] = parse_int(raw_row.get(header_mapping.get("read_bytes_sec")), FIELD_DEFAULTS["read_bytes_sec"])
    cleaned["write_bytes_sec"] = parse_int(raw_row.get(header_mapping.get("write_bytes_sec")), FIELD_DEFAULTS["write_bytes_sec"])
    cleaned["signal_strength_dbm"] = parse_int(raw_row.get(header_mapping.get("signal_strength_dbm")), FIELD_DEFAULTS["signal_strength_dbm"])
    cleaned["ssid"] = str(raw_row.get(header_mapping.get("ssid"), FIELD_DEFAULTS["ssid"])).strip()
    cleaned["link_speed_mbps"] = parse_int(raw_row.get(header_mapping.get("link_speed_mbps")), FIELD_DEFAULTS["link_speed_mbps"])
    cleaned["thermal_state"] = str(raw_row.get(header_mapping.get("thermal_state"), FIELD_DEFAULTS["thermal_state"])).strip().lower()
    cleaned["power_draw_watts"] = parse_float(raw_row.get(header_mapping.get("power_draw_watts")), FIELD_DEFAULTS["power_draw_watts"])
    cleaned["voltage_mv"] = parse_float(raw_row.get(header_mapping.get("voltage_mv")), FIELD_DEFAULTS["voltage_mv"])
    
    # Range validations
    if not (0.0 <= cleaned["cpu_usage"] <= 100.0):
        return None, f"CPU usage {cleaned['cpu_usage']}% is out of bounds (0-100)."
    if not (0.0 <= cleaned["memory_usage"] <= 100.0):
        return None, f"Memory usage {cleaned['memory_usage']}% is out of bounds (0-100)."
    if not (0.0 <= cleaned["disk_usage"] <= 100.0):
        return None, f"Disk usage {cleaned['disk_usage']}% is out of bounds (0-100)."
    if not (0.0 <= cleaned["battery_level"] <= 100.0):
        cleaned["battery_level"] = max(0.0, min(100.0, cleaned["battery_level"]))
    if not (0.0 <= cleaned["battery_health"] <= 100.0):
        cleaned["battery_health"] = max(0.0, min(100.0, cleaned["battery_health"]))
    if cleaned["cpu_temperature"] < -50.0 or cleaned["cpu_temperature"] > 150.0:
        return None, f"CPU temperature {cleaned['cpu_temperature']}°C is out of bounds."
    if cleaned["fan_speed"] < 0 or cleaned["fan_speed"] > 10000:
        cleaned["fan_speed"] = max(0, min(8000, cleaned["fan_speed"]))
    
    if not (0.0 <= cleaned["gpu_usage"] <= 100.0):
        cleaned["gpu_usage"] = max(0.0, min(100.0, cleaned["gpu_usage"]))
    if not (0.0 <= cleaned["gpu_memory_usage"] <= 100.0):
        cleaned["gpu_memory_usage"] = max(0.0, min(100.0, cleaned["gpu_memory_usage"]))
    if not (-100 <= cleaned["signal_strength_dbm"] <= 0):
        cleaned["signal_strength_dbm"] = max(-100, min(0, cleaned["signal_strength_dbm"]))
        
    # 4. Power Source
    raw_power_header = header_mapping.get("power_source")
    power_val = str(raw_row.get(raw_power_header)).strip().lower() if raw_power_header else ""
    if "ac" in power_val or "plug" in power_val or "line" in power_val:
        cleaned["power_source"] = "ac"
    elif "bat" in power_val or "discharge" in power_val:
        cleaned["power_source"] = "battery"
    else:
        cleaned["power_source"] = FIELD_DEFAULTS["power_source"]
        
    # Carry metadata if present
    cleaned["metadata_info"] = raw_row.get("metadata_info")
        
    return cleaned, None


def get_val(row: Dict[str, Any], key: str, default: Any) -> Any:
    val = row.get(key)
    return val if val is not None else default


def bulk_insert_normalized_telemetry(db: Session, batch: List[Dict[str, Any]]) -> List[str]:
    """
    Perform optimized bulk insert of telemetry rows across 9 normalized tables.
    Uses client-generated UUIDs to link tables.
    Returns a list of generated snapshot IDs.
    """
    snapshot_mappings = []
    cpu_mappings = []
    gpu_mappings = []
    memory_mappings = []
    battery_mappings = []
    disk_mappings = []
    wifi_mappings = []
    thermal_mappings = []
    power_mappings = []
    
    snapshot_ids = []
    
    for row in batch:
        # Generate client-side UUIDv4
        snapshot_id = str(uuid.uuid4())
        snapshot_ids.append(snapshot_id)
        
        # 1. Telemetry Snapshot
        snapshot_mappings.append({
            "id": snapshot_id,
            "device_id": row["device_id"],
            "timestamp": row.get("timestamp") or datetime.utcnow()
        })
        
        # 2. CPU Metrics
        cpu_mappings.append({
            "snapshot_id": snapshot_id,
            "cpu_usage": row["cpu_usage"],
            "active_process_count": row["active_process_count"],
            "cpu_frequency_mhz": get_val(row, "cpu_frequency_mhz", FIELD_DEFAULTS["cpu_frequency_mhz"])
        })
        
        # 3. GPU Metrics
        gpu_mappings.append({
            "snapshot_id": snapshot_id,
            "gpu_usage": get_val(row, "gpu_usage", FIELD_DEFAULTS["gpu_usage"]),
            "gpu_temperature": get_val(row, "gpu_temperature", FIELD_DEFAULTS["gpu_temperature"]),
            "gpu_memory_usage": get_val(row, "gpu_memory_usage", FIELD_DEFAULTS["gpu_memory_usage"])
        })
        
        # 4. Memory Metrics
        memory_mappings.append({
            "snapshot_id": snapshot_id,
            "memory_usage": row["memory_usage"],
            "total_mb": 16384.0,  # 16 GB default RAM
            "used_mb": 16384.0 * (row["memory_usage"] / 100.0)
        })
        
        # 5. Battery Metrics
        battery_mappings.append({
            "snapshot_id": snapshot_id,
            "battery_level": row["battery_level"],
            "battery_health": row["battery_health"],
            "battery_temperature": get_val(row, "battery_temperature", FIELD_DEFAULTS["battery_temperature"]),
            "cycle_count": get_val(row, "cycle_count", FIELD_DEFAULTS["cycle_count"])
        })
        
        # 6. Disk Metrics
        disk_mappings.append({
            "snapshot_id": snapshot_id,
            "disk_usage": row["disk_usage"],
            "read_bytes_sec": get_val(row, "read_bytes_sec", FIELD_DEFAULTS["read_bytes_sec"]),
            "write_bytes_sec": get_val(row, "write_bytes_sec", FIELD_DEFAULTS["write_bytes_sec"])
        })
        
        # 7. WiFi Metrics
        wifi_mappings.append({
            "snapshot_id": snapshot_id,
            "signal_strength_dbm": get_val(row, "signal_strength_dbm", FIELD_DEFAULTS["signal_strength_dbm"]),
            "ssid": get_val(row, "ssid", FIELD_DEFAULTS["ssid"]),
            "link_speed_mbps": get_val(row, "link_speed_mbps", FIELD_DEFAULTS["link_speed_mbps"])
        })
        
        # 8. Thermal Metrics
        thermal_mappings.append({
            "snapshot_id": snapshot_id,
            "cpu_temperature": row["cpu_temperature"],
            "fan_speed_rpm": row["fan_speed"],
            "thermal_state": get_val(row, "thermal_state", FIELD_DEFAULTS["thermal_state"])
        })
        
        # 9. Power Metrics
        power_mappings.append({
            "snapshot_id": snapshot_id,
            "power_source": row["power_source"],
            "power_draw_watts": get_val(row, "power_draw_watts", FIELD_DEFAULTS["power_draw_watts"]),
            "voltage_mv": get_val(row, "voltage_mv", FIELD_DEFAULTS["voltage_mv"])
        })
        
    # Execute bulk inserts in proper order (parent first)
    db.bulk_insert_mappings(TelemetrySnapshot, snapshot_mappings)
    db.bulk_insert_mappings(CPUMetrics, cpu_mappings)
    db.bulk_insert_mappings(GPUMetrics, gpu_mappings)
    db.bulk_insert_mappings(MemoryMetrics, memory_mappings)
    db.bulk_insert_mappings(BatteryMetrics, battery_mappings)
    db.bulk_insert_mappings(DiskMetrics, disk_mappings)
    db.bulk_insert_mappings(WiFiMetrics, wifi_mappings)
    db.bulk_insert_mappings(ThermalMetrics, thermal_mappings)
    db.bulk_insert_mappings(PowerMetrics, power_mappings)
    
    return snapshot_ids
