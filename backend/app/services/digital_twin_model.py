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

    def step_simulation(
        self,
        cpu_load: float,
        gpu_load: float,
        power_source: Optional[str] = None,
        delta_t_mins: float = 1.0
    ) -> Dict[str, Any]:
        """
        Executes a single step of the simulation, updating component models.
        - delta_t_mins is the step duration in minutes (default 1.0)
        """
        # 1. Resolve power source
        if power_source is None:
            power_source = self.battery.power_source
        self.battery.power_source = power_source

        # 2. CPU/GPU usages
        self.cpu.current_usage = cpu_load
        self.gpu.current_usage = gpu_load

        # 3. Thermal Throttling
        # Threshold: if temp >= 85 C, throttle frequency.
        # Max temp before full throttle: 105 C.
        current_temp = self.thermal.cpu_temperature
        throttle_ratio = 1.0
        if current_temp >= 85.0:
            # Linear throttling from 85C (1.0) to 105C (0.2)
            throttle_ratio = max(0.2, 1.0 - 0.04 * (current_temp - 85.0))
        
        # CPU Frequency drops
        base_freq = 3500.0  # MHz
        self.cpu.frequency_mhz = base_freq * throttle_ratio

        # 4. Thermodynamic Dissipation
        # CPU/GPU heat generation is scaled by CPU frequency/throttling
        cpu_heat_factor = 0.25 * throttle_ratio
        gpu_heat_factor = 0.15
        heat_generation = (cpu_load * cpu_heat_factor + gpu_load * gpu_heat_factor)  # per minute
        
        # Passive cooling
        ambient_temp = 25.0
        temp_above_ambient = max(0.0, current_temp - ambient_temp)
        passive_cooling = 0.03 * temp_above_ambient
        
        # Active cooling (fans)
        # Fan ramp speed: max change 1000 RPM per minute
        target_fan = self.thermal.target_fan_speed_rpm
        fan_speed_diff = target_fan - self.thermal.fan_speed_rpm
        fan_ramp = 1000.0 * delta_t_mins
        if abs(fan_speed_diff) <= fan_ramp:
            self.thermal.fan_speed_rpm = target_fan
        else:
            sign = 1 if fan_speed_diff > 0 else -1
            self.thermal.fan_speed_rpm += int(sign * fan_ramp)
            
        active_cooling = 0.00005 * self.thermal.fan_speed_rpm * temp_above_ambient
        
        net_heat = heat_generation - passive_cooling - active_cooling
        new_temp = current_temp + net_heat * delta_t_mins
        self.thermal.cpu_temperature = max(ambient_temp, min(105.0, new_temp))
        
        # Update thermal state category based on new temperature
        if self.thermal.cpu_temperature < 60.0:
            self.thermal.thermal_state = "nominal"
        elif self.thermal.cpu_temperature < 75.0:
            self.thermal.thermal_state = "moderate"
        elif self.thermal.cpu_temperature < 90.0:
            self.thermal.thermal_state = "serious"
        else:
            self.thermal.thermal_state = "critical"

        # 5. Power Draw & Battery Dynamics
        # Base power: 10W on AC, 8W on battery
        # CPU power draw: 35W max under load, GPU: 20W max
        cpu_watts = 35.0 * (cpu_load / 100.0) * throttle_ratio
        gpu_watts = 20.0 * (gpu_load / 100.0)
        aux_watts = 7.0  # RAM, Disk, screen, etc.
        component_watts = cpu_watts + gpu_watts + aux_watts
        
        total_wh = 56.0
        
        if power_source == "ac":
            # Charging
            # In CV (constant voltage) mode, charging power decreases near 100%
            current_level = self.battery.level
            if current_level >= 100.0:
                charging_watts = 0.0
                self.battery.level = 100.0
            else:
                # CC/CV model: charge speed decreases as level -> 100%
                charging_watts = 45.0 * max(0.05, 1.0 - (current_level / 100.0))
                # Add energy to battery
                added_wh = charging_watts * (delta_t_mins / 60.0)
                current_wh = (current_level / 100.0) * total_wh
                new_wh = min(total_wh, current_wh + added_wh)
                self.battery.level = (new_wh / total_wh) * 100.0
                
            power_draw = 15.0 + component_watts + charging_watts
        else:
            # Discharging on Battery
            power_draw = component_watts
            current_level = self.battery.level
            current_wh = (current_level / 100.0) * total_wh
            consumed_wh = power_draw * (delta_t_mins / 60.0)
            new_wh = max(0.0, current_wh - consumed_wh)
            self.battery.level = (new_wh / total_wh) * 100.0
            
            # Record cycle count throughput and health wear
            discharge_pct = (consumed_wh / total_wh) * 100.0
            # Accumulate fractional cycle count
            self.battery.cycle_count = int(self.battery.cycle_count + (discharge_pct / 100.0))
            # Degradation: 0.0003% health drop per discharge_pct
            self.battery.health = max(0.0, self.battery.health - 0.0003 * discharge_pct)

        # Update disk wear
        write_speed = 50 * 1024 + int((cpu_load / 100.0) * 50 * 1024**2)
        self.disk.write_bytes_sec = write_speed
        self.disk.read_bytes_sec = 20 * 1024 + int((cpu_load / 100.0) * 20 * 1024**2)
        hourly_tb = (write_speed * delta_t_mins * 60) / (1024**4)
        self.disk.cumulative_write_wear_tb += hourly_tb

        # Update battery temp slightly based on power draw
        if power_source == "ac" and self.battery.level < 99.0:
            self.battery.temperature = 30.0 + 5.0 * (power_draw / 60.0)
        else:
            self.battery.temperature = 28.0 + 3.0 * (power_draw / 60.0)

        # Update active processes slightly
        self.cpu.active_process_count = int(100 + cpu_load * 0.5)
        
        # We can update power draw on components if needed
        # Return serialized state
        return self.get_state_dict()

    def simulate_time_series_workload(
        self,
        cpu_load: float,
        gpu_load: float,
        duration_mins: float,
        power_source: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Runs a step-by-step thermodynamic and power simulation, stepping at 1-minute intervals.
        Returns a list of state dictionaries for each minute.
        """
        states = []
        steps = int(max(1.0, duration_mins))
        for _ in range(steps):
            state = self.step_simulation(
                cpu_load=cpu_load,
                gpu_load=gpu_load,
                power_source=power_source,
                delta_t_mins=1.0
            )
            states.append(state)
        return states

    def simulate_workload(self, cpu_load: float, gpu_load: float, duration_mins: float) -> Dict[str, Any]:
        """
        Runs a thermodynamic and power-drain simulation of the laptop twin.
        Projects new temperature and battery level without modifying actual logged database states.
        Keeps backward compatibility with the original simulate_workload structure.
        """
        initial_temp = self.thermal.cpu_temperature
        initial_fan = self.thermal.fan_speed_rpm
        initial_bat = self.battery.level
        
        # Run step simulation to get the final state
        states = self.simulate_time_series_workload(
            cpu_load=cpu_load,
            gpu_load=gpu_load,
            duration_mins=duration_mins
        )
        final_state = states[-1] if states else self.get_state_dict()
        
        cpu_watts = 35.0 * (cpu_load / 100.0)
        gpu_watts = 20.0 * (gpu_load / 100.0)
        power_draw_watts = 10.0 + cpu_watts + gpu_watts
        
        return {
            "device_id": self.device_id,
            "simulation_parameters": {
                "cpu_load_input": cpu_load,
                "gpu_load_input": gpu_load,
                "duration_minutes": duration_mins
            },
            "initial_state": {
                "cpu_temperature": initial_temp,
                "fan_speed_rpm": initial_fan,
                "battery_level": initial_bat
            },
            "projected_state": {
                "cpu_temperature": final_state["components"]["thermal"]["cpu_temperature"],
                "fan_speed_rpm": final_state["components"]["thermal"]["fan_speed_rpm"],
                "battery_level": final_state["components"]["battery"]["level"],
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
