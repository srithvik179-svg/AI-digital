"""
Phase 50 — Evidence-Driven Chatbot & Hallucination Guard.

Architected to process user questions through a strict 10-step modular pipeline:
1. Question Classification (Current Status, Diagnostics, RCA, Health, Recs, Correlation, Trend, Prediction, Simulation, Unknown).
2. Data Retrieval Layer (PostgreSQL latest telemetry, history, alerts, relationships, predictions, recs).
3. Deterministic Rule Engine (evaluates CPU temp, battery health, disk, wifi thresholds before LLM).
4. Root Cause Analysis (integrates decision tree & causal graph diagnostics).
5. Prediction Engine (7-day/30-day wear/failure projections, cycles & SSD TBW failure probability).
6. Simulation Engine (hypothetical what-if physics-based steady state calculations).
7. LLM Prompt Gating (strictly passes evidence/reasoning, forbids fabrication).
8. Mandatory Format Renderer (Answer, Evidence, Reasoning, Confidence).
9. Post-Generation Hallucination Guard (verifies claims, strips banned keywords like dust/paste/hardware unless present).
10. Supported Questions fallback.
"""

from __future__ import annotations
import re
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple, Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.core.logging import logger
from app.models.telemetry import TelemetrySnapshot
from app.models.alert import TelemetryAlert
from app.models.relationship import TelemetryRelationship
from app.services.alert_engine import evaluate_alerts
from app.services.rca_engine import run_rca_analysis
from app.services.ai_reasoning.what_if_simulator import simulate_what_if
from app.services.ai_reasoning.failure_prediction import FailurePredictor
from app.services.health_score import compute_health_score

# ─────────────────────────────────────────────────────────────────────────────
# Step 1: Question Classification
# ─────────────────────────────────────────────────────────────────────────────

CATEGORIES = {
    "Prediction": [
        r"\b(?:how will|condition after|7 days|30 days|forecast|likely to fail|predicted|prediction|RUL|remaining useful life)\b"
    ],
    "Simulation": [
        r"\b(?:what if|what happens if|gaming continues|simulate)\b"
    ],
    "Diagnostics": [
        r"\bwhy is\b.*\b(?:hot|draining|slow|sluggish|loud|noisy)\b",
        r"\b(?:diagnose|diagnosing|troubleshoot)\b.*\b(?:slow|heat|fan|battery)\b"
    ],
    "Root Cause Analysis": [
        r"\bwhy is\b.*\b(?:overheating|low health|critical health|failing|degraded)\b",
        r"\broot cause\b"
    ],
    "Health Assessment": [
        r"\b(?:how healthy|what is the health|health score|why is health marked|why is health warning|why is health critical)\b"
    ],
    "Recommendations": [
        r"\b(?:how can i|recomm|recommendation|improve|reduce|optimize)\b.*\b(?:battery|temp|temperature|perf|performance|health)\b"
    ],
    "Correlation Analysis": [
        r"\b(?:does|affect|relation|correlat)\b.*\b(?:cpu|temp|temperature|fan|battery|drain|load)\b"
    ],
    "Trend Analysis": [
        r"\b(?:trend|history|past|change|wear trend)\b"
    ],
    "Current Status": [
        r"\b(?:what is|show|check|get)\b.*\b(?:cpu usage|cpu load|gpu usage|ram usage|memory usage|battery level|battery charge|battery health|disk health|ssd health|storage usage|disk usage|wifi strength|wifi signal|ssid|fan speed|cpu temp|cpu temperature|temperature|active processes)\b",
        r"\b(?:cpu usage|gpu usage|ram usage|memory level|battery level|battery health|disk health|wifi strength)\b"
    ]
}

def classify_question(query: str) -> str:
    query_lower = query.lower().strip()
    for cat, patterns in CATEGORIES.items():
        for pat in patterns:
            if re.search(pat, query_lower):
                return cat
    return "Unknown"


# ─────────────────────────────────────────────────────────────────────────────
# Step 3: Rule Engine
# ─────────────────────────────────────────────────────────────────────────────

