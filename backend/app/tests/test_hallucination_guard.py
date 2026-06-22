"""
Unit tests for Step 9 — Hallucination Guard.

Tests cover:
  1. Safe block when response contains banned keywords not present in evidence (dust, paste, defects, behavior, environment).
  2. Safe block when response contains ungrounded numerical claims.
  3. Valid responses pass the guard without modifications.
"""

from __future__ import annotations
import pytest

from app.services.evidence_chatbot import run_hallucination_guard

class TestHallucinationGuard:

    def test_valid_grounded_response_passes(self):
        evidence = ["CPU Usage = 45.2%", "CPU Temperature = 68.0°C"]
        response = (
            "Answer:\nCPU temperature is stable at 68.0°C under 45.2% load.\n\n"
            "Evidence:\nCPU Usage = 45.2%\nCPU Temperature = 68.0°C\n\n"
            "Reasoning:\nRetrievals show stable parameters.\n\n"
            "Confidence:\n100%"
        )
        is_valid, out = run_hallucination_guard(response, evidence)
        assert is_valid is True
        assert out == response

    def test_banned_keyword_blocked(self):
        evidence = ["CPU Usage = 97.0%", "CPU Temperature = 98.0°C"]
        # Response mentions "dust" and "thermal paste" which are banned terms
        response = (
            "Answer:\nLaptop is hot because dust is blocking vents.\n\n"
            "Evidence:\nCPU Usage = 97.0%\nCPU Temperature = 98.0°C\n\n"
            "Reasoning:\nWorkloads and dust caused the thermal stress. Thermal paste might be dried.\n\n"
            "Confidence:\n85%"
        )
        is_valid, out = run_hallucination_guard(response, evidence)
        assert is_valid is False
        assert "Insufficient telemetry data available" in out

    def test_ungrounded_numerical_claim_blocked(self):
        evidence = ["CPU Usage = 25.0%", "CPU Temperature = 50.0°C"]
        # Response claims CPU is at 99% usage, which is not in evidence
        response = (
            "Answer:\nCPU usage is critically high at 99.0%.\n\n"
            "Evidence:\nCPU Usage = 25.0%\nCPU Temperature = 50.0°C\n\n"
            "Reasoning:\nHigh load detected.\n\n"
            "Confidence:\n95%"
        )
        is_valid, out = run_hallucination_guard(response, evidence)
        assert is_valid is False
        assert "Insufficient telemetry data available" in out

    def test_ignored_scale_numbers_allowed(self):
        # Scale numbers like 7, 30 days, 100%, 0% etc are allowed even if not in evidence
        evidence = ["CPU Usage = 25.0%", "CPU Temperature = 50.0°C"]
        response = (
            "Answer:\nCPU usage is 25.0%. Projections over a 7-day horizon are nominal (100% survival).\n\n"
            "Evidence:\nCPU Usage = 25.0%\nCPU Temperature = 50.0°C\n\n"
            "Reasoning:\nWeibull forecast shows 100% confidence for next 7 days.\n\n"
            "Confidence:\n100%"
        )
        is_valid, out = run_hallucination_guard(response, evidence)
        assert is_valid is True
        assert out == response
