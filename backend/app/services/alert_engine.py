"""
Alert Detection Engine — Phase 6
Rule-based system that detects anomalies in telemetry snapshots.

Alert categories:
  - Overheating   (CPU/GPU temperature, thermal state)
  - Battery       (low charge, degraded health, high cycle count, temp)
  - Disk          (high fill %, sustained write storm)
  - Network       (weak WiFi signal, low link speed)

Every rule is a dataclass with an explicit threshold so the formula is
easy to audit and tune. Rules fire independently — one snapshot can
produce multiple alerts.

Severity levels:
  INFO     — informational, no action required
  WARNING  — attention needed soon
  CRITICAL — action required now
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List
import uuid

__all__ = ["evaluate_alerts", "Alert", "AlertSeverity", "AlertCategory"]

# ── Constants ──────────────────────────────────────────────────────────
class AlertSeverity:
    INFO     = "Info"
    WARNING  = "Warning"
    CRITICAL = "Critical"

class AlertCategory:
    OVERHEATING = "Overheating"
    BATTERY     = "Battery"
    DISK        = "Disk"
    NETWORK     = "Network"


# ── Alert dataclass ────────────────────────────────────────────────────
@dataclass
class Alert:
    id: str
    rule_id: str
    category: str
    severity: str
    message: str
    metric_name: str
    metric_value: float
    threshold_value: float
    triggered_at: datetime = field(default_factory=datetime.utcnow)
    device_id: str = ""
    snapshot_id: str = ""


# ── Rule registry ──────────────────────────────────────────────────────
@dataclass
class Rule:
    rule_id: str
    category: str
    severity: str
    metric_name: str
    threshold: float
    message_template: str   # supports {value:.1f} and {threshold}


# All active rules (ordered: Critical before Warning within each category)
RULES: List[Rule] = [

    # ── OVERHEATING ──────────────────────────────────────────────────
    Rule(
        rule_id="cpu_temp_critical",
        category=AlertCategory.OVERHEATING,
        severity=AlertSeverity.CRITICAL,
        metric_name="cpu_temperature",
        threshold=88.0,
        message_template="CPU temperature is critically high at {value:.1f}°C (threshold {threshold}°C). Risk of thermal throttling or hardware damage.",
    ),
    Rule(
        rule_id="cpu_temp_warning",
        category=AlertCategory.OVERHEATING,
        severity=AlertSeverity.WARNING,
        metric_name="cpu_temperature",
        threshold=75.0,
        message_template="CPU temperature elevated at {value:.1f}°C (threshold {threshold}°C). Check ventilation and clean cooling fans.",
    ),
    Rule(
        rule_id="gpu_temp_critical",
        category=AlertCategory.OVERHEATING,
        severity=AlertSeverity.CRITICAL,
        metric_name="gpu_temperature",
        threshold=90.0,
        message_template="GPU temperature is critically high at {value:.1f}°C (threshold {threshold}°C). Reduce GPU workload immediately.",
    ),
    Rule(
        rule_id="gpu_temp_warning",
        category=AlertCategory.OVERHEATING,
        severity=AlertSeverity.WARNING,
        metric_name="gpu_temperature",
        threshold=80.0,
        message_template="GPU temperature elevated at {value:.1f}°C (threshold {threshold}°C). Monitor GPU-intensive applications.",
    ),

    # ── BATTERY ──────────────────────────────────────────────────────
    Rule(
        rule_id="battery_level_critical",
        category=AlertCategory.BATTERY,
        severity=AlertSeverity.CRITICAL,
        metric_name="battery_level",
        threshold=10.0,
        message_template="Battery critically low at {value:.1f}% (threshold {threshold}%). Connect to power immediately to avoid shutdown.",
    ),
    Rule(
        rule_id="battery_level_warning",
        category=AlertCategory.BATTERY,
        severity=AlertSeverity.WARNING,
        metric_name="battery_level",
        threshold=20.0,
        message_template="Battery level low at {value:.1f}% (threshold {threshold}%). Consider connecting to power soon.",
    ),
    Rule(
        rule_id="battery_health_critical",
        category=AlertCategory.BATTERY,
        severity=AlertSeverity.CRITICAL,
        metric_name="battery_health",
        threshold=60.0,
        message_template="Battery health critically degraded at {value:.1f}% (threshold {threshold}%). Battery replacement is strongly recommended.",
    ),
    Rule(
        rule_id="battery_health_warning",
        category=AlertCategory.BATTERY,
        severity=AlertSeverity.WARNING,
        metric_name="battery_health",
        threshold=80.0,
        message_template="Battery health degraded at {value:.1f}% (threshold {threshold}%). Schedule a battery replacement.",
    ),
    Rule(
        rule_id="battery_cycle_warning",
        category=AlertCategory.BATTERY,
        severity=AlertSeverity.WARNING,
        metric_name="cycle_count",
        threshold=800.0,
        message_template="Battery cycle count is {value:.0f} (threshold {threshold:.0f}). Battery may be approaching end of lifespan.",
    ),
    Rule(
        rule_id="battery_temp_warning",
        category=AlertCategory.BATTERY,
        severity=AlertSeverity.WARNING,
        metric_name="battery_temperature",
        threshold=40.0,
        message_template="Battery temperature elevated at {value:.1f}°C (threshold {threshold}°C). Avoid heavy charging in hot environments.",
    ),

    # ── DISK ─────────────────────────────────────────────────────────
    Rule(
        rule_id="disk_usage_critical",
        category=AlertCategory.DISK,
        severity=AlertSeverity.CRITICAL,
        metric_name="disk_usage",
        threshold=92.0,
        message_template="Disk usage critically high at {value:.1f}% (threshold {threshold}%). Free up storage immediately to prevent system failures.",
    ),
    Rule(
        rule_id="disk_usage_warning",
        category=AlertCategory.DISK,
        severity=AlertSeverity.WARNING,
        metric_name="disk_usage",
        threshold=80.0,
        message_template="Disk usage high at {value:.1f}% (threshold {threshold}%). Review and remove unnecessary files.",
    ),
    Rule(
        rule_id="disk_write_storm",
        category=AlertCategory.DISK,
        severity=AlertSeverity.WARNING,
        metric_name="write_bytes_sec",
        threshold=100_000_000.0,   # 100 MB/s
        message_template="Sustained disk write rate is {value:,.0f} B/s (threshold {threshold:,.0f} B/s). Check for runaway backup or logging process.",
    ),

    # ── NETWORK ──────────────────────────────────────────────────────
    Rule(
        rule_id="wifi_signal_critical",
        category=AlertCategory.NETWORK,
        severity=AlertSeverity.CRITICAL,
        metric_name="signal_strength_dbm",
        threshold=-85.0,
        message_template="WiFi signal critically weak at {value:.0f} dBm (threshold {threshold:.0f} dBm). Connection is likely unstable or dropping.",
    ),
    Rule(
        rule_id="wifi_signal_warning",
        category=AlertCategory.NETWORK,
        severity=AlertSeverity.WARNING,
        metric_name="signal_strength_dbm",
        threshold=-70.0,
        message_template="WiFi signal weak at {value:.0f} dBm (threshold {threshold:.0f} dBm). Move closer to the router or use ethernet.",
    ),
    Rule(
        rule_id="wifi_speed_warning",
        category=AlertCategory.NETWORK,
        severity=AlertSeverity.WARNING,
        metric_name="link_speed_mbps",
        threshold=54.0,
        message_template="WiFi link speed is low at {value:.0f} Mbps (threshold {threshold:.0f} Mbps). Network performance may be impacted.",
    ),
]


# ── Rule evaluation helpers ────────────────────────────────────────────

def _fire(rule: Rule, value: float, device_id: str = "", snapshot_id: str = "") -> Alert:
    """Instantiate an Alert for a triggered rule."""
    return Alert(
        id=str(uuid.uuid4()),
        rule_id=rule.rule_id,
        category=rule.category,
        severity=rule.severity,
        message=rule.message_template.format(value=value, threshold=rule.threshold),
        metric_name=rule.metric_name,
        metric_value=value,
        threshold_value=rule.threshold,
        triggered_at=datetime.utcnow(),
        device_id=device_id,
        snapshot_id=snapshot_id,
    )


def _get(metrics: dict, key: str) -> Optional[float]:
    v = metrics.get(key)
    return float(v) if v is not None else None


# ── Main evaluation function ───────────────────────────────────────────

def evaluate_alerts(
    cpu_temperature: float,
    battery_level: float,
    battery_health: float,
    disk_usage: float,
    gpu_temperature: Optional[float] = None,
    battery_temperature: Optional[float] = None,
    cycle_count: Optional[int] = None,
    write_bytes_sec: Optional[int] = None,
    signal_strength_dbm: Optional[float] = None,
    link_speed_mbps: Optional[int] = None,
    thermal_state: Optional[str] = None,
    power_source: str = "ac",
    device_id: str = "",
    snapshot_id: str = "",
) -> List[Alert]:
    """
    Evaluate all rules against one telemetry snapshot.
    Returns a list of fired Alert objects (may be empty).

    Rules are evaluated highest-severity-first. Within a single category,
    only the highest-severity breach fires (avoids duplicate Warning+Critical
    for the same metric).
    """
    alerts: List[Alert] = []
    fired_rules: set[str] = set()  # track which rule_ids already fired

    # Build lookup for convenience
    metrics = {
        "cpu_temperature":    cpu_temperature,
        "gpu_temperature":    gpu_temperature,
        "battery_level":      battery_level,
        "battery_health":     battery_health,
        "battery_temperature": battery_temperature,
        "cycle_count":        float(cycle_count) if cycle_count is not None else None,
        "disk_usage":         disk_usage,
        "write_bytes_sec":    float(write_bytes_sec) if write_bytes_sec is not None else None,
        "signal_strength_dbm": signal_strength_dbm,
        "link_speed_mbps":    float(link_speed_mbps) if link_speed_mbps is not None else None,
    }

    # Suppress Warning-level rule if Critical for same metric already fired
    # (We process CRITICAL first, then WARNING — RULES list is already ordered)
    fired_metrics: set[str] = set()

    for rule in RULES:
        value = _get(metrics, rule.metric_name)
        if value is None:
            continue

        # Determine if threshold is breached
        if rule.metric_name in ("signal_strength_dbm", "battery_level",
                                 "battery_health", "link_speed_mbps"):
            # Low-is-bad: fire when value < threshold (for battery/wifi level rules)
            # But battery_level and battery_health: fire when value < threshold
            # signal_strength_dbm: fire when value < threshold (more negative = worse)
            breached = value < rule.threshold
        elif rule.metric_name == "link_speed_mbps":
            breached = value < rule.threshold
        else:
            # High-is-bad: fire when value > threshold
            breached = value > rule.threshold

        if not breached:
            continue

        # Skip lower severity for same metric (Critical already covers it)
        metric_severity_key = f"{rule.metric_name}:{AlertSeverity.CRITICAL}"
        if rule.severity == AlertSeverity.WARNING and metric_severity_key in fired_metrics:
            continue

        alerts.append(_fire(rule, value, device_id, snapshot_id))
        fired_rules.add(rule.rule_id)
        if rule.severity == AlertSeverity.CRITICAL:
            fired_metrics.add(metric_severity_key)

    # Extra: thermal_state hard trigger (overrides temp check)
    if thermal_state in ("critical", "serious"):
        severity = AlertSeverity.CRITICAL if thermal_state == "critical" else AlertSeverity.WARNING
        # Only add if cpu_temp rule didn't already fire at this severity
        already = any(a.rule_id.startswith("cpu_temp") and a.severity == severity for a in alerts)
        if not already:
            alerts.append(Alert(
                id=str(uuid.uuid4()),
                rule_id=f"thermal_state_{thermal_state}",
                category=AlertCategory.OVERHEATING,
                severity=severity,
                message=f"System thermal state is '{thermal_state}'. CPU is being throttled to prevent damage.",
                metric_name="thermal_state",
                metric_value=0.0,
                threshold_value=0.0,
                triggered_at=datetime.utcnow(),
                device_id=device_id,
                snapshot_id=snapshot_id,
            ))

    return alerts


def group_alerts_by_category(alerts: List[Alert]) -> dict:
    """Utility: group a list of alerts by category for summary views."""
    grouped: dict = {
        AlertCategory.OVERHEATING: [],
        AlertCategory.BATTERY:     [],
        AlertCategory.DISK:        [],
        AlertCategory.NETWORK:     [],
    }
    for a in alerts:
        grouped.setdefault(a.category, []).append(a)
    return grouped
