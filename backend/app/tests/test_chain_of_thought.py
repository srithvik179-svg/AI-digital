"""
Unit tests for Phase 37 Chain of Thought Service.
"""
import pytest
from app.services.ai_reasoning.chain_of_thought import (
    parse_cot_response,
    generate_local_cot
)

def test_parse_cot_response():
    """Ensure tagged sections are correctly parsed and stripped from the final answer."""
    raw = (
        "[Observation] CPU core temp is 88°C.\n"
        "[Thought] CPU is overheating (>85°C).\n"
        "[Action] Execute thermal clock throttling.\n"
        "[Analysis] Workload is heavy, causing thermal strain.\n"
        "[Answer] The CPU is hot but running stable at 88°C."
    )
    
    answer, steps = parse_cot_response(raw)
    
    assert answer == "The CPU is hot but running stable at 88°C."
    assert len(steps) == 4
    
    step_map = {s.step: s.content for s in steps}
    assert step_map["Observation"] == "CPU core temp is 88°C."
    assert step_map["Thought"] == "CPU is overheating (>85°C)."
    assert step_map["Action"] == "Execute thermal clock throttling."
    assert step_map["Analysis"] == "Workload is heavy, causing thermal strain."

def test_generate_local_cot():
    """Ensure local mock CoT generator produces all 4 reasoning steps with metric context."""
    evidence = [
        {
            "metric": "cpu_usage",
            "value": 90.0,
            "unit": "%",
            "timestamp": "2026-06-20 12:00:00",
            "citation": "[Source: Telemetry at 2026-06-20 12:00:00]"
        }
    ]
    
    steps = generate_local_cot("Is my CPU load high?", evidence)
    
    assert len(steps) == 4
    step_types = [s.step for s in steps]
    assert step_types == ["Observation", "Thought", "Action", "Analysis"]
    
    # Check that CPU details are in the Thought
    assert "CPU load is critical" in steps[1].content
    assert "Observation" in steps[0].step
    assert "90.0%" in steps[0].content
