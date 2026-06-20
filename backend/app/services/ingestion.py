import csv
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
from app.core.logging import logger

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
    "timestamp": ["timestamp", "time", "date", "recorded_at"]
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
        # Strip trailing '%' signs or units
        clean_val = str(val).replace("%", "").replace("°C", "").replace("C", "").strip()
        return float(clean_val)
    except ValueError:
        return default

def parse_int(val: Any, default: int) -> int:
    if val is None or str(val).strip() == "":
        return default
    try:
        clean_val = str(val).replace("RPM", "").replace("rpm", "").strip()
        return int(float(clean_val)) # Handle float strings like '1200.0'
    except ValueError:
        return default

def parse_datetime(val: Any) -> datetime:
    if val is None or str(val).strip() == "":
        return datetime.utcnow()
    
    val_str = str(val).strip()
    # Try common formats
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
            
    # Try timestamp float parsing
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
    If the row is critically invalid, returns (None, error_message).
    """
    cleaned: Dict[str, Any] = {}
    
    # 1. Device ID (Required-ish, fallback to default if missing)
    raw_device_header = header_mapping.get("device_id")
    device_id = raw_row.get(raw_device_header) if raw_device_header else None
    if not device_id or str(device_id).strip() == "":
        device_id = FIELD_DEFAULTS["device_id"]
    cleaned["device_id"] = str(device_id).strip()
    
    # 2. Timestamp (Fallback to now if missing)
    raw_time_header = header_mapping.get("timestamp")
    timestamp_val = raw_row.get(raw_time_header) if raw_time_header else None
    cleaned["timestamp"] = parse_datetime(timestamp_val)
    
    # 3. Numeric values
    cleaned["cpu_usage"] = parse_float(
        raw_row.get(header_mapping.get("cpu_usage")), 
        FIELD_DEFAULTS["cpu_usage"]
    )
    cleaned["memory_usage"] = parse_float(
        raw_row.get(header_mapping.get("memory_usage")), 
        FIELD_DEFAULTS["memory_usage"]
    )
    cleaned["disk_usage"] = parse_float(
        raw_row.get(header_mapping.get("disk_usage")), 
        FIELD_DEFAULTS["disk_usage"]
    )
    cleaned["cpu_temperature"] = parse_float(
        raw_row.get(header_mapping.get("cpu_temperature")), 
        FIELD_DEFAULTS["cpu_temperature"]
    )
    cleaned["battery_level"] = parse_float(
        raw_row.get(header_mapping.get("battery_level")), 
        FIELD_DEFAULTS["battery_level"]
    )
    cleaned["battery_health"] = parse_float(
        raw_row.get(header_mapping.get("battery_health")), 
        FIELD_DEFAULTS["battery_health"]
    )
    
    cleaned["fan_speed"] = parse_int(
        raw_row.get(header_mapping.get("fan_speed")), 
        FIELD_DEFAULTS["fan_speed"]
    )
    cleaned["active_process_count"] = parse_int(
        raw_row.get(header_mapping.get("active_process_count")), 
        FIELD_DEFAULTS["active_process_count"]
    )
    
    # Limit range checks to prevent garbage telemetry inputs
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
        
    # 4. Power Source
    raw_power_header = header_mapping.get("power_source")
    power_val = str(raw_row.get(raw_power_header)).strip().lower() if raw_power_header else ""
    if "ac" in power_val or "plug" in power_val or "line" in power_val:
        cleaned["power_source"] = "ac"
    elif "bat" in power_val or "discharge" in power_val:
        cleaned["power_source"] = "battery"
    else:
        cleaned["power_source"] = FIELD_DEFAULTS["power_source"]
        
    return cleaned, None
