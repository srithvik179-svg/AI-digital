"""
Health Score Engine — Phase 5
Computes a 0-100 composite health score for a laptop telemetry snapshot.

Scoring formula uses 7 weighted sub-scores. Each sub-score is 0-100
(100 = perfect, 0 = worst). Weights sum to 1.0.

  Component       Weight   Penalty Trigger
  ─────────────────────────────────────────
  CPU usage        22%     > 50 %  → penalty scales to 0 at 95 %
  Memory usage     13%     > 60 %  → penalty scales to 0 at 98 %
  GPU usage         8%     > 60 %  → penalty scales to 0 at 98 %
  Temperature      22%     > 60 °C → penalty scales to 0 at 95 °C
  Battery          15%     < 50 %  → penalty scales to 0 at 5 %
                           Battery health also factored in
  Disk usage       10%     > 70 %  → penalty scales to 0 at 98 %
  WiFi signal      10%     < -60 dBm → penalty scales to 0 at -90 dBm

Category thresholds:
  ≥ 75 → Healthy
  ≥ 50 → Warning
  <  50 → Critical
"""

from dataclasses import dataclass
from typing import Optional

__all__ = ["compute_health_score", "HealthScore"]

CATEGORY_HEALTHY  = "Healthy"
CATEGORY_WARNING  = "Warning"
CATEGORY_CRITICAL = "Critical"


@dataclass
class HealthScore:
    score: float                 # 0.0 – 100.0 (2 dp)
    category: str                # "Healthy" | "Warning" | "Critical"
    breakdown: dict              # per-component scores (0-100)
    recommendations: list[str]   # human-readable action items


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _linear_score(value: float, good_thresh: float, bad_thresh: float) -> float:
    """
    Returns 100 when value <= good_thresh, 0 when value >= bad_thresh,
    and linearly interpolates in between.  Works for both ascending (high
    is bad, e.g. CPU %) and descending (low is bad, e.g. battery level)
    ranges — pass good/bad accordingly.
    """
    if good_thresh < bad_thresh:
        # Higher value is worse (CPU %, temperature, disk %)
        if value <= good_thresh:
            return 100.0
        if value >= bad_thresh:
            return 0.0
        return 100.0 * (bad_thresh - value) / (bad_thresh - good_thresh)
    else:
        # Lower value is worse (battery level, WiFi signal dBm)
        if value >= good_thresh:
            return 100.0
        if value <= bad_thresh:
            return 0.0
        return 100.0 * (value - bad_thresh) / (good_thresh - bad_thresh)