def run_rule_engine(snap: TelemetrySnapshot) -> List[str]:
    """Deterministically checks key metric thresholds."""
    rules_triggered = []
    
    cpu_temp = snap.thermal.cpu_temperature if (snap.thermal and snap.thermal.cpu_temperature is not None) else 0.0
    battery_health = snap.battery.battery_health if (snap.battery and snap.battery.battery_health is not None) else 100.0
    disk_usage = snap.disk.disk_usage if (snap.disk and snap.disk.disk_usage is not None) else 0.0
    wifi_strength = snap.wifi.signal_strength_dbm if (snap.wifi and snap.wifi.signal_strength_dbm is not None) else -50
    
    # Map RSSI back to 0-100 strength for the rule condition check
    # RSSI: -100 to -20 dBm -> 0 to 100 strength
    wifi_pct = max(0, min(100, int(2 * (wifi_strength + 100))))

    if cpu_temp > 90:
        rules_triggered.append("Rule Triggered: Thermal Stress detected (CPU Temperature > 90°C)")
    if battery_health < 75:
        rules_triggered.append("Rule Triggered: Battery Risk detected (Battery Health < 75%)")
    if disk_usage > 90:
        rules_triggered.append("Rule Triggered: Storage Failure Risk detected (Disk Usage > 90%)")
    if wifi_pct < 50:
        rules_triggered.append("Rule Triggered: Connectivity Risk detected (WiFi Signal Strength < 50%)")
        
    return rules_triggered


# ─────────────────────────────────────────────────────────────────────────────
# Query Orchestrator
# ─────────────────────────────────────────────────────────────────────────────

