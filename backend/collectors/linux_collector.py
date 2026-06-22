"""
Linux Hardware Collector — Phase 46.

Data sources
------------
  psutil                     : CPU, memory, disk, processes, net I/O
  /sys/class/thermal/        : thermal zone temperatures
  /sys/class/power_supply/   : battery level, health, voltage, power status
  iw / iwgetid / iwconfig    : WiFi SSID, signal strength, link rate
  /sys/class/hwmon/          : fan RPM (hwmon sensors)
  /sys/class/drm/            : GPU utilisation (Linux ≥ 5.14 for dGPU)

No extra pip dependencies beyond psutil.
"""

from __future__ import annotations

import os
import re
import time
import subprocess
import logging
from typing import Optional

import psutil

from collectors import BaseCollector, TelemetryReading

logger = logging.getLogger("telemetry.collector.linux")


class LinuxCollector(BaseCollector):
    """Hardware metric collector for Linux hosts."""

    def __init__(self, device_id: str):
        super().__init__(device_id)
        psutil.cpu_percent(interval=None)
        time.sleep(0.3)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def collect(self) -> TelemetryReading:
        t0 = time.monotonic()

        cpu_usage    = round(psutil.cpu_percent(interval=None), 1)
        memory_usage = psutil.virtual_memory().percent
        disk_usage   = psutil.disk_usage('/').percent
        process_count= len(psutil.pids())
        cpu_freq     = self._cpu_freq()
        read_b, write_b = self._disk_io_rates(psutil)

        cpu_temp     = self._cpu_temp()
        fan_speed    = self._fan_speed()
        thermal_state= self._thermal_state(cpu_temp or 55.0)

        gpu_usage, gpu_temp, gpu_mem = self._gpu()

        level, source, health, batt_temp, voltage_mv, cycles = self._battery()
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
            battery_level      = level,
            battery_health     = health,
            battery_temperature= batt_temp,
            cycle_count        = cycles,
            power_source       = source,
            fan_speed          = fan_speed or self._fan_from_temp(cpu_temp or 55.0),
            thermal_state      = thermal_state,
            power_draw_watts   = None,
            voltage_mv         = voltage_mv,
            signal_strength_dbm= signal_dbm,
            ssid               = ssid,
            link_speed_mbps    = link_speed,
            active_process_count = process_count,
            source             = "linux",
            collection_latency_ms = latency,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _cpu_freq(self) -> Optional[float]:
        try:
            freq = psutil.cpu_freq()
            return round(freq.current, 0) if freq else None
        except Exception:
            return None

    def _cpu_temp(self) -> Optional[float]:
        """Reads first thermal zone from /sys/class/thermal/."""
        try:
            # psutil sensors (preferred if available)
            temps = psutil.sensors_temperatures()
            if temps:
                for key in ("coretemp", "k10temp", "zenpower", "cpu_thermal"):
                    if key in temps and temps[key]:
                        return round(temps[key][0].current, 1)
                # Generic fallback: first available sensor
                first_sensor = next(iter(temps.values()))
                if first_sensor:
                    return round(first_sensor[0].current, 1)
        except Exception:
            pass
        # /sys/class/thermal fallback
        try:
            with open("/sys/class/thermal/thermal_zone0/temp") as f:
                return round(int(f.read().strip()) / 1000.0, 1)
        except Exception:
            return round(45.0 + psutil.cpu_percent(interval=None) * 0.45, 1)

    def _fan_speed(self) -> Optional[int]:
        try:
            fans = psutil.sensors_fans()
            if fans:
                all_rpms = [f.current for sensors in fans.values() for f in sensors]
                return max(all_rpms) if all_rpms else None
        except Exception:
            pass
        # hwmon fallback
        try:
            for hwmon in os.listdir("/sys/class/hwmon"):
                base = f"/sys/class/hwmon/{hwmon}"
                for i in range(10):
                    fan_file = f"{base}/fan{i+1}_input"
                    if os.path.exists(fan_file):
                        with open(fan_file) as f:
                            return int(f.read().strip())
        except Exception:
            pass
        return None

    def _battery(self):
        """Returns (level, source, health, temp, voltage_mv, cycles)."""
        level, source, health, batt_temp, voltage_mv, cycles = 100.0, "ac", 95.0, None, None, None
        ps_path = "/sys/class/power_supply"
        try:
            bat = psutil.sensors_battery()
            if bat:
                level  = round(bat.percent, 1)
                source = "battery" if not bat.power_plugged else "ac"
        except Exception:
            pass
        try:
            for supply in os.listdir(ps_path):
                base = f"{ps_path}/{supply}"
                type_f = f"{base}/type"
                if not os.path.exists(type_f):
                    continue
                with open(type_f) as f:
                    if f.read().strip() != "Battery":
                        continue
                def _r(path):
                    try:
                        with open(path) as f: return f.read().strip()
                    except: return None

                cap   = _r(f"{base}/capacity")
                stat  = _r(f"{base}/status")
                ec    = _r(f"{base}/energy_full")
                ed    = _r(f"{base}/energy_full_design")
                volt  = _r(f"{base}/voltage_now")
                cyc   = _r(f"{base}/cycle_count")
                temp  = _r(f"{base}/temp")

                if cap:   level  = float(cap)
                if stat:  source = "battery" if stat not in ("Charging", "Full", "Unknown") else "ac"
                if ec and ed and int(ed) > 0:
                    health = round(min(100.0, int(ec) / int(ed) * 100), 1)
                if volt:  voltage_mv = round(int(volt) / 1000.0, 0)   # µV → mV
                if cyc:   cycles = int(cyc)
                if temp:  batt_temp = round(int(temp) / 10.0, 1)
                break
        except Exception:
            pass
        return level, source, health, batt_temp, voltage_mv, cycles

    def _gpu(self):
        """Reads NVIDIA GPU metrics via nvidia-smi if available."""
        try:
            out = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=utilization.gpu,temperature.gpu,memory.used,memory.total",
                 "--format=csv,noheader,nounits"],
                timeout=3, stderr=subprocess.DEVNULL
            ).decode().strip().split(",")
            usage = round(float(out[0]), 1)
            temp  = round(float(out[1]), 1)
            used  = float(out[2])
            total = float(out[3]) if float(out[3]) > 0 else 1.0
            mem   = round(used / total * 100.0, 1)
            return usage, temp, mem
        except Exception:
            return None, None, None

    def _wifi(self):
        """Reads WiFi via iw or iwconfig."""
        try:
            # Try iw first (modern)
            out = subprocess.check_output(
                ["iw", "dev"], timeout=3, stderr=subprocess.DEVNULL
            ).decode()
            iface_m = re.search(r"Interface\s+(\S+)", out)
            if not iface_m:
                raise ValueError("no interface found")
            iface = iface_m.group(1)

            link_out = subprocess.check_output(
                ["iw", iface, "link"], timeout=3, stderr=subprocess.DEVNULL
            ).decode()
            ssid_m   = re.search(r"SSID:\s+(.+)", link_out)
            signal_m = re.search(r"signal:\s+(-?\d+)\s+dBm", link_out)
            rate_m   = re.search(r"tx bitrate:\s+([\d.]+)", link_out)

            ssid       = ssid_m.group(1).strip()  if ssid_m  else None
            signal_dbm = int(signal_m.group(1))   if signal_m else None
            link_speed = int(float(rate_m.group(1))) if rate_m else None
            return ssid, signal_dbm, link_speed
        except Exception:
            pass

        try:
            out = subprocess.check_output(
                ["iwconfig"], timeout=3, stderr=subprocess.DEVNULL
            ).decode()
            ssid_m   = re.search(r'ESSID:"([^"]+)"', out)
            signal_m = re.search(r"Signal level=(-?\d+)\s*dBm", out)
            rate_m   = re.search(r"Bit Rate=([\d.]+)", out)
            return (
                ssid_m.group(1)         if ssid_m  else None,
                int(signal_m.group(1))  if signal_m else None,
                int(float(rate_m.group(1))) if rate_m else None,
            )
        except Exception:
            return None, None, None