def compute_health_score(
    cpu_usage: float,
    memory_usage: float,
    disk_usage: float,
    cpu_temperature: float,
    battery_level: float,
    battery_health: float,
    gpu_usage: Optional[float] = None,
    signal_strength_dbm: Optional[float] = None,
    power_source: str = "ac",
    thermal_state: Optional[str] = None,
) -> HealthScore:
    """
    Compute the composite laptop health score.

    Parameters
    ----------
    cpu_usage           : CPU utilization %  (0-100)
    memory_usage        : RAM utilization %  (0-100)
    disk_usage          : Disk fill %        (0-100)
    cpu_temperature     : CPU temp °C
    battery_level       : Battery charge %   (0-100)
    battery_health      : Battery condition % (0-100)
    gpu_usage           : GPU utilization %  (0-100), optional
    signal_strength_dbm : WiFi RSSI dBm, optional (negative int, e.g. -55)
    power_source        : "ac" | "battery"
    thermal_state       : "nominal" | "moderate" | "critical" | "serious"
    """

    # ── Sub-scores (0-100) ────────────────────────────────────────────
    cpu_score  = _linear_score(cpu_usage,        good_thresh=50.0, bad_thresh=95.0)
    mem_score  = _linear_score(memory_usage,     good_thresh=60.0, bad_thresh=98.0)
    disk_score = _linear_score(disk_usage,       good_thresh=70.0, bad_thresh=98.0)
    temp_score = _linear_score(cpu_temperature,  good_thresh=60.0, bad_thresh=95.0)

    # Battery: weighted average of charge level and health
    bat_level_score  = _linear_score(battery_level,  good_thresh=50.0, bad_thresh=5.0)
    bat_health_score = _linear_score(battery_health, good_thresh=80.0, bad_thresh=40.0)
    bat_score = bat_level_score * 0.65 + bat_health_score * 0.35

    # GPU: if not provided assume idle (perfect score)
    gpu_score = _linear_score(gpu_usage, good_thresh=60.0, bad_thresh=98.0) \
        if gpu_usage is not None else 100.0

    # WiFi: if not provided assume good signal
    if signal_strength_dbm is not None:
        wifi_score = _linear_score(float(signal_strength_dbm), good_thresh=-60.0, bad_thresh=-90.0)
    else:
        wifi_score = 100.0

    # ── Thermal-state hard override ───────────────────────────────────
    if thermal_state in ("critical", "serious"):
        temp_score = min(temp_score, 10.0)
    elif thermal_state == "moderate":
        temp_score = min(temp_score, 60.0)

    # ── Weighted composite ────────────────────────────────────────────
    weights = {
        "cpu":         0.22,
        "memory":      0.13,
        "gpu":         0.08,
        "temperature": 0.22,
        "battery":     0.15,
        "disk":        0.10,
        "wifi":        0.10,
    }
    raw_score = (
        cpu_score        * weights["cpu"]         +
        mem_score        * weights["memory"]      +
        gpu_score        * weights["gpu"]         +
        temp_score       * weights["temperature"] +
        bat_score        * weights["battery"]     +
        disk_score       * weights["disk"]        +
        wifi_score       * weights["wifi"]
    )
    final_score = round(_clamp(raw_score, 0.0, 100.0), 2)

    # ── Categorise ────────────────────────────────────────────────────
    if final_score >= 75.0:
        category = CATEGORY_HEALTHY
    elif final_score >= 50.0:
        category = CATEGORY_WARNING
    else:
        category = CATEGORY_CRITICAL

    # ── Recommendations ───────────────────────────────────────────────
    recs: list[str] = []
    if cpu_score < 50:
        recs.append(f"CPU utilization is high ({cpu_usage:.1f}%). Close background applications to reduce load.")
    if mem_score < 50:
        recs.append(f"Memory usage is high ({memory_usage:.1f}%). Consider closing unused apps or adding RAM.")
    if temp_score < 50:
        recs.append(f"CPU temperature is elevated ({cpu_temperature:.1f}°C). Ensure ventilation and clean cooling fans.")
    if bat_level_score < 30:
        recs.append(f"Battery level is critically low ({battery_level:.1f}%). Connect to power immediately.")
    elif bat_level_score < 60:
        recs.append(f"Battery level is low ({battery_level:.1f}%). Consider charging soon.")
    if bat_health_score < 50:
        recs.append(f"Battery health is degraded ({battery_health:.1f}%). Consider battery replacement.")
    if disk_score < 50:
        recs.append(f"Disk usage is high ({disk_usage:.1f}%). Free up storage space.")
    if wifi_score < 50:
        recs.append(f"WiFi signal is weak ({signal_strength_dbm} dBm). Move closer to router or use ethernet.")
    if gpu_score < 50:
        recs.append(f"GPU load is high ({gpu_usage:.1f}%). Check GPU-intensive applications.")
    if not recs:
        recs.append("All systems are operating within healthy parameters.")

    breakdown = {
        "cpu":         round(cpu_score,  2),
        "memory":      round(mem_score,  2),
        "gpu":         round(gpu_score,  2),
        "temperature": round(temp_score, 2),
        "battery":     round(bat_score,  2),
        "disk":        round(disk_score, 2),
        "wifi":        round(wifi_score, 2),
    }

    return HealthScore(
        score=final_score,
        category=category,
        breakdown=breakdown,
        recommendations=recs,
    )
