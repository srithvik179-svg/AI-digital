"""
Chain of Thought Service — Phase 37.
Generates and parses intermediate reasoning steps (Observation, Thought, Action, Analysis).
"""
import re
from typing import List, Dict, Any, Tuple
from pydantic import BaseModel

class ReasoningStep(BaseModel):
    step: str
    content: str

def parse_cot_response(raw_response: str) -> Tuple[str, List[ReasoningStep]]:
    """
    Parses a raw LLM response that contains [Observation], [Thought], [Action], [Analysis], and [Answer] tags.
    """
    steps = []
    final_answer = raw_response
    
    # Regular expressions for tags
    tags = ["Observation", "Thought", "Action", "Analysis"]
    
    # Extract tags
    for tag in tags:
        match = re.search(rf'\[{tag}\](.*?)(?=\[|$)', raw_response, re.DOTALL | re.IGNORECASE)
        if match:
            content = match.group(1).strip()
            # Remove any trailing tags
            for other in tags + ["Answer"]:
                content = re.sub(rf'\[{other}\].*$', '', content, flags=re.DOTALL | re.IGNORECASE).strip()
            steps.append(ReasoningStep(step=tag, content=content))
            
    # Extract final answer
    answer_match = re.search(r'\[Answer\](.*)', raw_response, re.DOTALL | re.IGNORECASE)
    if answer_match:
        final_answer = answer_match.group(1).strip()
        
    return final_answer, steps

def generate_local_cot(query: str, evidence: List[Dict[str, Any]]) -> List[ReasoningStep]:
    """
    Generates a deterministic reasoning chain for local mock mode.
    """
    query_lower = query.lower()
    steps = []
    
    # 1. Observation Step
    obs_lines = []
    for item in evidence:
        obs_lines.append(f"Observed {item['metric']} value of {item['value']}{item['unit']} at {item['timestamp']}.")
    obs_content = " ".join(obs_lines) if obs_lines else "No direct telemetry records found in retrieval context."
    steps.append(ReasoningStep(step="Observation", content=obs_content))
    
    # 2. Thought Step
    thought_lines = []
    if any(k in query_lower for k in ["cpu", "processes"]):
        cpu_item = next((i for i in evidence if i["metric"] == "cpu_usage"), None)
        if cpu_item:
            if cpu_item["value"] > 85:
                thought_lines.append("CPU load is critical, suggesting CPU thrashing or intense workload.")
            elif cpu_item["value"] > 50:
                thought_lines.append("CPU load is moderate; processing queries cleanly.")
            else:
                thought_lines.append("CPU load is low, laptop is mostly idle.")
                
    if any(k in query_lower for k in ["temp", "temperature", "hot", "heat", "fan"]):
        temp_item = next((i for i in evidence if i["metric"] == "cpu_temperature"), None)
        if temp_item:
            if temp_item["value"] > 75:
                thought_lines.append("Processor thermals are elevated; fan should ramp to high speed to cool cores.")
            else:
                thought_lines.append("Thermals are within normal operating bounds.")
                
    if any(k in query_lower for k in ["battery", "charge", "power"]):
        bat_item = next((i for i in evidence if i["metric"] == "battery_level"), None)
        if bat_item:
            if bat_item["value"] < 20:
                thought_lines.append("Battery capacity is critically low (<20%), power saving profiles should engage.")
            else:
                thought_lines.append("Battery reserves are sufficient.")
                
    thought_content = " ".join(thought_lines) if thought_lines else "Analyzing query context against active thresholds."
    steps.append(ReasoningStep(step="Thought", content=thought_content))
    
    # 3. Action Step
    action_lines = []
    if any(k in query_lower for k in ["temp", "heat", "fan", "hot"]):
        action_lines.append("Evaluating correlation weights between CPU load, Temperature, and Fan Speed.")
    if any(k in query_lower for k in ["battery", "power"]):
        action_lines.append("Checking power draw rates and CC/CV charge curves.")
    action_content = " ".join(action_lines) if action_lines else "Compiling matching telemetry logs to formulate grounded diagnostics response."
    steps.append(ReasoningStep(step="Action", content=action_content))
    
    # 4. Analysis Step
    analysis_lines = []
    for item in evidence:
        analysis_lines.append(f"Analyzed {item['metric']} ({item['value']}{item['unit']}).")
    analysis_content = " ".join(analysis_lines) if analysis_lines else "Verifying data constraints to guarantee response carries no hallucinations."
    steps.append(ReasoningStep(step="Analysis", content=analysis_content))
    
    return steps