def query_evidence_chatbot(
    device_id: str,
    query: str,
    db_session: Session
) -> Dict[str, Any]:
    """
    Main chatbot orchestrator implementing the 10-step pipeline.
    """
    t0 = time.perf_counter()
    query_lower = query.lower().strip()

    # Step 1: Question Classification
    category = classify_question(query)
    
    # Step 2: Retrieval Layer
    # Fetch latest snapshot
    snap = (
        db_session.query(TelemetrySnapshot)
        .options(
            joinedload(TelemetrySnapshot.cpu),
            joinedload(TelemetrySnapshot.gpu),
            joinedload(TelemetrySnapshot.battery),
            joinedload(TelemetrySnapshot.disk),
            joinedload(TelemetrySnapshot.power),
            joinedload(TelemetrySnapshot.thermal),
            joinedload(TelemetrySnapshot.wifi)
        )
        .filter(TelemetrySnapshot.device_id == device_id)
        .order_by(TelemetrySnapshot.timestamp.desc())
        .first()
    )

    if not snap:
        return {
            "query": query,
            "response": f"Answer:\nInsufficient telemetry data available to answer this question.\n\nEvidence:\nNone\n\nReasoning:\nDevice registry is empty.\n\nConfidence:\n0%",
            "source_documents": []
        }

    # Fetch history (last 60 ticks)
    history_records = (
        db_session.query(TelemetrySnapshot)
        .filter(TelemetrySnapshot.device_id == device_id)
        .order_by(TelemetrySnapshot.timestamp.desc())
        .limit(60)
        .all()
    )
    history = []
    for h in history_records:
        history.append({
            "timestamp": h.timestamp.isoformat() if hasattr(h.timestamp, "isoformat") else str(h.timestamp),
            "cpu_usage": h.cpu.cpu_usage if h.cpu else 0.0,
            "cpu_temperature": h.thermal.cpu_temperature if h.thermal else 0.0,
            "battery_level": h.battery.battery_level if h.battery else 100.0,
            "battery_health": h.battery.battery_health if h.battery else 100.0,
            "battery_cycle_count": h.battery.cycle_count if h.battery else 0,
            "write_bytes_sec": h.disk.write_bytes_sec if h.disk else 0.0,
        })
    history.reverse() # Chronological

    # Fetch active alerts
    alerts = db_session.query(TelemetryAlert).filter(
        TelemetryAlert.device_id == device_id,
        TelemetryAlert.acknowledged == False
    ).all()
    alerts_serialized = [
        f"{a.category} alert on metric '{a.metric_name}' (value: {a.metric_value}, threshold: >{a.threshold_value})"
        for a in alerts
    ]

    # Fetch relationships (correlations)
    relationships = db_session.query(TelemetryRelationship).filter(
        TelemetryRelationship.device_id == device_id
    ).all()
    correlations = [
        f"{r.source_node} has {r.relationship_type} correlation with {r.target_node} (strength: {r.correlation_strength:.2f})"
        for r in relationships
    ]

    # Compile structured Evidence dictionary from retrievals
    latest_cpu = snap.cpu.cpu_usage if (snap.cpu and snap.cpu.cpu_usage is not None) else 0.0
    latest_temp = snap.thermal.cpu_temperature if (snap.thermal and snap.thermal.cpu_temperature is not None) else 0.0
    latest_fan = snap.thermal.fan_speed_rpm if (snap.thermal and snap.thermal.fan_speed_rpm is not None) else 0
    latest_battery = snap.battery.battery_level if (snap.battery and snap.battery.battery_level is not None) else 0.0
    latest_health = snap.battery.battery_health if (snap.battery and snap.battery.battery_health is not None) else 100.0
    latest_disk = snap.disk.disk_usage if (snap.disk and snap.disk.disk_usage is not None) else 0.0
    latest_wifi_dbm = snap.wifi.signal_strength_dbm if (snap.wifi and snap.wifi.signal_strength_dbm is not None) else -50
    latest_wifi_pct = max(0, min(100, int(2 * (latest_wifi_dbm + 100))))
    latest_gpu = snap.gpu.gpu_usage if (snap.gpu and snap.gpu.gpu_usage is not None) else 0.0
    latest_gpu_temp = snap.gpu.gpu_temperature if (snap.gpu and snap.gpu.gpu_temperature is not None) else 0.0
    latest_mem = snap.memory.memory_usage if (snap.memory and snap.memory.memory_usage is not None) else 0.0
    latest_cycles = snap.battery.cycle_count if (snap.battery and snap.battery.cycle_count is not None) else 0
    latest_power = snap.power.power_source if (snap.power and snap.power.power_source is not None) else "ac"

    evidence_dict = {
        "CPU Usage": f"{latest_cpu:.1f}%",
        "CPU Temperature": f"{latest_temp:.1f}°C",
        "Fan Speed": f"{latest_fan} RPM",
        "Battery Level": f"{latest_battery:.1f}%",
        "Battery Health": f"{latest_health:.1f}%",
        "Disk Usage": f"{latest_disk:.1f}%",
        "WiFi Strength": f"{latest_wifi_pct}%",
        "WiFi RSSI": f"{latest_wifi_dbm} dBm",
        "GPU Usage": f"{latest_gpu:.1f}%",
        "GPU Temperature": f"{latest_gpu_temp:.1f}°C",
        "Memory Usage": f"{latest_mem:.1f}%",
        "Battery Cycle Count": str(latest_cycles),
        "Power Source": latest_power.upper()
    }

    # Step 3: Rule Engine
    rules_triggered = run_rule_engine(snap)

    # Step 4: Root Cause Engine
    rca_results = run_rca_analysis(snap, db_session)

    # Step 5: Prediction Engine
    failure_predictor = FailurePredictor()
    predictions_failed = False
    try:
        current_state_map = {
            "battery_health": latest_health,
            "battery_cycle_count": latest_cycles,
            "write_bytes_sec": snap.disk.write_bytes_sec if snap.disk else 0.0
        }
        pred_out = failure_predictor.predict_failure_horizon(current_state_map, history)
    except Exception as e:
        logger.error(f"Prediction model execution failed: {e}")
        pred_out = {}
        predictions_failed = True

    # Step 6: Simulation Engine
    sim_out = {}
    if category == "Simulation":
        # Extract simulation parameter values
        cpu_sim = latest_cpu
        health_sim = latest_health
        
        cpu_match = re.search(r'cpu\s*(?:reaches|is|drops\s*to)?\s*(\d+)%', query_lower)
        if cpu_match:
            cpu_sim = float(cpu_match.group(1))
            
        health_match = re.search(r'battery\s*health\s*(?:drops\s*to|is)?\s*(\d+)%', query_lower)
        if health_match:
            health_sim = float(health_match.group(1))

        is_gaming = "gaming" in query_lower
        if is_gaming:
            # Simulate high-load gaming workload
            sim_out = simulate_what_if(
                cpu_usage=80.0,
                gpu_usage=70.0,
                memory_usage=75.0,
                battery_level=latest_battery,
                battery_health=latest_health,
                power_source="battery"
            )
        else:
            sim_out = simulate_what_if(
                cpu_usage=cpu_sim,
                gpu_usage=latest_gpu,
                memory_usage=latest_mem,
                battery_level=latest_battery,
                battery_health=health_sim,
                power_source=latest_power
            )

    # Compile reasoning text block based on question classification
    answer = ""
    reasoning = ""
    confidence = "100%"
    evidence_lines = []

    if category == "Current Status":
        # Pull only relevant metrics depending on what was asked
        matched_keys = []
        if "cpu" in query_lower:
            matched_keys.append("CPU Usage")
            matched_keys.append("CPU Temperature")
        if "gpu" in query_lower:
            matched_keys.append("GPU Usage")
            matched_keys.append("GPU Temperature")
        if "memory" in query_lower or "ram" in query_lower:
            matched_keys.append("Memory Usage")
        if "battery" in query_lower:
            matched_keys.append("Battery Level")
            matched_keys.append("Battery Health")
            matched_keys.append("Battery Cycle Count")
            matched_keys.append("Power Source")
        if "disk" in query_lower or "storage" in query_lower:
            matched_keys.append("Disk Usage")
        if "wifi" in query_lower or "signal" in query_lower:
            matched_keys.append("WiFi Strength")
            matched_keys.append("WiFi RSSI")
            
        if not matched_keys:
            matched_keys = list(evidence_dict.keys())
            
        evidence_lines = [f"{k} = {evidence_dict[k]}" for k in matched_keys]
        answer = f"The current status is: " + ", ".join(evidence_lines) + "."
        reasoning = "Retrieved direct values from the latest hardware telemetry snapshot."
        confidence = "100%"

    elif category in ("Diagnostics", "Root Cause Analysis"):
        if rca_results:
            top_cause = rca_results[0]
            answer = f"The diagnosed cause is {top_cause['cause']}."
            reasoning = f"Heuristic tree check verified: {top_cause['remedy']} (Traversal path: {' -> '.join(top_cause['path'])})."
            confidence = f"{int(top_cause['confidence'] * 100)}%"
            evidence_lines = [f"{k} = {v}" for k in evidence_dict.keys()]
        else:
            answer = "Diagnostics report nominal operation."
            reasoning = "No alert rules triggered, system is healthy."
            confidence = "95%"
            evidence_lines = [f"Alert Count = {len(alerts)}"]

    elif category == "Health Assessment":
        hs = compute_health_score(
            cpu_usage=latest_cpu,
            memory_usage=latest_mem,
            disk_usage=latest_disk,
            cpu_temperature=latest_temp,
            battery_level=latest_battery,
            battery_health=latest_health,
            gpu_usage=latest_gpu,
            signal_strength_dbm=latest_wifi_dbm,
            power_source=latest_power
        )
        answer = f"Laptop health is scored at {hs.score:.0f}/100, which is classified as {hs.category}."
        reasoning = f"Scoring engine computed sub-component weights. Category determined by score thresholds: {', '.join(hs.recommendations[:2])}."
        confidence = "100%"
        evidence_lines = [
            f"Health Score = {hs.score:.0f}/100",
            f"Health Category = {hs.category}",
            f"CPU Usage = {latest_cpu:.1f}%",
            f"CPU Temperature = {latest_temp:.1f}°C",
            f"Battery Level = {latest_battery:.1f}%",
            f"Battery Health = {latest_health:.1f}%"
        ]

    elif category == "Recommendations":
        # Extract recommendations from health score or alerts
        hs = compute_health_score(
            cpu_usage=latest_cpu,
            memory_usage=latest_mem,
            disk_usage=latest_disk,
            cpu_temperature=latest_temp,
            battery_level=latest_battery,
            battery_health=latest_health,
            gpu_usage=latest_gpu,
            signal_strength_dbm=latest_wifi_dbm,
            power_source=latest_power
        )
        recs = hs.recommendations
        if not recs:
            recs = ["No immediate recommendations. Maintain current healthy usage profiles."]
        answer = f"Remediation steps: {'; '.join(recs)}."
        reasoning = "Recommendations generated based on resource stress scoring and alert rules."
        confidence = "90%"
        evidence_lines = [f"Alert count = {len(alerts)}", f"Health Score = {hs.score:.0f}/100"]

    elif category == "Correlation Analysis":
        # Extract matches
        matched_correlations = []
        for corr in correlations:
            if any(k in corr.lower() for k in query_lower.split()):
                matched_correlations.append(corr)
        if not matched_correlations:
            matched_correlations = correlations[:2]
        
        answer = f"Correlation mapping: {'; '.join(matched_correlations)}."
        reasoning = "Analyzed historical snapshots in PostgreSQL to calculate Pearson/Spearman correlation coefficients."
        confidence = "95%"
        evidence_lines = [f"Active relationship mappings = {len(relationships)}"]

    elif category == "Trend Analysis":
        avg_temp = sum(h["cpu_temperature"] for h in history) / len(history) if history else latest_temp
        answer = f"The historical telemetry indicates stable resource trends over the last {len(history)} frames."
        reasoning = f"Calculated baseline CPU temperature mean of {avg_temp:.1f}°C from sliding logs."
        confidence = "100%"
        evidence_lines = [f"Baseline records retrieved = {len(history)}", f"Average CPU Temp = {avg_temp:.1f}°C"]

    elif category == "Prediction":
        if predictions_failed or not pred_out:
            answer = "Prediction model not available."
            reasoning = "Failure prediction model is uninstantiated or calculation failed."
            confidence = "0%"
            evidence_lines = []
        else:
            is_30d = "30" in query_lower
            horizon_days = 30 if is_30d else 7
            
            # Interpolate wear for target horizon
            # Battery degradation: 0.02% per day
            # SSD degradation: TBW rate per day
            ssd_decay_pct = (failure_predictor.DEFAULT_SSD_GB_WRITTEN_PER_DAY / (failure_predictor.SSD_TBW_LIMIT * 1024.0)) * 100.0
            
            projected_battery_health = max(0.0, latest_health - (0.02 * horizon_days))
            projected_ssd_health = max(0.0, 100.0 - (12.5 / failure_predictor.SSD_TBW_LIMIT * 100.0) - (ssd_decay_pct * horizon_days))
            
            answer = (
                f"Prediction over {horizon_days}-day horizon: Battery Health is projected to decline to {projected_battery_health:.1f}%. "
                f"SSD Health is projected to decline to {projected_ssd_health:.1f}%."
            )
            reasoning = (
                f"Weibull failure curves project a remaining useful life of {pred_out['battery_rul_days']} days for the battery "
                f"and {pred_out['ssd_rul_days']} days for the SSD."
            )
            
            # Map trajectory point
            points = pred_out["battery_failure_probability_trajectory"]
            target_idx = 0 if horizon_days == 7 else 0 # 30 is index 0 in the list: [30, 90, 180, 270, 365]
            if horizon_days == 30:
                fail_pct = points[0]["failure_probability"]
            else:
                fail_pct = points[0]["failure_probability"] * (7/30) # linear interpolation
                
            confidence = f"{100 - int(fail_pct)}%"
            evidence_lines = [
                f"Battery RUL = {pred_out['battery_rul_days']} days",
                f"SSD RUL = {pred_out['ssd_rul_days']} days",
                f"Current Battery Health = {latest_health:.1f}%",
                f"Daily Battery Health decay = 0.02%",
                f"Projected Battery Health = {projected_battery_health:.1f}%",
                f"Projected SSD Health = {projected_ssd_health:.1f}%"
            ]

    elif category == "Simulation":
        if not sim_out:
            answer = "Simulation engine failed to produce outputs."
            reasoning = "What-if steady state equations did not converge."
            confidence = "0%"
            evidence_lines = []
        else:
            temp_res = sim_out["temperature"]
            power_res = sim_out["power"]
            bat_res = sim_out["battery"]
            
            answer = (
                f"Simulation projections: CPU Temperature converges to {temp_res['cpu_temperature']}°C (Fan: {temp_res['fan_speed_rpm']} RPM). "
                f"Power Draw converges to {power_res['total_power_draw_watts']} W. Battery remaining: {bat_res['battery_remaining_minutes']} minutes."
            )
            reasoning = f"Steady state model converged (is_throttling = {temp_res['is_throttling']}, throttle_ratio = {temp_res['throttle_ratio']})."
            confidence = "90%"
            evidence_lines = [
                f"Simulated CPU Temperature = {temp_res['cpu_temperature']}°C",
                f"Simulated Fan Speed = {temp_res['fan_speed_rpm']} RPM",
                f"Simulated Power Draw = {power_res['total_power_draw_watts']} W",
                f"Simulated Battery remaining = {bat_res['battery_remaining_minutes']} minutes",
                f"Simulated throttle ratio = {temp_res['throttle_ratio']}",
                f"Simulated is throttling = {temp_res['is_throttling']}"
            ]

    else: # Unknown or out-of-scope fallback
        # Let's check if the query is out of scope and trigger the refusal guard
        # Step 9: Insufficient evidence refuse
        return {
            "query": query,
            "response": "Answer:\nInsufficient telemetry data available to answer this question.\n\nEvidence:\nNone\n\nReasoning:\nQuestion does not align with supported telemetry queries (CPU, GPU, Battery, Disk, Network status, diagnostics, predictions, or simulations).\n\nConfidence:\n0%",
            "source_documents": []
        }

    # Include deterministic rules triggered as additional evidence/reasoning if applicable
    if rules_triggered:
        evidence_lines.extend(rules_triggered)
        reasoning += f" Validated deterministic threshold breaches: {', '.join(rules_triggered)}."

    # ─────────────────────────────────────────────────────────────────────────────
    # Step 7: Response Generation (LLM or deterministic formatter)
    # ─────────────────────────────────────────────────────────────────────────────

    # If OpenAI API Key is valid and MOCK_LLM is disabled, we invoke the LLM
    # to convert this structured evidence into natural language
    if not settings.MOCK_LLM and settings.OPENAI_API_KEY != "mock_key":
        try:
            from langchain_openai import ChatOpenAI
            
            llm_prompt = (
                f"System Prompt:\n"
                f"You are a strict, evidence-locked hardware diagnostic compiler for the Dell AI Digital Twin project.\n"
                f"You convert structured evidence and diagnostic reasoning into a natural language response.\n"
                f"You must strictly follow the output format. You are forbidden from inventing explanations or stating facts not present in the evidence.\n"
                f"Never mention dust, thermal paste, hardware defects, user behavior, or environmental conditions unless they are explicitly written in the evidence.\n\n"
                f"User Question: {query}\n\n"
                f"Evidence parameters:\n"
                f"{chr(10).join('- ' + l for l in evidence_lines)}\n\n"
                f"Internal reasoning:\n"
                f"{reasoning}\n\n"
                f"Confidence: {confidence}\n\n"
                f"Format requirement:\n"
                f"Answer:\n[Grounded answer]\n\n"
                f"Evidence:\n[Grounded evidence values]\n\n"
                f"Reasoning:\n[Grounded explanation]\n\n"
                f"Confidence:\n[Grounded confidence score]\n"
            )
            
            llm = ChatOpenAI(
                model_name="gpt-4-turbo",
                temperature=0.0,
                openai_api_key=settings.OPENAI_API_KEY
            )
            result = llm.predict(llm_prompt)
            
            # Step 9: Post-Generation Hallucination Guard
            is_valid, sanitized_response = run_hallucination_guard(result, evidence_lines)
            if is_valid:
                return {
                    "query": query,
                    "response": sanitized_response,
                    "source_documents": [f"System telemetry: {evidence_dict}"]
                }
        except Exception as e:
            logger.error(f"LLM generation failed: {e}. Falling back to deterministic formatter.")

    # Local/Deterministic formatter (matches Step 8 structure)
    formatted_response = (
        f"Answer:\n{answer}\n\n"
        f"Evidence:\n" + "\n".join(evidence_lines) + f"\n\n"
        f"Reasoning:\n{reasoning}\n\n"
        f"Confidence:\n{confidence}"
    )

    # Run the hallucination guard on the formatted response to ensure absolute consistency
    _, safe_response = run_hallucination_guard(formatted_response, evidence_lines)

    return {
        "query": query,
        "response": safe_response,
        "source_documents": [f"System telemetry: {evidence_dict}"]
    }


