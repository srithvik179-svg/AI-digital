"""
Digital Twin Core Model — Phase 11
Object-oriented virtual representation of a laptop and its sub-systems.
Maintains state, models sub-component trends, projects wear, and simulates thermodynamics.
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional
from datetime import datetime
from app.models.telemetry import TelemetrySnapshot

class VirtualComponent:
    """Base class for all virtual laptop sub-components."""
    def __init__(self):
        self.last_updated: Optional[datetime] = None

    def update(self, snapshot: TelemetrySnapshot):
        self.last_updated = snapshot.timestamp


class VirtualCPU(VirtualComponent):
    """Virtual representation of the CPU sub-system."""
    def __init__(self):
        super().__init__()
        self.current_usage: float = 0.0
        self.active_process_count: int = 0
        self.frequency_mhz: Optional[float] = None
        self.historical_load: List[float] = []

    def update(self, snapshot: TelemetrySnapshot):
        super().update(snapshot)
        if snapshot.cpu:
            self.current_usage = snapshot.cpu.cpu_usage
            self.active_process_count = snapshot.cpu.active_process_count
            self.frequency_mhz = snapshot.cpu.cpu_frequency_mhz
            
            # Maintain rolling average of last 10 load values
            self.historical_load.append(self.current_usage)
            if len(self.historical_load) > 10:
                self.historical_load.pop(0)

    @property
    def load_average(self) -> float:
        if not self.historical_load:
            return 0.0
        return sum(self.historical_load) / len(self.historical_load)


class VirtualGPU(VirtualComponent):
    """Virtual representation of the GPU sub-system."""
    def __init__(self):
        super().__init__()
        self.current_usage: float = 0.0
        self.temperature: Optional[float] = None
        self.memory_usage: Optional[float] = None

    def update(self, snapshot: TelemetrySnapshot):
        super().update(snapshot)
        if snapshot.gpu:
            self.current_usage = snapshot.gpu.gpu_usage
            self.temperature = snapshot.gpu.gpu_temperature
            self.memory_usage = snapshot.gpu.gpu_memory_usage


class VirtualRAM(VirtualComponent):
    """Virtual representation of the Memory sub-system."""
    def __init__(self):
        super().__init__()
        self.current_usage: float = 0.0

    def update(self, snapshot: TelemetrySnapshot):
        super().update(snapshot)
        if snapshot.memory:
            self.current_usage = snapshot.memory.memory_usage


class VirtualBattery(VirtualComponent):
    """Virtual representation of the Battery power delivery sub-system."""
    def __init__(self):
        super().__init__()
        self.level: float = 100.0
        self.health: float = 100.0
        self.temperature: Optional[float] = None
        self.cycle_count: int = 0
        self.power_source: str = "ac"

    def update(self, snapshot: TelemetrySnapshot):
        super().update(snapshot)
        if snapshot.battery:
            self.level = snapshot.battery.battery_level
            self.health = snapshot.battery.battery_health
            self.temperature = snapshot.battery.battery_temperature
            self.cycle_count = snapshot.battery.cycle_count or 0
        if snapshot.power:
            self.power_source = snapshot.power.power_source

    @property
    def estimated_wear_percentage(self) -> float:
        """Projects how much the battery has degraded relative to cycle count limits (typically 1000 cycles)."""
        limit = 1000.0
        return min(100.0, (self.cycle_count / limit) * 100.0)

    @property
    def lifetime_projection_days(self) -> float:
        """Projects remaining useful lifetime in days based on health degradation trend (replaces battery at < 70% health)."""
        remaining_health = max(0.0, self.health - 70.0)
        # Assume 1 cycle per day on average, health degrades at 0.03% per cycle
        if remaining_health == 0:
            return 0.0
        return (remaining_health / 0.03)


class VirtualDisk(VirtualComponent):
    """Virtual representation of the Storage sub-system."""
    def __init__(self):
        super().__init__()
        self.usage: float = 0.0
        self.read_bytes_sec: int = 0
        self.write_bytes_sec: int = 0
        self.cumulative_write_wear_tb: float = 0.0

    def update(self, snapshot: TelemetrySnapshot):
        super().update(snapshot)
        if snapshot.disk:
            self.usage = snapshot.disk.disk_usage
            self.read_bytes_sec = snapshot.disk.read_bytes_sec or 0
            self.write_bytes_sec = snapshot.disk.write_bytes_sec or 0
            
            # Accumulate disk wear based on writes (e.g. assume 1 hour of this average write speed occurred)
            # 1 MB/s write for 1 hour is ~3.6 GB. Convert bytes/sec to cumulative TeraBytes written.
            # In a real model we accumulate using time deltas, here we accumulate a symbolic factor
            hourly_tb = (self.write_bytes_sec * 3600) / (1024**4)
            self.cumulative_write_wear_tb += hourly_tb


class VirtualWiFi(VirtualComponent):
    """Virtual representation of the Network connectivity sub-system."""
    def __init__(self):
        super().__init__()
        self.signal_strength_dbm: Optional[int] = None
        self.ssid: Optional[str] = None
        self.link_speed_mbps: Optional[int] = None

    def update(self, snapshot: TelemetrySnapshot):
        super().update(snapshot)
        if snapshot.wifi:
            self.signal_strength_dbm = snapshot.wifi.signal_strength_dbm
            self.ssid = snapshot.wifi.ssid
            self.link_speed_mbps = snapshot.wifi.link_speed_mbps


class VirtualThermal(VirtualComponent):
    """Virtual representation of Thermals and Fan systems."""
    def __init__(self):
        super().__init__()
        self.cpu_temperature: float = 45.0
        self.fan_speed_rpm: int = 1200
        self.thermal_state: Optional[str] = "nominal"

    def update(self, snapshot: TelemetrySnapshot):
        super().update(snapshot)
        if snapshot.thermal:
            self.cpu_temperature = snapshot.thermal.cpu_temperature
            self.fan_speed_rpm = snapshot.thermal.fan_speed_rpm
            self.thermal_state = snapshot.thermal.thermal_state

    @property
    def target_fan_speed_rpm(self) -> int:
        """Determines what fan speed the BIOS should target based on thermal load."""
        if self.cpu_temperature < 50.0:
            return 1200
        if self.cpu_temperature < 65.0:
            return 2200
        if self.cpu_temperature < 75.0:
            return 3500
        if self.cpu_temperature < 85.0:
            return 4800
        return 6000


class VirtualLaptop:
    """Master Coordinator classes maintaining the unified Object-Oriented state of the Laptop Twin."""
    def __init__(self, device_id: str):
        self.device_id = device_id
        self.cpu = VirtualCPU()
        self.gpu = VirtualGPU()
        self.memory = VirtualRAM()
        self.battery = VirtualBattery()
        self.disk = VirtualDisk()
        self.wifi = VirtualWiFi()
        self.thermal = VirtualThermal()
        self.health_score: Optional[float] = None
        self.health_category: Optional[str] = None

    def update_state(self, snapshot: TelemetrySnapshot):
        """Processes a new telemetry snapshot and transitions all virtual sub-system models."""
        self.cpu.update(snapshot)
        self.gpu.update(snapshot)
        self.memory.update(snapshot)
        self.battery.update(snapshot)
        self.disk.update(snapshot)
        self.wifi.update(snapshot)
        self.thermal.update(snapshot)
        
        self.health_score = snapshot.health_score
        self.health_category = snapshot.health_category

    def simulate_workload(self, cpu_load: float, gpu_load: float, duration_mins: float) -> Dict[str, Any]:
        """
        Runs a thermodynamic and power-drain simulation of the laptop twin.
        Projects new temperature and battery level without modifying actual logged database states.
        """
        # 1. Thermodynamics: higher workloads generate thermal energy
        base_thermal_dissipation = 0.5 # cooling rate per minute
        heat_generation = (cpu_load * 0.18 + gpu_load * 0.12) # heat units generated per minute
        
        net_heat = (heat_generation - base_thermal_dissipation) * (duration_mins / 5.0)
        projected_temp = max(40.0, min(99.0, self.thermal.cpu_temperature + net_heat))
        
        # 2. Fan RPM adjusts dynamically to temperature
        if projected_temp < 50.0:
            projected_fan_rpm = 1200
        elif projected_temp < 65.0:
            projected_fan_rpm = 2500
        elif projected_temp < 78.0:
            projected_fan_rpm = 4000
        else:
            projected_fan_rpm = 5800

        # 3. Battery Drain: power draw depends on workload
        # Base power draw is 10 Watts, max load draws 65 Watts
        power_draw_watts = 10.0 + (cpu_load / 100.0) * 40.0 + (gpu_load / 100.0) * 15.0
        
        # Calculate battery capacity in Watt-Hours (e.g. assume a standard 56 Wh battery)
        total_wh = 56.0
        current_wh = (self.battery.level / 100.0) * total_wh
        
        # Consumed energy: Wh = Watts * Hours
        consumed_wh = power_draw_watts * (duration_mins / 60.0)
        projected_wh = max(0.0, current_wh - consumed_wh)
        
        projected_battery_level = (projected_wh / total_wh) * 100.0
        
        return {
            "device_id": self.device_id,
            "simulation_parameters": {
                "cpu_load_input": cpu_load,
                "gpu_load_input": gpu_load,
                "duration_minutes": duration_mins
            },
            "initial_state": {
                "cpu_temperature": self.thermal.cpu_temperature,
                "fan_speed_rpm": self.thermal.fan_speed_rpm,
                "battery_level": self.battery.level
            },
            "projected_state": {
                "cpu_temperature": round(projected_temp, 1),
                "fan_speed_rpm": projected_fan_rpm,
                "battery_level": round(projected_battery_level, 1),
                "power_draw_watts": round(power_draw_watts, 1)
            }
        }

    def get_state_dict(self) -> Dict[str, Any]:
        """Returns a serialized dictionary view of the digital twin virtual state."""
        return {
            "device_id": self.device_id,
            "overall_health": {
                "score": self.health_score,
                "category": self.health_category
            },
            "components": {
                "cpu": {
                    "current_usage": self.cpu.current_usage,
                    "active_process_count": self.cpu.active_process_count,
                    "frequency_mhz": self.cpu.frequency_mhz,
                    "rolling_load_average": round(self.cpu.load_average, 1)
                },
                "gpu": {
                    "current_usage": self.gpu.current_usage,
                    "temperature": self.gpu.temperature,
                    "memory_usage": self.gpu.memory_usage
                },
                "ram": {
                    "current_usage": self.memory.current_usage
                },
                "battery": {
                    "level": self.battery.level,
                    "health": self.battery.health,
                    "temperature": self.battery.temperature,
                    "cycle_count": self.battery.cycle_count,
                    "power_source": self.battery.power_source,
                    "projected_wear_percentage": round(self.battery.estimated_wear_percentage, 1),
                    "projected_remaining_health_days": round(self.battery.lifetime_projection_days, 1)
                },
                "disk": {
                    "usage": self.disk.usage,
                    "read_bytes_sec": self.disk.read_bytes_sec,
                    "write_bytes_sec": self.disk.write_bytes_sec,
                    "estimated_wear_accumulated_tb": round(self.disk.cumulative_write_wear_tb, 4)
                },
                "wifi": {
                    "signal_strength_dbm": self.wifi.signal_strength_dbm,
                    "ssid": self.wifi.ssid,
                    "link_speed_mbps": self.wifi.link_speed_mbps
                },
                "thermal": {
                    "cpu_temperature": self.thermal.cpu_temperature,
                    "fan_speed_rpm": self.thermal.fan_speed_rpm,
                    "thermal_state": self.thermal.thermal_state,
                    "target_fan_speed_rpm": self.thermal.target_fan_speed_rpm
                }
            }
        }
