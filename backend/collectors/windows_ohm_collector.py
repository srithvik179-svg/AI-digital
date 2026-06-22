"""
Windows OpenHardwareMonitor (OHM) Collector — Phase 46.

OpenHardwareMonitor exposes ALL sensor readings (CPU cores, GPU, fans,
battery, voltages, clock speeds) as WMI objects under the
`root/OpenHardwareMonitor` namespace once it is running in the background.

How to enable OHM WMI support
------------------------------
  1. Download OpenHardwareMonitor ≥ 0.9.6 from https://openhardwaremonitor.org
  2. Run OpenHardwareMonitor.exe as Administrator
  3. Options → Enable WMI Provider (checkbox)
  4. Keep it running in the background

This collector then reads from the `root/OpenHardwareMonitor` WMI namespace
for precise per-core temperatures, GPU utilisation/VRAM, fan RPMs, and
battery voltages that are unavailable through standard WMI.

Fallback
--------
If OHM is not running (WMI namespace not found), this class transparently
delegates to WindowsWMICollector for all metrics.
"""

from __future__ import annotations

import time
import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger("telemetry.collector.windows_ohm")

import sys
if sys.platform != "win32":
    raise ImportError("WindowsOHMCollector is only available on Windows")

try:
    import psutil
    import wmi as _wmi_module
except ImportError as e:
    raise ImportError("Requires: pip install pywin32 wmi psutil") from e

from collectors import TelemetryReading
from collectors.windows_wmi_collector import WindowsWMICollector


# ---------------------------------------------------------------------------
# Sensor type constants (OHM SensorType field)
# ---------------------------------------------------------------------------
_OHM_TEMPERATURE = "Temperature"
_OHM_LOAD        = "Load"
_OHM_FAN         = "Fan"
_OHM_CLOCK       = "Clock"
_OHM_VOLTAGE     = "Voltage"
_OHM_POWER       = "Power"
_OHM_DATA        = "Data"       # bytes (memory/disk)
_OHM_FACTOR      = "Factor"     # %