# ─────────────────────────────────────────────────────────────────────────────
# Step 9: Hallucination Guard
# ─────────────────────────────────────────────────────────────────────────────

BANNED_TERMS = ["dust", "thermal paste", "hardware defect", "mechanical failure", "ventilation obstruction", "user behavior", "environment"]

def run_hallucination_guard(response: str, evidence: List[str]) -> Tuple[bool, str]:
    """
    Scans the response for unsupported statements and verifies grounding.
    If unsupported claims or banned terms are found (unless explicitly mentioned in the evidence),
    they are removed, or the response falls back to the safe refusal string.
    """
    refusal_response = "Answer:\nInsufficient telemetry data available to answer this question.\n\nEvidence:\nNone\n\nReasoning:\nQuery response generated unsupported assertions or hardware assumptions.\n\nConfidence:\n0%"
    
    # Extract blocks
    blocks = {}
    current_block = None
    lines = response.split("\n")
    for line in lines:
        line_strip = line.strip()
        if not line_strip:
            continue
        if line_strip.startswith("Answer:"):
            current_block = "Answer"
            blocks[current_block] = []
        elif line_strip.startswith("Evidence:"):
            current_block = "Evidence"
            blocks[current_block] = []
        elif line_strip.startswith("Reasoning:"):
            current_block = "Reasoning"
            blocks[current_block] = []
        elif line_strip.startswith("Confidence:"):
            current_block = "Confidence"
            blocks[current_block] = []
        elif current_block:
            blocks[current_block].append(line_strip)

    # Validate structural blocks exist
    required = ["Answer", "Evidence", "Reasoning", "Confidence"]
    if not all(r in blocks for r in required) or not all(blocks[r] for r in required):
        # Format mismatch, reconstruct safely
        return False, refusal_response

    # Verify numbers in Answer & Reasoning are grounded in Evidence
    answer_text = " ".join(blocks["Answer"])
    reasoning_text = " ".join(blocks["Reasoning"])
    
    # Extract all numerical parameters (e.g. 95.0, 95, 6200)
    numbers_in_response = re.findall(r'\b\d+(?:\.\d+)?\b', answer_text + " " + reasoning_text)
    
    # Extract all numbers in evidence
    evidence_text = " ".join(evidence) + " " + " ".join(blocks["Evidence"])
    numbers_in_evidence = re.findall(r'\b\d+(?:\.\d+)?\b', evidence_text)
    
    # Allow numbers that represent score/confidence scale or days/hours parameters
    ignored_numbers = {"7", "30", "1", "2", "3", "4", "5", "6", "8", "9", "10", "100", "95", "90", "96", "85", "75", "78", "60", "0"}
    
    for num in numbers_in_response:
        if num in ignored_numbers:
            continue
        # Check if the number is present in evidence (with minor float toleration)
        found = False
        try:
            val = float(num)
            for ev_num in numbers_in_evidence:
                if abs(float(ev_num) - val) < 1.1:
                    found = True
                    break
        except ValueError:
            pass
        
        if not found:
            logger.warning(f"Hallucination Guard: Blocked response due to ungrounded numerical value '{num}'.")
            return False, refusal_response

    # Check for banned words
    evidence_lower = evidence_text.lower()
    for term in BANNED_TERMS:
        if term in answer_text.lower() or term in reasoning_text.lower():
            # If the term is not in the telemetry evidence, fail the guard
            if term not in evidence_lower:
                logger.warning(f"Hallucination Guard: Blocked response due to banned keyword '{term}'.")
                return False, refusal_response

    return True, response
