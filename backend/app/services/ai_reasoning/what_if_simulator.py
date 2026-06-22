"""
What-If Simulation Engine — Phase 41.
Computes instant steady-state predictions for temperature, power draw, and battery impact
based on user-configurable hypothetical workloads.
"""
from typing import Dict, Any, Optional

def simulate_what_if(
    cpu_usage: float,
    gpu_usage: float,
    memory_usage: float,
    battery_level: float,
    battery_health: float,
    power_source: str,
    ambient_temperature: float = 25.0
) -> Dict[str, Any]:
    """
    Simulates steady-state physics and power dynamics based on input parameters.
    No database queries, completes in real-time.
    """
    # 1. Iterative convergence for Temperature & Fan Speed & Throttling
    t_steady = 45.0  # Initial guess
    rpm = 1200
    thermal_state = "nominal"
    throttle_ratio = 1.0
    is_throttling = False
    
    # 10 iterations are more than enough to converge
    for _ in range(10):
        # Determine fan speed and thermal state based on current temperature
        if t_steady < 60.0:
            rpm = 1200
            thermal_state = "nominal"
        elif t_steady < 75.0:
            rpm = 2500
            thermal_state = "moderate"
        elif t_steady < 90.0:
            rpm = 4500
            thermal_state = "serious"
        else:
            rpm = 6000
            thermal_state = "critical"
            
        # Thermal Throttling: if temperature exceeds 85°C, throttle CPU frequency
        if t_steady >= 85.0:
            throttle_ratio = max(0.2, 1.0 - 0.04 * (t_steady - 85.0))
            is_throttling = True
        else:
            throttle_ratio = 1.0
            is_throttling = False
            
        # Heat generation scaled by CPU throttling
        q_gen = cpu_usage * 0.25 * throttle_ratio + gpu_usage * 0.15
        
        # Total cooling (passive + active)
        # Steady state: q_gen = cooling_coefficient * (T_steady - T_ambient)
        cooling_coeff = 0.03 + 0.00005 * rpm
        t_steady = ambient_temperature + q_gen / cooling_coeff
        
    t_steady = max(ambient_temperature, min(105.0, round(t_steady, 1)))
    
    # Re-evaluate final thermal state
    if t_steady < 60.0:
        thermal_state = "nominal"
    elif t_steady < 75.0:
        thermal_state = "moderate"
    elif t_steady < 90.0:
        thermal_state = "serious"
    else:
        thermal_state = "critical"

    # 2. Power Consumption Calculations
    cpu_watts = round(35.0 * (cpu_usage / 100.0) * throttle_ratio, 2)
    gpu_watts = round(20.0 * (gpu_usage / 100.0), 2)
    aux_watts = round(7.0 + 3.0 * (memory_usage / 100.0), 2)
    base_watts = 8.0 if power_source == "battery" else 10.0
    
    if power_source == "ac" and battery_level < 100.0:
        charging_watts = round(45.0 * max(0.05, 1.0 - (battery_level / 100.0)), 2)
    else:
        charging_watts = 0.0
        
    total_power_draw = round(base_watts + cpu_watts + gpu_watts + aux_watts + charging_watts, 2)

    # 3. Battery Impact Calculations
    total_wh = 56.0
    health_factor = max(10.0, min(100.0, battery_health)) / 100.0
    eff_capacity_wh = total_wh * health_factor
    
    if power_source == "battery":
        battery_status = "discharging"
        component_watts = base_watts + cpu_watts + gpu_watts + aux_watts
        drain_rate = round((component_watts / eff_capacity_wh) * 100.0, 2)
        charge_rate = 0.0
        
        remaining_wh = (battery_level / 100.0) * eff_capacity_wh
        remaining_minutes = round((remaining_wh / component_watts) * 60.0, 1) if component_watts > 0 else 0.0
        battery_temp = round(28.0 + 3.0 * (total_power_draw / 60.0), 1)
    else:
        battery_status = "charging" if battery_level < 100.0 else "full"
        drain_rate = 0.0
        charge_rate = round((charging_watts / eff_capacity_wh) * 100.0, 2) if battery_level < 100.0 else 0.0
        
        if battery_level < 100.0 and charging_watts > 0:
            wh_to_charge = ((100.0 - battery_level) / 100.0) * eff_capacity_wh
            remaining_minutes = round((wh_to_charge / charging_watts) * 60.0, 1)
        else:
            remaining_minutes = 0.0
        battery_temp = round(30.0 + 5.0 * (total_power_draw / 60.0), 1)

    return {
        "temperature": {
            "cpu_temperature": t_steady,
            "fan_speed_rpm": rpm,
            "thermal_state": thermal_state,
            "is_throttling": is_throttling,
            "throttle_ratio": round(throttle_ratio, 2)
        },
        "power": {
            "total_power_draw_watts": total_power_draw,
            "cpu_power_draw_watts": cpu_watts,
            "gpu_power_draw_watts": gpu_watts,
            "aux_power_draw_watts": aux_watts,
            "base_power_draw_watts": base_watts,
            "charging_power_draw_watts": charging_watts
        },
        "battery": {
            "battery_status": battery_status,
            "battery_drain_rate_percent_per_hour": drain_rate,
            "battery_charge_rate_percent_per_hour": charge_rate,
            "battery_remaining_minutes": remaining_minutes,
            "battery_temperature": battery_temp
        }
    }