class WindowsOHMCollector(WindowsWMICollector):
    """
    Full-fidelity Windows collector using OpenHardwareMonitor WMI bridge.

    Extends the WMI collector: OHM provides the thermal/fan/GPU data that
    standard WMI cannot expose; all other metrics still come from psutil.

    If OHM is not available, `collect()` seamlessly falls back to the parent
    WMI implementation.
    """

    def __init__(self, device_id: str):
        super().__init__(device_id)
        self._ohm_available = False
        self._ohm_wmi: Any = None
        self._init_ohm()

    # ------------------------------------------------------------------
    # OHM initialisation
    # ------------------------------------------------------------------

    def _init_ohm(self) -> None:
        try:
            self._ohm_wmi = _wmi_module.WMI(namespace="root/OpenHardwareMonitor")
            # Quick probe
            _ = list(self._ohm_wmi.Sensor())
            self._ohm_available = True
            logger.info("OpenHardwareMonitor WMI namespace connected successfully")
        except Exception as e:
            logger.warning(
                f"OpenHardwareMonitor WMI not available: {e}. "
                "Start OHM as Administrator with WMI enabled."
            )
            self._ohm_available = False

    # ------------------------------------------------------------------
    # Sensor cache
    # ------------------------------------------------------------------

    def _read_ohm_sensors(self) -> Dict[str, List[Any]]:
        """
        Returns all OHM sensors grouped by SensorType.
        Shape: { "Temperature": [sensor, ...], "Load": [...], ... }
        """
        grouped: Dict[str, List] = {}
        try:
            for sensor in self._ohm_wmi.Sensor():
                st = sensor.SensorType
                if st not in grouped:
                    grouped[st] = []
                grouped[st].append(sensor)
        except Exception as e:
            logger.warning(f"OHM sensor read error: {e}")
        return grouped

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def collect(self) -> TelemetryReading:
        t0 = time.monotonic()

        # Core metrics from psutil (fast, always available)
        cpu_usage    = round(psutil.cpu_percent(interval=None), 1)
        memory_usage = psutil.virtual_memory().percent
        disk_usage   = psutil.disk_usage('C:\\').percent
        process_count= len(psutil.pids())
        read_b, write_b = self._disk_io_rates(psutil)

        if not self._ohm_available:
            # Attempt reconnect once per collection cycle
            self._init_ohm()

        if self._ohm_available:
            sensors = self._read_ohm_sensors()
            cpu_temp      = self._ohm_cpu_temp(sensors)
            cpu_freq      = self._ohm_cpu_freq(sensors)
            gpu_usage_val = self._ohm_gpu_load(sensors)
            gpu_temp_val  = self._ohm_gpu_temp(sensors)
            gpu_mem_val   = self._ohm_gpu_mem(sensors)
            fan_speed_val = self._ohm_fan_speed(sensors)
            power_w       = self._ohm_power(sensors)
            voltage_mv    = self._ohm_voltage(sensors)
            source_label  = "windows-ohm"
        else:
            # Graceful degradation to WMI fallbacks
            cpu_temp      = self._cpu_temperature()
            cpu_freq      = self._cpu_frequency()
            gpu_usage_val = None
            gpu_temp_val  = None
            gpu_mem_val   = None
            fan_speed_val = None
            power_w       = None
            voltage_mv    = None
            source_label  = "windows-wmi"

        battery_level, power_source, battery_health, batt_temp, cycles = self._battery()
        thermal_state = self._thermal_state(cpu_temp or 55.0)
        fan_speed     = fan_speed_val or self._fan_from_temp(cpu_temp or 55.0)
        ssid, signal_dbm, link_speed = self._wifi()

        latency = round((time.monotonic() - t0) * 1000, 1)

        return TelemetryReading(
            device_id          = self.device_id,
            cpu_usage          = cpu_usage,
            cpu_temperature    = cpu_temp,
            cpu_frequency_mhz  = cpu_freq,
            gpu_usage          = gpu_usage_val,
            gpu_temperature    = gpu_temp_val,
            gpu_memory_usage   = gpu_mem_val,
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
            source             = source_label,
            collection_latency_ms = latency,
        )

    # ------------------------------------------------------------------
    # OHM sensor parsers
    # ------------------------------------------------------------------

    def _ohm_cpu_temp(self, sensors: Dict) -> Optional[float]:
        """Average of all CPU core temperature sensors."""
        temps = [
            s.Value for s in sensors.get(_OHM_TEMPERATURE, [])
            if "cpu" in s.Name.lower() or "core" in s.Name.lower()
        ]
        if temps:
            return round(sum(temps) / len(temps), 1)
        return None

    def _ohm_cpu_freq(self, sensors: Dict) -> Optional[float]:
        """Average CPU core clock frequency (MHz)."""
        clocks = [
            s.Value for s in sensors.get(_OHM_CLOCK, [])
            if "cpu" in s.Name.lower() or "core" in s.Name.lower()
        ]
        if clocks:
            return round(sum(clocks) / len(clocks), 0)
        return None

    def _ohm_gpu_load(self, sensors: Dict) -> Optional[float]:
        """GPU Core load (%)."""
        for s in sensors.get(_OHM_LOAD, []):
            if "gpu core" in s.Name.lower() or "gpu total" in s.Name.lower():
                return round(float(s.Value), 1)
        return None

    def _ohm_gpu_temp(self, sensors: Dict) -> Optional[float]:
        """GPU Core temperature (°C)."""
        for s in sensors.get(_OHM_TEMPERATURE, []):
            if "gpu" in s.Name.lower():
                return round(float(s.Value), 1)
        return None

    def _ohm_gpu_mem(self, sensors: Dict) -> Optional[float]:
        """GPU Memory controller load (%) — proxy for VRAM utilisation."""
        for s in sensors.get(_OHM_LOAD, []):
            if "gpu memory" in s.Name.lower() or "vram" in s.Name.lower():
                return round(float(s.Value), 1)
        return None

    def _ohm_fan_speed(self, sensors: Dict) -> Optional[int]:
        """Maximum fan RPM across all fans."""
        rpms = [s.Value for s in sensors.get(_OHM_FAN, [])]
        if rpms:
            return int(max(rpms))
        return None

    def _ohm_power(self, sensors: Dict) -> Optional[float]:
        """Total CPU package power draw (W)."""
        for s in sensors.get(_OHM_POWER, []):
            if "cpu package" in s.Name.lower() or "package" in s.Name.lower():
                return round(float(s.Value), 2)
        return None

    def _ohm_voltage(self, sensors: Dict) -> Optional[float]:
        """Battery or CPU voltage in mV."""
        for s in sensors.get(_OHM_VOLTAGE, []):
            if "battery" in s.Name.lower() or "cpu vcore" in s.Name.lower():
                return round(float(s.Value) * 1000, 0)  # V → mV
        return None
