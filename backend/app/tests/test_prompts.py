"""
Unit tests for Phase 36 Prompt Engineering Registry.
"""
import pytest
from app.services.ai_reasoning.prompts import prompt_registry

def test_prompt_rendering_variables():
    """Ensure all template variables are dynamically populated in the prompt text."""
    prompt = prompt_registry.get_prompt(
        personality="diagnostic_engineer",
        device_id="macbook-1",
        alerts_count=3,
        health_score=85.0,
        health_category="Warning",
        context="Sample context logs",
        question="How hot is the CPU?"
    )
    
    assert "macbook-1" in prompt
    assert "3" in prompt
    assert "85" in prompt
    assert "Warning" in prompt
    assert "Sample context logs" in prompt
    assert "How hot is the CPU?" in prompt
    assert "diagnostic engineer" in prompt.lower()

def test_prompt_personality_selection():
    """Ensure correct personality template is selected."""
    eco_prompt = prompt_registry.get_prompt(
        personality="eco_assistant",
        device_id="macbook-1",
        alerts_count=0,
        health_score=100.0,
        health_category="Healthy",
        context="Context",
        question="Query"
    )
    assert "green-computing" in eco_prompt.lower()
    
    safety_prompt = prompt_registry.get_prompt(
        personality="safety_expert",
        device_id="macbook-1",
        alerts_count=0,
        health_score=100.0,
        health_category="Healthy",
        context="Context",
        question="Query"
    )
    assert "safety expert" in safety_prompt.lower()

def test_prompt_fallback():
    """Ensure request for non-existent personality falls back gracefully to diagnostic_engineer."""
    fallback_prompt = prompt_registry.get_prompt(
        personality="unsupported_personality",
        device_id="macbook-1",
        alerts_count=0,
        health_score=100.0,
        health_category="Healthy",
        context="Context",
        question="Query"
    )
    assert "diagnostic engineer" in fallback_prompt.lower()
