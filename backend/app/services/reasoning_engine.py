import logging
from typing import Any, Dict, List, Optional
import uuid
from sqlalchemy.orm import Session
from datetime import datetime

from app.models.telemetry import TelemetrySnapshot
from app.models.reasoning import ReasoningRule
from app.core.logging import logger

def get_metric_value(snapshot: TelemetrySnapshot, metric: str) -> Any:
    """
    Extract a telemetry metric value from a TelemetrySnapshot.
    Supports both dotted paths (e.g. 'cpu.cpu_usage') and flat metric names (e.g. 'cpu_usage').
    """
    if not snapshot:
        return None

    # 1. Dotted path lookup
    if "." in metric:
        parts = metric.split(".")
        obj = snapshot
        for part in parts:
            if obj is None:
                return None
            obj = getattr(obj, part, None)
        return obj

    # 2. Flat lookup mapping
    flat_map = {
        "cpu_usage": lambda s: s.cpu.cpu_usage if s.cpu else None,
        "active_process_count": lambda s: s.cpu.active_process_count if s.cpu else None,
        "cpu_frequency_mhz": lambda s: s.cpu.cpu_frequency_mhz if s.cpu else None,
        "gpu_usage": lambda s: s.gpu.gpu_usage if s.gpu else None,
        "gpu_temperature": lambda s: s.gpu.gpu_temperature if s.gpu else None,
        "gpu_memory_usage": lambda s: s.gpu.gpu_memory_usage if s.gpu else None,
        "memory_usage": lambda s: s.memory.memory_usage if s.memory else None,
        "battery_level": lambda s: s.battery.battery_level if s.battery else None,
        "battery_health": lambda s: s.battery.battery_health if s.battery else None,
        "battery_temperature": lambda s: s.battery.battery_temperature if s.battery else None,
        "cycle_count": lambda s: s.battery.cycle_count if s.battery else None,
        "disk_usage": lambda s: s.disk.disk_usage if s.disk else None,
        "read_bytes_sec": lambda s: s.disk.read_bytes_sec if s.disk else None,
        "write_bytes_sec": lambda s: s.disk.write_bytes_sec if s.disk else None,
        "signal_strength_dbm": lambda s: s.wifi.signal_strength_dbm if s.wifi else None,
        "ssid": lambda s: s.wifi.ssid if s.wifi else None,
        "link_speed_mbps": lambda s: s.wifi.link_speed_mbps if s.wifi else None,
        "cpu_temperature": lambda s: s.thermal.cpu_temperature if s.thermal else None,
        "fan_speed": lambda s: s.thermal.fan_speed_rpm if s.thermal else None,
        "fan_speed_rpm": lambda s: s.thermal.fan_speed_rpm if s.thermal else None,
        "thermal_state": lambda s: s.thermal.thermal_state if s.thermal else None,
        "power_source": lambda s: s.power.power_source if s.power else None,
        "power_draw_watts": lambda s: s.power.power_draw_watts if s.power else None,
        "voltage_mv": lambda s: s.power.voltage_mv if s.power else None,
        "health_score": lambda s: s.health_score
    }

    if metric in flat_map:
        return flat_map[metric](snapshot)

    # 3. Direct attribute fallback
    return getattr(snapshot, metric, None)


def format_metric_display_name(metric: str) -> str:
    """Format a metric name to a human-readable title."""
    # Strip prefixes like "cpu." or "thermal."
    name = metric.split(".")[-1] if "." in metric else metric
    return name.replace("_", " ").title()


def compare_values(actual: Any, operator: str, threshold: Any) -> bool:
    """
    Compare actual telemetry value against a threshold value using the given operator.
    Handles numeric conversion and string comparisons gracefully.
    """
    if actual is None:
        return False

    try:
        # For string comparison, strip and lowercase
        if operator == "==":
            try:
                return float(actual) == float(threshold)
            except (ValueError, TypeError):
                return str(actual).strip().lower() == str(threshold).strip().lower()

        elif operator == "!=":
            try:
                return float(actual) != float(threshold)
            except (ValueError, TypeError):
                return str(actual).strip().lower() != str(threshold).strip().lower()

        # Numeric operators
        actual_num = float(actual)
        threshold_num = float(threshold)

        if operator == ">":
            return actual_num > threshold_num
        elif operator == "<":
            return actual_num < threshold_num
        elif operator == ">=":
            return actual_num >= threshold_num
        elif operator == "<=":
            return actual_num <= threshold_num

    except Exception as e:
        logger.error(f"Error evaluating condition ({actual} {operator} {threshold}): {str(e)}")
        return False

    return False


