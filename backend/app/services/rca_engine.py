from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from datetime import datetime

from app.models.telemetry import TelemetrySnapshot
from app.models.alert import TelemetryAlert
from app.models.relationship import TelemetryRelationship
from app.services.alert_engine import evaluate_alerts
from app.core.logging import logger

def get_snapshot_alerts(snapshot: TelemetrySnapshot, db: Session) -> List[Dict[str, Any]]:
    """
    Fetch alerts associated with a snapshot. If not found in the database,
    evaluates rules on-the-fly.
    """
    # 1. Try querying the database
    alerts = db.query(TelemetryAlert).filter(TelemetryAlert.snapshot_id == snapshot.id).all()
    if alerts:
        return [
            {
                "rule_id": a.rule_id,
                "category": a.category,
                "severity": a.severity,
                "message": a.message,
                "metric_name": a.metric_name,
                "metric_value": a.metric_value,
                "threshold_value": a.threshold_value,
            }
            for a in alerts
        ]

    # 2. Evaluate on-the-fly if not stored
    evaluated = evaluate_alerts(
        cpu_temperature=snapshot.thermal.cpu_temperature if snapshot.thermal else 45.0,
        battery_level=snapshot.battery.battery_level if snapshot.battery else 100.0,
        battery_health=snapshot.battery.battery_health if snapshot.battery else 100.0,
        disk_usage=snapshot.disk.disk_usage if snapshot.disk else 0.0,
        gpu_temperature=snapshot.gpu.gpu_temperature if snapshot.gpu else None,
        battery_temperature=snapshot.battery.battery_temperature if snapshot.battery else None,
        cycle_count=snapshot.battery.cycle_count if snapshot.battery else None,
        write_bytes_sec=snapshot.disk.write_bytes_sec if snapshot.disk else None,
        signal_strength_dbm=snapshot.wifi.signal_strength_dbm if snapshot.wifi else None,
        link_speed_mbps=snapshot.wifi.link_speed_mbps if snapshot.wifi else None,
        thermal_state=snapshot.thermal.thermal_state if snapshot.thermal else None,
        power_source=snapshot.power.power_source if snapshot.power else "ac",
        device_id=snapshot.device_id,
        snapshot_id=snapshot.id,
    )
    return [
        {
            "rule_id": a.rule_id,
            "category": a.category,
            "severity": a.severity,
            "message": a.message,
            "metric_name": a.metric_name,
            "metric_value": a.metric_value,
            "threshold_value": a.threshold_value,
        }
        for a in evaluated
    ]


def run_dependency_graph_rca(
    active_metrics: List[str], 
    device_id: str, 
    db: Session
) -> Dict[str, float]:
    """
    Traverses the correlation dependency graph to rank root causes.
    If metric A influences metric B and both are alerted, A gets a higher causal score.
    Returns a dictionary of metrics mapped to their causal strength scores.
    """
    if len(active_metrics) <= 1:
        return {m: 1.0 for m in active_metrics}

    # Fetch relationship paths for this device
    relationships = (
        db.query(TelemetryRelationship)
        .filter(
            TelemetryRelationship.device_id == device_id,
            TelemetryRelationship.source_node.in_(active_metrics),
            TelemetryRelationship.target_node.in_(active_metrics)
        )
        .all()
    )

    # Initialize score map
    # Base score of 1.0 for all alerted metrics
    scores = {m: 1.0 for m in active_metrics}

    for rel in relationships:
        src = rel.source_node
        tgt = rel.target_node
        weight = abs(rel.correlation_strength)

        # Source gets causal boost, target gets reduced (symptomatic)
        scores[src] += weight
        scores[tgt] = max(0.1, scores[tgt] - (weight * 0.5))

    return scores


