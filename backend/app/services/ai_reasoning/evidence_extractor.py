"""
Evidence Extraction Service — Phase 34.
Parses retrieved telemetry records to compile structured, cited evidence records.
"""
import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

class EvidenceItem(BaseModel):
    metric: str
    value: float
    unit: str
    timestamp: str
    citation: str

def extract_evidence_from_doc(doc: str) -> List[EvidenceItem]:
    """
    Parses a single telemetry document string and extracts structured evidence metrics.
    """
    evidence = []
    
    # Extract timestamp
    ts_match = re.search(r'\[Telemetry Record for .*? at ([\d\-\:\s]+)\]', doc)
    if not ts_match:
        # Fallback to source format citation
        ts_match = re.search(r'Source: Telemetry at ([\d\-\:\s]+)', doc)
        
    timestamp = ts_match.group(1).strip() if ts_match else "unknown"
    citation = f"[Source: Telemetry at {timestamp}]"

    # Define extraction patterns: (metric_name, regex, unit, cast_type)
    patterns = [
        ("cpu_usage", r'cpu load is ([\d\.]+)%', "%", float),
        ("cpu_usage", r'cpu usage is ([\d\.]+)%', "%", float),
        ("memory_usage", r'memory usage is ([\d\.]+)%', "%", float),
        ("disk_usage", r'disk usage space used is ([\d\.]+)%', "%", float),
        ("disk_usage", r'disk usage: ([\d\.]+)%', "%", float),
        ("cpu_temperature", r'cpu core temperature is ([\d\.]+)°c', "°C", float),
        ("cpu_temperature", r'cpu core temperature: ([\d\.]+)°c', "°C", float),
        ("fan_speed", r'cooling fan active at ([\d\.]+) rpm', "RPM", float),
        ("fan_speed", r'fan: ([\d\.]+) rpm', "RPM", float),
        ("battery_level", r'battery charge level is ([\d\.]+)%', "%", float),
        ("battery_level", r'battery level: ([\d\.]+)%', "%", float),
        ("battery_health", r'health: ([\d\.]+)%', "%", float),
        ("active_processes", r'active running processes: (\d+)', "processes", int),
        ("gpu_usage", r'gpu usage is ([\d\.]+)%', "%", float),
        ("gpu_temperature", r'gpu temperature is ([\d\.]+)°c', "°C", float),
        ("gpu_temperature", r'temperature ([\d\.]+)°c', "°C", float),
        ("cpu_frequency_mhz", r'cpu frequency is ([\d\.]+) mhz', "MHz", float),
        ("cycle_count", r'battery cycle count is (\d+)', "cycles", int),
    ]

    doc_lower = doc.lower()
    for metric, pattern, unit, cast in patterns:
        match = re.search(pattern, doc_lower)
        if match:
            try:
                val = cast(match.group(1))
                evidence.append(EvidenceItem(
                    metric=metric,
                    value=float(val),
                    unit=unit,
                    timestamp=timestamp,
                    citation=citation
                ))
            except (ValueError, TypeError):
                continue
                
    return evidence

def extract_evidence(documents: List[str]) -> List[EvidenceItem]:
    """
    Extracts structured evidence items across a list of document strings.
    Deduplicates by keeping the latest evidence per metric.
    """
    all_evidence = []
    seen = set()
    
    # Process documents in reverse chronological order (assume list is ordered or we parse timestamp)
    # Parse and sort documents by parsed timestamp if possible
    parsed_docs = []
    for doc in documents:
        ts_match = re.search(r'\[Telemetry Record for .*? at ([\d\-\:\s]+)\]', doc)
        if not ts_match:
            ts_match = re.search(r'Source: Telemetry at ([\d\-\:\s]+)', doc)
        ts = ts_match.group(1).strip() if ts_match else "0000-00-00 00:00:00"
        parsed_docs.append((ts, doc))
        
    # Sort descending by timestamp
    parsed_docs.sort(key=lambda x: x[0], reverse=True)
    
    for _, doc in parsed_docs:
        doc_evidence = extract_evidence_from_doc(doc)
        for item in doc_evidence:
            key = (item.metric, item.timestamp)
            if key not in seen:
                seen.add(key)
                all_evidence.append(item)
                
    return all_evidence
