"""
AI Guardrails Service — Phase 35.
Handles input query sanitization/validation and output hallucination alignment checks.
"""
import re
from typing import List, Dict, Any, Tuple, Optional
from pydantic import BaseModel
from app.services.ai_reasoning.evidence_extractor import EvidenceItem
from app.core.logging import logger

class GuardrailStatus(BaseModel):
    is_valid: bool
    reason: Optional[str] = None
    sanitized_query: str

def validate_input(query: str) -> GuardrailStatus:
    """
    Validates the input query for prompt injections, SQL injections, and out-of-scope topics.
    """
    sanitized = query.strip()
    
    # 1. SQL Injection check
    sql_patterns = [
        r'\bunion\b.*\bselect\b',
        r'\bdrop\s+table\b',
        r'\binsert\s+into\b',
        r'\bdelete\s+from\b',
        r'\bselect\b.*\bfrom\b.*--'
    ]
    for pattern in sql_patterns:
        if re.search(pattern, sanitized, re.IGNORECASE):
            return GuardrailStatus(
                is_valid=False,
                reason="Malicious query pattern detected (SQL Injection risk).",
                sanitized_query=sanitized
            )
            
    # 2. Prompt Injection check
    injection_patterns = [
        r'ignore\s+all\s+previous\s+instructions',
        r'ignore\s+instructions\s+above',
        r'you\s+are\s+now\s+a\s+roleplay',
        r'system\s+prompt',
        r'bypass\s+restrictions'
    ]
    for pattern in injection_patterns:
        if re.search(pattern, sanitized, re.IGNORECASE):
            return GuardrailStatus(
                is_valid=False,
                reason="Prompt injection attempt detected.",
                sanitized_query=sanitized
            )

    # 3. Out-of-scope check
    scope_keywords = [
        "cpu", "gpu", "battery", "disk", "temp", "fan", "heat", "hot", "power", 
        "charge", "performance", "usage", "process", "processes", "signal", "wifi",
        "eco", "kill"
    ]
    query_lower = sanitized.lower()
    is_in_scope = any(kw in query_lower for kw in scope_keywords)
    if not is_in_scope:
        return GuardrailStatus(
            is_valid=False,
            reason="I cannot find evidence in the telemetry logs to answer this question.",
            sanitized_query=sanitized
        )
        
    return GuardrailStatus(is_valid=True, sanitized_query=sanitized)


def validate_output(response: str, evidence: List[EvidenceItem]) -> Tuple[bool, str]:
    """
    Validates that numerical claims in the response align with the extracted evidence.
    If a claim cannot be verified against the evidence list, it is marked as a hallucination,
    and the output is replaced with the grounded refusal string.
    """
    # Exclude the refusal string itself from validation
    refusal_msg = "I cannot find evidence in the telemetry logs to answer this question."
    if refusal_msg in response:
        return True, response

    # Tokenize response into sentences
    sentences = re.split(r'(?<=[.!?])\s+', response)
    
    # Define validation rules: (prefix_value_regex, metric_name)
    claim_patterns: List[Tuple[str, str]] = [
        # GPU Metrics
        (r'gpu\s*(?:usage|load|utilization)?\s*(?:is)?\s*(\d+\.?\d*)\s*%', "gpu_usage"),
        (r'gpu\s*(?:temperature|temp).*?(\d+\.?\d*)\s*(?:°c|c)(?![a-z])', "gpu_temperature"),
        
        # CPU Metrics
        (r'cpu\s*(?:usage|load|utilization)\s*(?:is)?\s*(\d+\.?\d*)\s*%', "cpu_usage"),
        (r'cpu\s*status\s*:\s*utilization\s*is\s*(\d+\.?\d*)\s*%', "cpu_usage"),
        
        # Memory
        (r'memory\s*(?:usage|load)?\s*(?:is)?\s*(\d+\.?\d*)\s*%', "memory_usage"),
        
        # Disk Space
        (r'disk\s*(?:usage|space\s+used)?\s*(?:is)?\s*(\d+\.?\d*)\s*%', "disk_usage"),
        (r'disk\s*status\s*:\s*space\s+used\s+is\s*(\d+\.?\d*)\s*%', "disk_usage"),
        
        # CPU Thermals
        (r'cpu\s*(?:core\s+)?(?:temperature|temp)\s*(?:is)?\s*(\d+\.?\d*)\s*(?:°c|c)(?![a-z])', "cpu_temperature"),
        (r'thermal\s*status\s*:\s*cpu\s*temperature\s*is\s*(\d+\.?\d*)\s*(?:°c|c)(?![a-z])', "cpu_temperature"),
        
        # Fan RPM
        (r'fan\s*(?:speed|rpm)?\s*(?:active\s+at|is)?\s*(\d+)\s*rpm', "fan_speed"),
        
        # Battery
        (r'battery\s*status\s*:\s*charge\s+level\s+is\s*(\d+\.?\d*)\s*%', "battery_level"),
        (r'battery\s*(?:level|charge)?\s*(?:is)?\s*(\d+\.?\d*)\s*%', "battery_level"),
        (r'health\s*:\s*(\d+\.?\d*)\s*%', "battery_health"),
        (r'health\s+is\s+(\d+\.?\d*)\s*%', "battery_health"),
        
        # CPU Frequency
        (r'cpu\s*frequency\s*(?:is)?\s*(\d+\.?\d*)\s*mhz', "cpu_frequency_mhz"),
        
        # Cycle counts & processes
        (r'cycle\s*count\s*(?:is)?\s*(\d+)', "cycle_count"),
        (r'(\d+)\s*cycles', "cycle_count"),
        (r'(\d+)\s*active\s*processes', "active_processes"),
    ]

    for sentence in sentences:
        sentence_lower = sentence.lower()
        for val_pattern, metric_name in claim_patterns:
            match = re.search(val_pattern, sentence_lower)
            if match:
                try:
                    claim_val = float(match.group(1))
                except (ValueError, IndexError):
                    continue
                
                # Verify if this claim exists in our evidence list
                matched_evidence = [
                    item for item in evidence 
                    if item.metric == metric_name and abs(item.value - claim_val) < 0.2
                ]
                
                if not matched_evidence:
                    logger.warning(
                        f"Hallucination Blocked: Claim '{sentence}' asserted value {claim_val} "
                        f"for metric '{metric_name}', but no such value exists in the evidence logs."
                    )
                    return False, refusal_msg
                        
    return True, response
