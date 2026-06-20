"""
Natural Language Summary Generator — Phase 7
Template-based system. Zero I/O, zero LLM. Sub-millisecond execution.

Architecture:
  1. Each metric is bucketed into a named tier (excellent / good / moderate / high / critical)
  2. Each tier maps to a sentence fragment
  3. Fragments are ranked by severity and assembled into:
       - headline  : single most important sentence
       - paragraph : 2–4 flowing natural-language sentences
       - observations : 4–7 bullet-point phrases
  4. A closing verdict sentence based on overall health_score / category

All templates are explicit Python strings — no LLM, no regex, no dynamic code.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List, Tuple
import time

__all__ = ["generate_summary", "NLSummary"]


# ─── Output dataclass ─────────────────────────────────────────────────

@dataclass
class NLSummary:
    headline: str           # Most critical one-liner (< 120 chars)
    paragraph: str          # Full 2-4 sentence readable narrative
    observations: List[str] # Bullet-point phrases (4-7 items)
    severity: str           # Healthy | Warning | Critical
    generated_in_ms: float  # Wall-clock latency


# ─── Tier helpers ─────────────────────────────────────────────────────

# Each tier is: (severity_rank, short_label, sentence_fragment)
# severity_rank: 0 = excellent, 1 = good, 2 = moderate, 3 = high, 4 = critical

Tier = Tuple[int, str, str]

def _cpu_tier(v: float) -> Tier:
    if v < 25:   return (0, "idle",            f"CPU utilization is low at {v:.0f}%")
    if v < 50:   return (1, "moderate",        f"CPU utilization is moderate at {v:.0f}%")
    if v < 70:   return (2, "elevated",        f"CPU utilization is elevated at {v:.0f}%")
    if v < 85:   return (3, "high",            f"CPU utilization is high at {v:.0f}%")
    return        (4, "critically high",       f"CPU utilization is critically high at {v:.0f}%, risking sluggishness")

def _memory_tier(v: float) -> Tier:
    if v < 40:   return (0, "low",             f"memory pressure is low at {v:.0f}%")
    if v < 65:   return (1, "comfortable",     f"memory usage is comfortable at {v:.0f}%")
    if v < 80:   return (2, "elevated",        f"memory usage is elevated at {v:.0f}%")
    if v < 90:   return (3, "high",            f"memory pressure is high at {v:.0f}%")
    return        (4, "critically high",       f"memory is critically strained at {v:.0f}%, close applications immediately")

def _temp_tier(v: float, thermal_state: Optional[str] = None) -> Tier:
    if thermal_state in ("critical",):
        return (4, "critical",                 f"the system thermal state is critical at {v:.0f}°C — throttling is active")
    if thermal_state in ("serious",):
        return (3, "serious",                  f"thermal stress is serious at {v:.0f}°C")
    if v < 50:   return (0, "cool",            f"thermals are cool at {v:.0f}°C")
    if v < 65:   return (1, "normal",          f"CPU temperature is within normal range at {v:.0f}°C")
    if v < 75:   return (2, "warm",            f"thermal stress is increasing at {v:.0f}°C")
    if v < 85:   return (3, "hot",             f"CPU is running hot at {v:.0f}°C")
    return        (4, "critical",              f"CPU temperature is critically high at {v:.0f}°C — hardware damage risk")

def _battery_level_tier(v: float, power_source: str = "ac") -> Tier:
    charging = power_source.lower() == "ac"
    suffix = " (charging)" if charging else " (on battery)"
    if v > 80:   return (0, "well-charged",    f"battery is well-charged at {v:.0f}%{suffix}")
    if v > 50:   return (1, "adequate",        f"battery level is adequate at {v:.0f}%{suffix}")
    if v > 25:   return (2, "draining",        f"battery is draining — currently at {v:.0f}%{suffix}")
    if v > 10:   return (3, "low",             f"battery is low at {v:.0f}% — connect to power soon")
    return        (4, "critically low",        f"battery is critically low at {v:.0f}% — connect to power immediately")

def _battery_health_tier(v: float) -> Tier:
    if v >= 90:  return (0, "excellent",       f"battery health is excellent at {v:.0f}%")
    if v >= 80:  return (1, "good",            f"battery health is good at {v:.0f}%")
    if v >= 70:  return (2, "degrading",       f"battery health has degraded to {v:.0f}%")
    if v >= 60:  return (3, "poor",            f"battery health is poor at {v:.0f}% — replacement advised")
    return        (4, "critical",              f"battery health is critically degraded at {v:.0f}% — replace battery")

def _disk_tier(v: float) -> Tier:
    if v < 55:   return (0, "ample",           f"disk space is ample at {v:.0f}% used")
    if v < 75:   return (1, "moderate",        f"disk usage is moderate at {v:.0f}%")
    if v < 88:   return (2, "filling",         f"disk space is filling up at {v:.0f}%")
    if v < 95:   return (3, "low",             f"disk space is running low at {v:.0f}% — review large files")
    return        (4, "critical",              f"disk space is critically low at {v:.0f}% — free storage immediately")

def _gpu_tier(v: float) -> Tier:
    if v < 15:   return (0, "idle",            f"GPU is mostly idle at {v:.0f}%")
    if v < 45:   return (1, "light",           f"GPU is under light load at {v:.0f}%")
    if v < 65:   return (2, "moderate",        f"GPU is under moderate load at {v:.0f}%")
    if v < 85:   return (3, "heavy",           f"GPU utilization is high at {v:.0f}%")
    return        (4, "critical",              f"GPU utilization is critically high at {v:.0f}%")

def _wifi_tier(v: float) -> Tier:
    if v >= -55: return (0, "excellent",       "network signal is excellent")
    if v >= -67: return (1, "good",            f"network signal is good at {v:.0f} dBm")
    if v >= -75: return (2, "fair",            f"network signal is fair at {v:.0f} dBm")
    if v >= -85: return (3, "weak",            f"network signal is weak at {v:.0f} dBm — consider moving closer to the router")
    return        (4, "very weak",             f"network signal is very weak at {v:.0f} dBm — connectivity may drop")

def _fan_note(fan_rpm: Optional[int]) -> Optional[str]:
    if fan_rpm is None:
        return None
    if fan_rpm > 4500:
        return f"fans are spinning loudly at {fan_rpm} RPM, indicating significant thermal load"
    if fan_rpm > 3000:
        return f"fans are running at {fan_rpm} RPM under moderate thermal pressure"
    return None  # quiet fans don't warrant mention


# ─── Verdict templates keyed by (health_category, critical_count) ─────

def _verdict(health_score: Optional[float], health_category: Optional[str],
             critical_count: int, warning_count: int) -> str:
    cat = (health_category or "Healthy").strip()
    score_str = f" (score: {health_score:.0f}/100)" if health_score is not None else ""

    if cat == "Critical" or critical_count >= 2:
        return f"Overall, the laptop is in critical condition{score_str} and requires immediate attention."
    if cat == "Critical" or critical_count == 1:
        return f"Overall, the system is under significant stress{score_str} — address the critical issue above."
    if cat == "Warning" or warning_count >= 2:
        return f"Overall, the laptop is functional but showing warning signs{score_str}. Monitor closely."
    if cat == "Warning" or warning_count == 1:
        return f"Overall, the system is performing adequately{score_str} with one area to watch."
    return f"Overall, the laptop is operating normally and all systems are healthy{score_str}."


# ─── Sentence joiner ──────────────────────────────────────────────────

def _join_sentences(parts: List[str]) -> str:
    """Join sentence fragments into a flowing paragraph."""
    if not parts:
        return "All systems are operating normally."
    # Capitalise first char of each, end with period
    sentences = []
    for p in parts:
        s = p.strip()
        if s:
            sentences.append(s[0].upper() + s[1:] + ("" if s.endswith(".") else "."))
    return " ".join(sentences)


def _headline(ranked_tiers: List[Tuple[int, str, str, str]]) -> str:
    """Pick the most severe observation as the headline."""
    if not ranked_tiers:
        return "All systems are healthy and operating normally."
    worst = ranked_tiers[0]
    _, _, fragment, _ = worst
    s = fragment.strip()
    return s[0].upper() + s[1:] + "."


# ─── Main generator ───────────────────────────────────────────────────

def generate_summary(
    cpu_usage: float,
    memory_usage: float,
    disk_usage: float,
    cpu_temperature: float,
    battery_level: float,
    battery_health: float,
    fan_speed: Optional[int] = None,
    gpu_usage: Optional[float] = None,
    signal_strength_dbm: Optional[float] = None,
    power_source: str = "ac",
    health_score: Optional[float] = None,
    health_category: Optional[str] = None,
    active_process_count: Optional[int] = None,
    thermal_state: Optional[str] = None,
    link_speed_mbps: Optional[int] = None,
) -> NLSummary:
    """
    Generate a human-readable telemetry summary from raw metrics.
    Pure template logic — no I/O, no LLM. Typically < 0.5 ms.
    """
    t0 = time.perf_counter()

    # ── Evaluate all tiers ────────────────────────────────────────
    cpu_t    = _cpu_tier(cpu_usage)
    mem_t    = _memory_tier(memory_usage)
    temp_t   = _temp_tier(cpu_temperature, thermal_state)
    batt_t   = _battery_level_tier(battery_level, power_source)
    bhealth_t = _battery_health_tier(battery_health)
    disk_t   = _disk_tier(disk_usage)

    # Optional
    gpu_t    = _gpu_tier(gpu_usage) if gpu_usage is not None else None
    wifi_t   = _wifi_tier(signal_strength_dbm) if signal_strength_dbm is not None else None

    # ── Build ranked list: (rank, label, fragment, component_name) ─
    tiers: List[Tuple[int, str, str, str]] = [
        (cpu_t[0],    cpu_t[1],    cpu_t[2],    "CPU"),
        (mem_t[0],    mem_t[1],    mem_t[2],    "Memory"),
        (temp_t[0],   temp_t[1],   temp_t[2],   "Temperature"),
        (batt_t[0],   batt_t[1],   batt_t[2],   "Battery"),
        (bhealth_t[0], bhealth_t[1], bhealth_t[2], "Battery Health"),
        (disk_t[0],   disk_t[1],   disk_t[2],   "Disk"),
    ]
    if gpu_t:
        tiers.append((gpu_t[0], gpu_t[1], gpu_t[2], "GPU"))
    if wifi_t:
        tiers.append((wifi_t[0], wifi_t[1], wifi_t[2], "Network"))

    # Sort: highest severity first, then alphabetical for stability
    ranked = sorted(tiers, key=lambda x: (-x[0], x[3]))

    # ── Count warnings / criticals ───────────────────────────────
    critical_count = sum(1 for r in ranked if r[0] >= 4)
    warning_count  = sum(1 for r in ranked if r[0] == 3)

    # ── Observations (bullet points) ─────────────────────────────
    # Show all non-excellent items; always show at least 3
    notable = [r for r in ranked if r[0] >= 2]
    if len(notable) < 3:
        notable = ranked[:4]  # fallback: top 4 regardless of tier
    observations = [r[2][0].upper() + r[2][1:] for r in notable[:7]]

    # Add fan note if interesting
    fan_note = _fan_note(fan_speed)
    if fan_note and len(observations) < 7:
        observations.append(fan_note[0].upper() + fan_note[1:])

    # Add process count note
    if active_process_count and active_process_count > 120:
        observations.append(f"{active_process_count} active processes are running")

    # ── Paragraph construction ────────────────────────────────────
    # Strategy:
    #   Sentence 1: Lead with 1-2 most critical observations
    #   Sentence 2: Mid-range observations (memory, disk, wifi)
    #   Sentence 3: Battery + power context
    #   Sentence 4: Verdict

    # Sentence 1 — performance + thermals (top concerns)
    perf_parts = []
    for name in ("CPU", "Temperature", "Memory", "GPU"):
        match = next((r for r in ranked if r[3] == name and r[0] >= 2), None)
        if match:
            perf_parts.append(match[2])
    if not perf_parts:
        # Everything good — use nominal descriptions for top 2
        perf_parts = [ranked[0][2], ranked[1][2]] if len(ranked) > 1 else [ranked[0][2]]
    s1_raw = _conjoin(perf_parts[:3])

    # Sentence 2 — storage + network
    infra_parts = []
    for name in ("Disk", "Network"):
        match = next((r for r in ranked if r[3] == name and r[0] >= 1), None)
        if match:
            infra_parts.append(match[2])
    s2 = _join_sentences(infra_parts) if infra_parts else ""

    # Sentence 3 — battery
    bat_parts = []
    for name in ("Battery", "Battery Health"):
        match = next((r for r in ranked if r[3] == name and r[0] >= 1), None)
        if match:
            bat_parts.append(match[2])
    s3 = _join_sentences(bat_parts[:2]) if bat_parts else ""

    # Sentence 4 — verdict
    s4 = _verdict(health_score, health_category, critical_count, warning_count)

    para_parts = [p for p in [s1_raw, s2, s3, s4] if p]
    paragraph = _join_sentences(para_parts)

    # ── Headline ─────────────────────────────────────────────────
    headline = _headline(ranked)

    # ── Severity label ────────────────────────────────────────────
    if health_category:
        severity = health_category
    elif critical_count >= 1:
        severity = "Critical"
    elif warning_count >= 1:
        severity = "Warning"
    else:
        severity = "Healthy"

    elapsed_ms = (time.perf_counter() - t0) * 1000

    return NLSummary(
        headline=headline,
        paragraph=paragraph,
        observations=observations,
        severity=severity,
        generated_in_ms=round(elapsed_ms, 3),
    )


def _conjoin(parts: List[str]) -> str:
    """Join 1-3 sentence fragments with natural connectors."""
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f"{parts[0]}, while {parts[1]}"
    return f"{parts[0]}, {parts[1]}, and {parts[2]}"