def evaluate_rule(snapshot: TelemetrySnapshot, rule: ReasoningRule) -> Dict[str, Any]:
    """
    Evaluate a single ReasoningRule against a TelemetrySnapshot.
    Returns an evaluation result dict containing:
      - rule_id (str)
      - rule_name (str)
      - triggered (bool)
      - explanation (str) (Detailed natural-language reason with evidence)
      - evidence (dict) (Map of metric to actual value)
      - severity (str)
    """
    conditions = rule.conditions
    logical_operator = rule.logical_operator.upper() if rule.logical_operator else "AND"

    evidence = {}
    condition_results = []
    condition_explanations = []

    for cond in conditions:
        metric = cond.get("metric")
        operator = cond.get("operator")
        threshold = cond.get("value")

        actual_val = get_metric_value(snapshot, metric)
        evidence[metric] = actual_val

        # Evaluate condition
        matched = compare_values(actual_val, operator, threshold)
        condition_results.append(matched)

        # Form description for this condition
        m_name = format_metric_display_name(metric)
        if actual_val is None:
            explanation = f"{m_name} is missing or unavailable (threshold: {operator} {threshold})"
        else:
            # Format value displays nicely
            val_str = f"{actual_val:.1f}" if isinstance(actual_val, float) else str(actual_val)
            explanation = f"{m_name} is {val_str} (threshold: {operator} {threshold})"
        
        condition_explanations.append((matched, explanation))

    # Combine results based on logical operator
    if logical_operator == "OR":
        triggered = any(condition_results)
    else: # Default is AND
        triggered = all(condition_results)

    # Compile natural language explanation
    explanation_parts = []
    for matched, desc in condition_explanations:
        status = "MET" if matched else "NOT MET"
        explanation_parts.append(f"{desc} [{status}]")

    explanation_list = " and ".join(f"'{desc}'" for _, desc in condition_explanations)
    
    if triggered:
        if logical_operator == "OR":
            triggered_conds = [desc for matched, desc in condition_explanations if matched]
            explanation = (
                f"Rule '{rule.name}' triggered because at least one condition was met: "
                f"{', '.join(triggered_conds)}. Conclusion: {rule.conclusion}."
            )
        else:
            explanation = (
                f"Rule '{rule.name}' triggered because all conditions were met: "
                f"{', '.join(desc for _, desc in condition_explanations)}. Conclusion: {rule.conclusion}."
            )
    else:
        if logical_operator == "OR":
            explanation = (
                f"Rule '{rule.name}' did not trigger because none of the conditions were met: "
                f"{', '.join(desc for _, desc in condition_explanations)}."
            )
        else:
            failed_conds = [desc for matched, desc in condition_explanations if not matched]
            explanation = (
                f"Rule '{rule.name}' did not trigger because some conditions were not met: "
                f"{', '.join(failed_conds)}."
            )

    return {
        "rule_id": rule.id,
        "rule_name": rule.name,
        "triggered": triggered,
        "explanation": explanation,
        "evidence": evidence,
        "severity": rule.severity
    }


def evaluate_all_rules(snapshot: TelemetrySnapshot, db: Session) -> List[Dict[str, Any]]:
    """
    Evaluate all active ReasoningRules against the given TelemetrySnapshot.
    """
    # Ensure rules exist (seed if database is empty)
    seed_default_rules_if_empty(db)

    rules = db.query(ReasoningRule).filter(ReasoningRule.is_active == True).all()
    results = []
    for rule in rules:
        results.append(evaluate_rule(snapshot, rule))
    return results


def seed_default_rules_if_empty(db: Session):
    """
    Seeds default rules if the reasoning_rules table is empty.
    """
    count = db.query(ReasoningRule).count()
    if count > 0:
        return

    logger.info("Reasoning rules table is empty. Seeding default rules...")
    default_rules = [
        ReasoningRule(
            id="rule-thermal-stress",
            name="Thermal Stress Detection",
            description="Triggers when CPU load is high and temperature is hot.",
            conditions=[
                {"metric": "cpu_usage", "operator": ">", "value": 80.0},
                {"metric": "cpu_temperature", "operator": ">", "value": 85.0}
            ],
            logical_operator="AND",
            conclusion="Thermal Stress",
            severity="critical",
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        ),
        ReasoningRule(
            id="rule-system-overload",
            name="System Overload",
            description="Triggers when both CPU and memory usages are extremely high.",
            conditions=[
                {"metric": "cpu_usage", "operator": ">", "value": 90.0},
                {"metric": "memory_usage", "operator": ">", "value": 85.0}
            ],
            logical_operator="AND",
            conclusion="System Overload",
            severity="critical",
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        ),
        ReasoningRule(
            id="rule-eco-warning",
            name="Low Battery AC Recommendation",
            description="Triggers when battery is low and running on battery power.",
            conditions=[
                {"metric": "battery_level", "operator": "<", "value": 20.0},
                {"metric": "power_source", "operator": "==", "value": "battery"}
            ],
            logical_operator="AND",
            conclusion="Low Power Mode Recommended",
            severity="warning",
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        ),
        ReasoningRule(
            id="rule-unstable-wifi",
            name="Weak WiFi Connection",
            description="Triggers when signal strength is very weak.",
            conditions=[
                {"metric": "signal_strength_dbm", "operator": "<", "value": -80.0}
            ],
            logical_operator="AND",
            conclusion="Weak WiFi Connection",
            severity="warning",
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
    ]

    try:
        db.add_all(default_rules)
        db.commit()
        logger.info("Seeded 4 default reasoning rules successfully.")
    except Exception as e:
        db.rollback()
        logger.error(f"Error seeding default rules: {str(e)}")
