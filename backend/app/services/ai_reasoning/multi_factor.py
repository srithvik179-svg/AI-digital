from typing import Dict, Any, List

class MultiFactorReasoning:
    """
    Phase 23: Multi-Factor Reasoning Engine
    Evaluates complex hardware states by correlating multiple metric dimensions
    and outputs a normalized System Stress Index (0-100) and specific diagnosed states.
    """
    def __init__(self):
        pass

    def analyze(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        # Extract metrics with safe defaults
        cpu_usage = float(metrics.get("cpu_usage", 0.0))
        cpu_temp = float(metrics.get("cpu_temperature", 0.0))
        gpu_usage = float(metrics.get("gpu_usage", 0.0))
        gpu_temp = float(metrics.get("gpu_temperature", 0.0))
        battery_level = float(metrics.get("battery_level", 100.0))
        power_source = str(metrics.get("power_source", "AC")).lower()
        fan_rpm = float(metrics.get("fan_rpm", 0.0))
        memory_usage = float(metrics.get("memory_usage", 0.0))
        wifi_signal = float(metrics.get("wifi_signal", -50.0))

        diagnoses = []
        
        # 1. Workload Thermal Coupling
        # CPU/GPU high workload combined with high temperatures
        if cpu_usage > 70.0 and cpu_temp > 80.0:
            diagnoses.append({
                "condition": "Workload Thermal Coupling",
                "severity": "CRITICAL" if cpu_temp > 90.0 else "WARNING",
                "evidence": f"CPU Usage at {cpu_usage:.1f}% coupled with CPU Temp at {cpu_temp:.1f}°C.",
                "confidence": min(100.0, float(max(50.0, (cpu_usage + cpu_temp) / 2.0)))
            })
        
        # 2. Power Draw Stress
        # High CPU/GPU load while running on battery
        if (cpu_usage > 75.0 or gpu_usage > 75.0) and power_source == "battery":
            diagnoses.append({
                "condition": "Power Draw Stress",
                "severity": "WARNING" if battery_level > 20.0 else "CRITICAL",
                "evidence": f"High computing load (CPU {cpu_usage:.1f}%, GPU {gpu_usage:.1f}%) on Battery ({battery_level:.1f}% remaining).",
                "confidence": min(100.0, float(max(60.0, (cpu_usage + (100.0 - battery_level)) / 2.0)))
            })

        # 3. Thermodynamic Inefficiency
        # Fan RPM is maxed out but CPU/GPU temperatures are still high
        if fan_rpm > 4500.0 and cpu_temp > 78.0:
            diagnoses.append({
                "condition": "Thermodynamic Inefficiency",
                "severity": "CRITICAL" if cpu_temp > 85.0 else "WARNING",
                "evidence": f"Cooling fan active at high speed ({fan_rpm:.0f} RPM) yet CPU temperature remains elevated at {cpu_temp:.1f}°C.",
                "confidence": min(100.0, float(max(50.0, (fan_rpm / 60.0 + cpu_temp) / 2.0)))
            })

        # 4. Critical Battery Wear Under Load
        if battery_level < 15.0 and cpu_usage > 60.0 and power_source == "battery":
            diagnoses.append({
                "condition": "Low Battery Thermal Throttling Risk",
                "severity": "CRITICAL",
                "evidence": f"Battery critically low ({battery_level:.1f}%) under high CPU load ({cpu_usage:.1f}%).",
                "confidence": 90.0
            })

        # 5. Network Reception Degradation under high WiFi throughput
        if wifi_signal < -78.0:
            diagnoses.append({
                "condition": "Network Link Quality Degradation",
                "severity": "WARNING",
                "evidence": f"WiFi Signal strength is weak at {wifi_signal:.1f} dBm.",
                "confidence": min(100.0, float(abs(wifi_signal)))
            })

        # System Stress Index Calculation (Fuzzy multi-factor weighting)
        # We compute membership scores (0 to 1) for various stressors
        cpu_stress = min(1.0, cpu_usage / 100.0)
        thermal_stress = min(1.0, max(0.0, (cpu_temp - 40.0) / 55.0)) # 40C to 95C
        memory_stress = min(1.0, memory_usage / 100.0)
        
        # If on battery and load is high, power stress is higher
        power_stress = 0.0
        if power_source == "battery":
            power_stress = min(1.0, max(0.0, (cpu_usage + (100.0 - battery_level)) / 200.0))
        
        # Weighted aggregate stress index
        weighted_stress = (cpu_stress * 0.35) + (thermal_stress * 0.35) + (memory_stress * 0.15) + (power_stress * 0.15)
        system_stress_index = round(weighted_stress * 100.0, 1)

        return {
            "system_stress_index": system_stress_index,
            "diagnoses": diagnoses
        }
