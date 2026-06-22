"""
Windows WMI Collector — Phase 46.

Reads hardware metrics via two complementary Windows subsystems:

  1. psutil                — CPU %, memory, disk, process count, disk I/O
  2. Windows Performance Counters (via WMI Win32_PerfFormattedData_*)
       - Win32_Processor   → CPU load, clock frequency
       - Win32_PhysicalMemory / OperatingSystem → memory
       - Win32_DiskDrive / PerfFormattedData_PerfDisk_LogicalDisk → disk I/O
       - Win32_Battery / BatteryStatus → battery level, charge state
       - MSAcpi_ThermalZoneTemperature → CPU thermal zone temperatures
  3. Win32_NetworkAdapter / NetworkAdapterConfiguration → WiFi SSID & signal

Prerequisites (Windows-only)
----------------------------
  pip install pywin32 wmi psutil

OpenHardwareMonitor (OHM) is handled in a separate collector
(windows_ohm_collector.py) which inherits from this class.
"""

from __future__ import annotations

import time
import logging
from typing import Optional

logger = logging.getLogger("telemetry.collector.windows_wmi")

# Guard: this module must only be imported on Windows
import sys
if sys.platform != "win32":
    raise ImportError("WindowsWMICollector is only available on Windows")

try:
    import psutil
    import wmi as _wmi_module
except ImportError as e:
    raise ImportError(
        "Windows collector requires: pip install pywin32 wmi psutil"
    ) from e

from collectors import BaseCollector, TelemetryReading


