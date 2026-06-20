from typing import Dict, Any, List

class RecommendationEngine:
    """
    Phase 24: Recommendation Engine
    Generates actionable system optimization recommendations with estimated
    thermodynamic benefits (cooling, battery runtime extension) based on active states.
    """
    def __init__(self):
        pass

    def generate_recommendations(self, metrics: Dict[str, Any], diagnoses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        cpu_usage = float(metrics.get("cpu_usage", 0.0))
        cpu_temp = float(metrics.get("cpu_temperature", 0.0))
        power_source = str(metrics.get("power_source", "AC")).lower()
        battery_level = float(metrics.get("battery_level", 100.0))
        fan_rpm = float(metrics.get("fan_rpm", 0.0))

        recommendations = []

        # 1. Background Process Suspension
        if cpu_usage > 60.0 or cpu_temp > 75.0:
            # Estimate thermal cooling benefit: Delta T = 0.15 * delta_cpu
            # Let's say we can reduce CPU usage by 25% by closing background processes
            cpu_reduction = min(25.0, cpu_usage - 10.0)
            cooling_benefit = round(0.18 * cpu_reduction, 1)
            
            # Estimate battery extension benefit:
            battery_extension_mins = 0
            if power_source == "battery":
                # Extends battery: more battery left, more absolute minutes saved
                battery_extension_mins = int(0.6 * cpu_reduction * (battery_level / 100.0) * 15.0)
                battery_extension_mins = max(5, battery_extension_mins)

            rec = {
                "action": "Terminate High-CPU Background Processes",
                "trigger": "Elevated CPU workload / temperature",
                "estimated_cooling_c": cooling_benefit,
                "estimated_battery_extension_mins": battery_extension_mins,
                "description": f"Identify and close background applications consuming high CPU cycles. This is expected to cool your CPU by {cooling_benefit}°C" + 
                               (f" and extend battery life by approximately {battery_extension_mins} minutes." if battery_extension_mins > 0 else "."),
                "priority": "HIGH" if cpu_temp > 85.0 else "MEDIUM"
            }
            recommendations.append(rec)

        # 2. Adjust Fan Speed Profile to Performance/Turbo
        if cpu_temp > 75.0 and fan_rpm < 4500.0:
            # Increasing fan RPM is estimated to cool by 5-10°C, but drains slightly more battery
            cooling_benefit = round(0.1 * (5000.0 - fan_rpm) / 100.0, 1)
            cooling_benefit = max(2.0, min(8.0, cooling_benefit))
            
            battery_cost_mins = 0
            if power_source == "battery":
                battery_cost_mins = max(1, int(battery_level * 0.05))

            rec = {
                "action": "Increase Fan Speed Profile (Performance/Turbo)",
                "trigger": "CPU core temperature above nominal threshold with under-utilized cooling capacity",
                "estimated_cooling_c": cooling_benefit,
                "estimated_battery_extension_mins": -battery_cost_mins,
                "description": f"Increase cooling fan velocity to optimize thermal dissipation. Expected to cool active components by {cooling_benefit}°C" + 
                               (f" (with a minor trade-off of -{battery_cost_mins} minutes of battery runtime)." if battery_cost_mins > 0 else "."),
                "priority": "HIGH" if cpu_temp > 82.0 else "MEDIUM"
            }
            recommendations.append(rec)

        # 3. Enable Eco Mode / Thermal Cap
        if power_source == "battery" or cpu_temp > 80.0:
            cooling_benefit = 6.5 if cpu_temp > 80.0 else 3.0
            battery_extension_mins = int((100.0 - cpu_usage / 2.0) * (battery_level / 100.0) * 0.5 + 15) if power_source == "battery" else 0

            rec = {
                "action": "Activate System Eco/Power-Saver Mode",
                "trigger": "System running on battery power or experiencing thermal stress",
                "estimated_cooling_c": cooling_benefit,
                "estimated_battery_extension_mins": battery_extension_mins,
                "description": "Applies a frequency multiplier cap to CPU and limits background telemetry logging. " +
                               f"Will lower temperature by {cooling_benefit}°C" +
                               (f" and extend battery by {battery_extension_mins} minutes." if battery_extension_mins > 0 else "."),
                "priority": "HIGH" if (power_source == "battery" and battery_level < 30.0) or cpu_temp > 88.0 else "MEDIUM"
            }
            recommendations.append(rec)

        # 4. Dim Screen Brightness
        if power_source == "battery" and battery_level < 50.0:
            battery_extension_mins = int((battery_level / 100.0) * 25.0 + 5)
            rec = {
                "action": "Reduce Display Brightness to 50%",
                "trigger": "Battery level below 50% on active discharge",
                "estimated_cooling_c": 0.5,
                "estimated_battery_extension_mins": battery_extension_mins,
                "description": f"Dimming the display reduces backlight power draw, extending remaining battery run-time by {battery_extension_mins} minutes.",
                "priority": "LOW" if battery_level > 20.0 else "MEDIUM"
            }
            recommendations.append(rec)

        # Sort recommendations by priority (HIGH -> MEDIUM -> LOW)
        priority_map = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        recommendations.sort(key=lambda r: priority_map.get(r["priority"], 3))

        return recommendations