def run_rca_analysis(snapshot: TelemetrySnapshot, db: Session) -> List[Dict[str, Any]]:
    """
    Orchestrates the Decision Tree and Dependency Graph RCA algorithms.
    Returns ranked root cause diagnoses.
    """
    # 1. Fetch active alerts
    alerts = get_snapshot_alerts(snapshot, db)
    
    if not alerts:
        return [{
            "cause": "Normal Operation",
            "confidence": 1.0,
            "evidence": ["No active telemetry alerts detected."],
            "remedy": "System is running healthy. No action required.",
            "path": ["System Nominal Check"]
        }]

    # Collect unique metrics that have alerts
    alerted_metrics = list(set(a["metric_name"] for a in alerts if a["metric_name"]))

    # 2. Run Causal Graph traversal
    causal_scores = run_dependency_graph_rca(alerted_metrics, snapshot.device_id, db)

    diagnoses = []
    
    # 3. Decision Tree checks
    # Profile A: CPU Overheating / Thermal Stress
    thermal_alerts = [a for a in alerts if a["category"] == "Overheating"]
    if thermal_alerts:
        cpu_temp = snapshot.thermal.cpu_temperature if snapshot.thermal else 0.0
        fan_speed = snapshot.thermal.fan_speed_rpm if snapshot.thermal else 0
        cpu_usage = snapshot.cpu.cpu_usage if snapshot.cpu else 0.0

        evidence = [f"CPU Temp is {cpu_temp:.1f}°C"]
        path = ["Thermal Profile Check"]

        # Decision Tree logic
        if fan_speed < 1500:
            cause = "Cooling Fan Mechanical Failure"
            confidence = 0.90
            remedy = "Verify if cooling fans are physically blocked or failing. Replace cooling module if necessary."
            path.append("Fan Speed < 1500 RPM")
            evidence.append(f"Fan Speed is critically low ({fan_speed} RPM)")
        elif cpu_usage > 75.0:
            cause = "CPU Workload Storm"
            confidence = 0.85
            remedy = "Review active tasks. Terminate high load processes or applications in the background."
            path.append("Fan Speed Operational -> CPU Load > 75%")
            evidence.append(f"CPU Load is elevated ({cpu_usage:.1f}%)")
        else:
            cause = "Ventilation Obstruction or Pasting Wear"
            confidence = 0.70
            remedy = "Ensure laptop vents are free of dust or obstructions. Thermal paste replacement may be needed."
            path.append("Fan Speed Operational -> CPU Load Normal")
            evidence.append(f"CPU Load is normal ({cpu_usage:.1f}%)")

        # Causal graph boost
        # If cpu_usage is also alerted and acts as a strong graph source, boost confidence
        if "cpu_usage" in causal_scores and causal_scores["cpu_usage"] > 1.2:
            confidence = min(0.98, confidence + 0.1)
            path.append(f"Graph causal source 'cpu_usage' confirmed (strength {causal_scores['cpu_usage']:.2f})")

        diagnoses.append({
            "cause": cause,
            "confidence": round(confidence, 2),
            "evidence": evidence,
            "remedy": remedy,
            "path": path
        })

    # Profile B: Battery Stress
    battery_alerts = [a for a in alerts if a["category"] == "Battery"]
    if battery_alerts:
        bat_level = snapshot.battery.battery_level if snapshot.battery else 100.0
        bat_health = snapshot.battery.battery_health if snapshot.battery else 100.0
        bat_temp = snapshot.battery.battery_temperature if snapshot.battery else 25.0
        power_draw = snapshot.power.power_draw_watts if snapshot.power else 0.0

        evidence = [f"Battery level is {bat_level:.1f}%"]
        path = ["Battery Profile Check"]

        if bat_health < 75.0:
            cause = "Battery Cell Degradation"
            confidence = 0.95
            remedy = "Battery health is degraded. Schedule a physical battery replacement to restore normal capacity."
            path.append("Battery Health < 75%")
            evidence.append(f"Battery Health is degraded ({bat_health:.1f}%)")
        elif power_draw > 22.0:
            cause = "Excessive Computational Power Draw"
            confidence = 0.80
            remedy = "Reduce screen brightness, close computational tasks, and disconnect unnecessary external peripherals."
            path.append("Battery Health Normal -> Power Draw > 22W")
            evidence.append(f"System Power Draw is high ({power_draw:.1f}W)")
        elif bat_temp > 40.0:
            cause = "Thermal Induced Battery Degradation"
            confidence = 0.85
            remedy = "Move device to a cooler environment and stop heavy processing. High thermals degrade lithium cells."
            path.append("Battery Health Normal -> Battery Temp > 40°C")
            evidence.append(f"Battery Temp is high ({bat_temp:.1f}°C)")
        else:
            cause = "Normal Charge Depletion"
            confidence = 0.60
            remedy = "Connect the laptop to an AC power outlet to prevent automatic shutdown."
            path.append("Battery Discharge Normal")

        # Graph boost
        if "power_draw_watts" in causal_scores and causal_scores["power_draw_watts"] > 1.2:
            confidence = min(0.98, confidence + 0.1)
            path.append("Graph causal source 'power_draw_watts' confirmed")

        diagnoses.append({
            "cause": cause,
            "confidence": round(confidence, 2),
            "evidence": evidence,
            "remedy": remedy,
            "path": path
        })

    # Profile C: Network Dropouts
    wifi_alerts = [a for a in alerts if a["category"] == "Network"]
    if wifi_alerts:
        rssi = snapshot.wifi.signal_strength_dbm if snapshot.wifi else 0
        speed = snapshot.wifi.link_speed_mbps if snapshot.wifi else 0

        evidence = [f"WiFi Signal RSSI is {rssi} dBm"]
        path = ["WiFi Profile Check"]

        if speed < 20:
            cause = "Extreme Distance or RF Path Blocking"
            confidence = 0.85
            remedy = "Move closer to the router or remove structural obstacles blocking wireless line-of-sight."
            path.append("Link Speed < 20 Mbps")
            evidence.append(f"WiFi Link Speed is critically slow ({speed} Mbps)")
        else:
            cause = "Wireless Congestion or Interference"
            confidence = 0.70
            remedy = "Reboot wireless router or configure router to broadcast on a less congested frequency (e.g. 5GHz band)."
            path.append("Link Speed Operational")
            evidence.append(f"WiFi Link Speed is normal ({speed} Mbps)")

        diagnoses.append({
            "cause": cause,
            "confidence": round(confidence, 2),
            "evidence": evidence,
            "remedy": remedy,
            "path": path
        })

    # Profile D: Disk Write Storm
    disk_alerts = [a for a in alerts if a["category"] == "Disk"]
    if disk_alerts:
        usage = snapshot.disk.disk_usage if snapshot.disk else 0.0
        write_speed = snapshot.disk.write_bytes_sec if snapshot.disk else 0

        evidence = []
        path = ["Disk Profile Check"]

        if write_speed > 80_000_000:
            cause = "Runaway Write Storm / Database Lock"
            confidence = 0.85
            remedy = "Identify and suspend process performing heavy write operations (e.g. database loops, logs dumps)."
            path.append("Disk Write Speed > 80 MB/s")
            evidence.append(f"Disk Write Rate is high ({write_speed / (1024*1024):.1f} MB/s)")
        else:
            cause = "Disk Space Exhaustion"
            confidence = 0.90
            remedy = "Use disk cleanup tool to delete temporary logs, clear download folders, and empty trash bin."
            path.append("Disk Space Critical")
            evidence.append(f"Disk Capacity is {usage:.1f}% full")

        diagnoses.append({
            "cause": cause,
            "confidence": round(confidence, 2),
            "evidence": evidence,
            "remedy": remedy,
            "path": path
        })

    # Sort diagnoses by confidence descending
    diagnoses.sort(key=lambda d: d["confidence"], reverse=True)
    return diagnoses
