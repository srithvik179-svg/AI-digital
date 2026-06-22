"""
Unit tests for Phase 34 Evidence Extraction Service.
"""
import pytest
from app.services.ai_reasoning.evidence_extractor import (
    extract_evidence_from_doc,
    extract_evidence
)

def test_extract_evidence_from_doc():
    """Ensure regex pattern matching successfully parses all target metrics from a record."""
    record = (
        "[Telemetry Record for test-laptop at 2026-06-20 12:00:00] "
        "CPU load is 45.2%. Memory usage is 68.1%. Disk usage space used is 40.5%. "
        "CPU core temperature is 55.0°C with cooling fan active at 2400 RPM. "
        "Battery charge level is 85.0% (health: 92.0%) connected via power source AC. "
        "Active running processes: 112. GPU usage is 15.5% with temperature 58.0°C. "
        "CPU frequency is 2400.0 MHz. Battery cycle count is 145."
    )
    
    evidence = extract_evidence_from_doc(record)
    
    # Map metrics to list for checking
    metrics_map = {item.metric: item for item in evidence}
    
    assert "cpu_usage" in metrics_map
    assert metrics_map["cpu_usage"].value == 45.2
    assert metrics_map["cpu_usage"].unit == "%"
    assert metrics_map["cpu_usage"].timestamp == "2026-06-20 12:00:00"
    assert metrics_map["cpu_usage"].citation == "[Source: Telemetry at 2026-06-20 12:00:00]"
    
    assert "cpu_temperature" in metrics_map
    assert metrics_map["cpu_temperature"].value == 55.0
    assert metrics_map["cpu_temperature"].unit == "°C"
    
    assert "fan_speed" in metrics_map
    assert metrics_map["fan_speed"].value == 2400.0
    assert metrics_map["fan_speed"].unit == "RPM"
    
    assert "battery_level" in metrics_map
    assert metrics_map["battery_level"].value == 85.0
    
    assert "gpu_usage" in metrics_map
    assert metrics_map["gpu_usage"].value == 15.5
    
    assert "cycle_count" in metrics_map
    assert metrics_map["cycle_count"].value == 145.0
    assert metrics_map["cycle_count"].unit == "cycles"

def test_extract_evidence_multiple_docs():
    """Ensure extracting across multiple documents aggregates and sorts metrics correctly."""
    doc1 = (
        "[Telemetry Record for test-laptop at 2026-06-20 12:00:00] "
        "CPU load is 10.0%. Battery charge level is 90.0%."
    )
    doc2 = (
        "[Telemetry Record for test-laptop at 2026-06-20 12:05:00] "
        "CPU load is 80.0%. Battery charge level is 88.0%."
    )
    
    evidence = extract_evidence([doc1, doc2])
    
    # Verify we get values from both timestamps
    cpu_events = [item for item in evidence if item.metric == "cpu_usage"]
    assert len(cpu_events) == 2
    # Sorted descending by timestamp, so 12:05:00 should be first
    assert cpu_events[0].timestamp == "2026-06-20 12:05:00"
    assert cpu_events[0].value == 80.0
    assert cpu_events[1].timestamp == "2026-06-20 12:00:00"
    assert cpu_events[1].value == 10.0