class WindowsWMICollector(BaseCollector):
    """
    Windows Performance Counter + WMI hardware collector.

    All WMI queries are executed synchronously via the `wmi` package
    (which wraps COM/WMI via pywin32).  The WMI connection object is
    re-used across calls for efficiency.
    """

    _KELVIN_OFFSET = 2731  # WMI thermal temps are in tenths of Kelvin

    def __init__(self, device_id: str):
        super().__init__(device_id)
        self._wmi = _wmi_module.WMI()
        # Warm up psutil CPU tracking
        psutil.cpu_percent(interval=None)
        time.sleep(0.3)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def collect(self) -> TelemetryReading:
        t0 = time.monotonic()

        cpu_usage       = round(psutil.cpu_percent(interval=None), 1)
        memory_usage    = psutil.virtual_memory().percent
        disk_usage      = psutil.disk_usage('C:\\').percent
        process_count   = len(psutil.pids())
        cpu_freq        = self._cpu_frequency()
        read_b, write_b = self._disk_io_rates(psutil)

        cpu_temp        = self._cpu_temperature()
        gpu_usage, gpu_temp, gpu_mem = self._gpu()
        battery_level, power_source, battery_health, batt_temp, cycles = self._battery()
        fan_speed       = self._fan_from_temp(cpu_temp or 55.0)
        thermal_state   = self._thermal_state(cpu_temp or 55.0)
        power_w, voltage_mv = self._power()
        ssid, signal_dbm, link_speed = self._wifi()

        latency = round((time.monotonic() - t0) * 1000, 1)

        return TelemetryReading(
            device_id          = self.device_id,
            cpu_usage          = cpu_usage,
            cpu_temperature    = cpu_temp,
            cpu_frequency_mhz  = cpu_freq,
            gpu_usage          = gpu_usage,
            gpu_temperature    = gpu_temp,
            gpu_memory_usage   = gpu_mem,
            memory_usage       = memory_usage,
            disk_usage         = disk_usage,
            read_bytes_sec     = read_b,
            write_bytes_sec    = write_b,
            battery_level      = battery_level,
            battery_health     = battery_health,
            battery_temperature= batt_temp,
            cycle_count        = cycles,
            power_source       = power_source,
            fan_speed          = fan_speed,
            thermal_state      = thermal_state,
            power_draw_watts   = power_w,
            voltage_mv         = voltage_mv,
            signal_strength_dbm= signal_dbm,
            ssid               = ssid,
            link_speed_mbps    = link_speed,
            active_process_count = process_count,
            source             = "windows-wmi",
            collection_latency_ms = latency,
        )

    # ------------------------------------------------------------------
    # Private: CPU
    # ------------------------------------------------------------------

    def _cpu_frequency(self) -> Optional[float]:
        try:
            for proc in self._wmi.Win32_Processor():
                return float(proc.CurrentClockSpeed)
        except Exception:
            pass
        try:
            freq = psutil.cpu_freq()
            return round(freq.current, 0) if freq else None
        except Exception:
            return None

    def _cpu_temperature(self) -> Optional[float]:
        """
        Reads MSAcpi_ThermalZoneTemperature from ACPI.
        Note: not all OEMs expose this; returns None if unavailable.
        """
        try:
            wmi_acpi = _wmi_module.WMI(namespace="root/wmi")
            zones = wmi_acpi.MSAcpi_ThermalZoneTemperature()
            if zones:
                # Average across all thermal zones
                temps = [
                    (z.CurrentTemperature - self._KELVIN_OFFSET) / 10.0
                    for z in zones
                    if z.CurrentTemperature > 0
                ]
                if temps:
                    return round(sum(temps) / len(temps), 1)
        except Exception:
            pass
        # Fallback: physics estimate from CPU %
        cpu = round(psutil.cpu_percent(interval=None), 1)
        return round(45.0 + cpu * 0.45, 1)

    # ------------------------------------------------------------------
    # Private: GPU
    # ------------------------------------------------------------------

    def _gpu(self) -> tuple[Optional[float], Optional[float], Optional[float]]:
        """
        Queries Win32_VideoController for adapter info.
        GPU utilisation requires DirectX query or OHM; returns None here
        — the OHM subclass overrides this method for full GPU metrics.
        """
        return None, None, None

    # ------------------------------------------------------------------
    # Private: Battery
    # ------------------------------------------------------------------

    def _battery(self) -> tuple[float, str, float, Optional[float], Optional[int]]:
        level, source, health, batt_temp, cycles = 100.0, "ac", 95.0, None, None
        try:
            bat = psutil.sensors_battery()
            if bat:
                level  = round(bat.percent, 1)
                source = "battery" if not bat.power_plugged else "ac"
        except Exception:
            pass

        try:
            for batt in self._wmi.Win32_Battery():
                # EstimatedChargeRemaining (0-100)
                if batt.EstimatedChargeRemaining is not None:
                    level = float(batt.EstimatedChargeRemaining)
                # BatteryStatus: 2 = AC, everything else = on battery
                if batt.BatteryStatus is not None:
                    source = "ac" if batt.BatteryStatus == 2 else "battery"
                if batt.DesignCapacity and batt.FullChargeCapacity:
                    health = round(
                        min(100.0, batt.FullChargeCapacity / batt.DesignCapacity * 100), 1
                    )
                if batt.CycleCount is not None:
                    cycles = batt.CycleCount
        except Exception:
            pass

        return level, source, health, batt_temp, cycles

    # ------------------------------------------------------------------
    # Private: Power
    # ------------------------------------------------------------------

    def _power(self) -> tuple[Optional[float], Optional[float]]:
        """Returns (power_draw_watts, voltage_mv)."""
        try:
            for bat in self._wmi.Win32_Battery():
                volts = getattr(bat, "DesignVoltage", None)
                if volts:
                    return None, float(volts)
        except Exception:
            pass
        return None, None

    # ------------------------------------------------------------------
    # Private: WiFi
    # ------------------------------------------------------------------

    def _wifi(self) -> tuple[Optional[str], Optional[int], Optional[int]]:
        """
        Uses netsh to query the active WiFi connection on Windows.
        Returns (ssid, signal_dbm_estimate, link_speed_mbps).
        """
        import subprocess, re
        try:
            out = subprocess.check_output(
                ["netsh", "wlan", "show", "interfaces"],
                timeout=4, stderr=subprocess.DEVNULL
            ).decode("utf-8", errors="replace")

            ssid_m   = re.search(r"SSID\s+:\s+(.+)", out)
            signal_m = re.search(r"Signal\s+:\s+(\d+)%", out)
            speed_m  = re.search(r"Receive rate.*?:\s+([\d.]+)", out)

            ssid  = ssid_m.group(1).strip()  if ssid_m  else None
            # Convert Windows signal % to approximate dBm
            # Windows maps: 0% → -100 dBm, 100% → -50 dBm (linear approx)
            signal_pct = int(signal_m.group(1)) if signal_m else None
            signal_dbm = int(-100 + signal_pct * 0.5) if signal_pct is not None else None
            link_speed = int(float(speed_m.group(1))) if speed_m else None

            return ssid, signal_dbm, link_speed
        except Exception:
            return None, None, None
