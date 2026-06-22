"""
Phase 46 — Cross-Platform Telemetry Collector Library.

Provides a platform-detection router and a shared base class for all
hardware collectors.  Each concrete collector (Mac, Windows, Linux) must
implement `collect()` and return a `TelemetryReading` dataclass instance.

Supported sources
-----------------
  macOS   : psutil + pmset + AppleScript (no extra deps)
  Windows : psutil + WMI (Windows Performance Counters)
                       + OpenHardwareMonitor WMI bridge (temperatures)
  Linux   : psutil + /sys/class/thermal + iw / iwconfig (WiFi)

The module is designed to run directly on the *host* machine (outside Docker)
because hardware sensor APIs require direct OS access.
"""

from __future__ import annotations

import os
import sys
import time
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("telemetry.collector")

# ---------------------------------------------------------------------------
# Shared data model
# ---------------------------------------------------------------------------

@dataclass
class TelemetryReading:
    """
    Unified telemetry snapshot produced by every platform collector.
    All fields that cannot be read on a given platform default to None.
    """
    # Identity
    device_id: str

    # CPU
    cpu_usage: float                      # %
    cpu_temperature: Optional[float]      # °C  (None on restricted platforms)
    cpu_frequency_mhz: Optional[float]   # MHz

    # GPU
    gpu_usage: Optional[float]           # %
    gpu_temperature: Optional[float]     # °C
    gpu_memory_usage: Optional[float]    # %

    # Memory
    memory_usage: float                  # %

    # Disk
    disk_usage: float                    # %
    read_bytes_sec: Optional[int]        # B/s
    write_bytes_sec: Optional[int]       # B/s

    # Battery
    battery_level: float                 # %
    battery_health: float                # % (estimated or from OHM)
    battery_temperature: Optional[float] # °C
    cycle_count: Optional[int]
    power_source: str                    # 'ac' or 'battery'

    # Thermal / Fan
    fan_speed: int                       # RPM
    thermal_state: str                   # 'nominal' | 'moderate' | 'serious' | 'critical'

    # Power
    power_draw_watts: Optional[float]   # W
    voltage_mv: Optional[float]         # mV

    # WiFi / Network
    signal_strength_dbm: Optional[int]  # dBm
    ssid: Optional[str]
    link_speed_mbps: Optional[int]      # Mbps

    # Process
    active_process_count: int

    # Collector metadata
    source: str = "unknown"             # 'mac' | 'windows-wmi' | 'windows-ohm' | 'linux'
    collection_latency_ms: float = 0.0  # time taken to collect this reading

    def to_api_payload(self) -> dict:
        """Serialize to the POST /telemetry/ JSON body format."""
        return {
            "device_id":            self.device_id,
            "cpu_usage":            self.cpu_usage,
            "memory_usage":         self.memory_usage,
            "disk_usage":           self.disk_usage,
            "cpu_temperature":      self.cpu_temperature or 45.0,
            "battery_level":        self.battery_level,
            "battery_health":       self.battery_health,
            "fan_speed":            self.fan_speed,
            "power_source":         self.power_source,
            "active_process_count": self.active_process_count,
            "cpu_frequency_mhz":    self.cpu_frequency_mhz,
            "gpu_usage":            self.gpu_usage,
            "gpu_temperature":      self.gpu_temperature,
            "gpu_memory_usage":     self.gpu_memory_usage,
            "battery_temperature":  self.battery_temperature,
            "cycle_count":          self.cycle_count,
            "read_bytes_sec":       self.read_bytes_sec,
            "write_bytes_sec":      self.write_bytes_sec,
            "signal_strength_dbm":  self.signal_strength_dbm,
            "ssid":                 self.ssid,
            "link_speed_mbps":      self.link_speed_mbps,
            "thermal_state":        self.thermal_state,
            "power_draw_watts":     self.power_draw_watts,
            "voltage_mv":           self.voltage_mv,
        }


# ---------------------------------------------------------------------------
# Abstract base collector
# ---------------------------------------------------------------------------

class BaseCollector(ABC):
    """
    Minimal contract every platform collector must satisfy.
    Subclasses must NOT block for more than 2 s per call.
    """

    def __init__(self, device_id: str):
        self.device_id = device_id
        self._prev_disk_io = None
        self._prev_disk_time = None

    @abstractmethod
    def collect(self) -> TelemetryReading:
        """
        Read all available hardware metrics and return a TelemetryReading.
        Must complete within 2 seconds.
        """

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _thermal_state(self, temp: float) -> str:
        if temp < 60:
            return "nominal"
        if temp < 75:
            return "moderate"
        if temp < 90:
            return "serious"
        return "critical"

    def _fan_from_temp(self, temp: float) -> int:
        if temp < 60:
            return 1200
        if temp < 75:
            return int(1200 + (temp - 60) * 110)
        if temp < 90:
            return int(2850 + (temp - 75) * 110)
        return 6000

    def _disk_io_rates(self, psutil) -> tuple[Optional[int], Optional[int]]:
        """
        Computes read_bytes_sec and write_bytes_sec using delta against last call.
        Returns (None, None) on first call.
        """
        try:
            current = psutil.disk_io_counters()
            now = time.monotonic()
            if self._prev_disk_io is not None:
                dt = now - self._prev_disk_time
                if dt > 0:
                    rb = int((current.read_bytes  - self._prev_disk_io.read_bytes)  / dt)
                    wb = int((current.write_bytes - self._prev_disk_io.write_bytes) / dt)
                    self._prev_disk_io   = current
                    self._prev_disk_time = now
                    return max(0, rb), max(0, wb)
            self._prev_disk_io   = current
            self._prev_disk_time = now
        except Exception:
            pass
        return None, None


# ---------------------------------------------------------------------------
# Platform router
# ---------------------------------------------------------------------------

def get_collector(device_id: str) -> BaseCollector:
    """
    Detects the current operating system and returns the appropriate collector.
    Importing platform-specific collectors is done lazily to avoid import errors
    on unsupported platforms.
    """
    platform = sys.platform

    if platform == "darwin":
        from collectors.mac_collector import MacCollector
        logger.info("Platform detected: macOS — using MacCollector")
        return MacCollector(device_id)

    elif platform == "win32":
        # Try OpenHardwareMonitor first (more complete), fall back to basic WMI
        try:
            from collectors.windows_ohm_collector import WindowsOHMCollector
            logger.info("Platform detected: Windows — using OpenHardwareMonitor collector")
            return WindowsOHMCollector(device_id)
        except Exception as e:
            logger.warning(f"OHM collector unavailable ({e}), falling back to WMI collector")
            from collectors.windows_wmi_collector import WindowsWMICollector
            return WindowsWMICollector(device_id)

    elif platform.startswith("linux"):
        from collectors.linux_collector import LinuxCollector
        logger.info("Platform detected: Linux — using LinuxCollector")
        return LinuxCollector(device_id)

    else:
        raise RuntimeError(f"Unsupported platform: {platform}")
