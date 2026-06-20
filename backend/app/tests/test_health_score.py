"""
Unit tests for the Phase 5 Health Score Engine.
Tests scoring formula accuracy, edge cases, and category thresholds.
"""
import pytest
from app.services.health_score import compute_health_score, CATEGORY_HEALTHY, CATEGORY_WARNING, CATEGORY_CRITICAL


class TestHealthScoreFormula:
    """Verify the scoring formula produces correct scores for known inputs."""

    def test_perfect_system_scores_100(self):
        """All metrics at their best should score very close to 100."""
        result = compute_health_score(
            cpu_usage=5.0,
            memory_usage=20.0,
            disk_usage=10.0,
            cpu_temperature=40.0,
            battery_level=100.0,
            battery_health=100.0,
            gpu_usage=0.0,
            signal_strength_dbm=-30.0,
            power_source="ac",
            thermal_state="nominal",
        )
        assert result.score == 100.0, f"Expected 100, got {result.score}"
        assert result.category == CATEGORY_HEALTHY

    def test_critical_system_scores_low(self):
        """All metrics at worst values should score below 50 (Critical)."""
        result = compute_health_score(
            cpu_usage=98.0,
            memory_usage=97.0,
            disk_usage=97.0,
            cpu_temperature=93.0,
            battery_level=3.0,
            battery_health=38.0,
            gpu_usage=97.0,
            signal_strength_dbm=-92.0,
            power_source="battery",
            thermal_state="critical",
        )
        assert result.score < 50.0, f"Expected < 50, got {result.score}"
        assert result.category == CATEGORY_CRITICAL

    def test_warning_threshold_boundary(self):
        """Scores in 50-74 range should be categorised as Warning."""
        result = compute_health_score(
            cpu_usage=80.0,
            memory_usage=75.0,
            disk_usage=85.0,
            cpu_temperature=70.0,
            battery_level=35.0,
            battery_health=75.0,
            gpu_usage=0.0,
            signal_strength_dbm=-70.0,
            power_source="battery",
            thermal_state="moderate",
        )
        assert 50.0 <= result.score < 75.0, f"Expected Warning range, got {result.score}"
        assert result.category == CATEGORY_WARNING

    def test_healthy_threshold(self):
        """Score >= 75 is Healthy."""
        result = compute_health_score(
            cpu_usage=30.0,
            memory_usage=45.0,
            disk_usage=50.0,
            cpu_temperature=52.0,
            battery_level=75.0,
            battery_health=95.0,
        )
        assert result.score >= 75.0
        assert result.category == CATEGORY_HEALTHY

    def test_thermal_critical_override(self):
        """thermal_state='critical' forces temp_score to <= 10 regardless of actual temp."""
        # Low temperature but critical thermal_state flag
        result = compute_health_score(
            cpu_usage=20.0,
            memory_usage=30.0,
            disk_usage=20.0,
            cpu_temperature=50.0,      # normally fine
            battery_level=90.0,
            battery_health=95.0,
            thermal_state="critical",  # forced override
        )
        # With temp component capped at 10 and weight 22%, expect significant penalty
        assert result.score < 85.0, f"Thermal override should reduce score, got {result.score}"

    def test_score_clamped_between_0_and_100(self):
        """Score must never exceed 100 or drop below 0."""
        for _ in range(10):
            import random
            r = compute_health_score(
                cpu_usage=random.uniform(0, 100),
                memory_usage=random.uniform(0, 100),
                disk_usage=random.uniform(0, 100),
                cpu_temperature=random.uniform(20, 110),
                battery_level=random.uniform(0, 100),
                battery_health=random.uniform(0, 100),
                gpu_usage=random.uniform(0, 100),
                signal_strength_dbm=random.uniform(-100, -20),
            )
            assert 0.0 <= r.score <= 100.0, f"Score out of range: {r.score}"

    def test_no_optional_params_does_not_crash(self):
        """Should work fine with only the required 6 parameters."""
        result = compute_health_score(
            cpu_usage=50.0,
            memory_usage=60.0,
            disk_usage=40.0,
            cpu_temperature=55.0,
            battery_level=80.0,
            battery_health=90.0,
        )
        assert result.score > 0
        assert result.category in (CATEGORY_HEALTHY, CATEGORY_WARNING, CATEGORY_CRITICAL)

    def test_breakdown_keys_present(self):
        """Breakdown dict must always contain all 7 component keys."""
        result = compute_health_score(
            cpu_usage=50.0, memory_usage=50.0, disk_usage=50.0,
            cpu_temperature=55.0, battery_level=80.0, battery_health=90.0,
        )
        expected_keys = {"cpu", "memory", "gpu", "temperature", "battery", "disk", "wifi"}
        assert set(result.breakdown.keys()) == expected_keys

    def test_recommendations_populated_for_high_cpu(self):
        """Recommendations should mention CPU when it's critically high."""
        result = compute_health_score(
            cpu_usage=96.0,
            memory_usage=40.0,
            disk_usage=30.0,
            cpu_temperature=45.0,
            battery_level=90.0,
            battery_health=95.0,
        )
        assert any("CPU" in r for r in result.recommendations)

    def test_healthy_system_single_recommendation(self):
        """A perfect system should return a single 'all systems healthy' recommendation."""
        result = compute_health_score(
            cpu_usage=10.0,
            memory_usage=20.0,
            disk_usage=15.0,
            cpu_temperature=42.0,
            battery_level=95.0,
            battery_health=98.0,
            gpu_usage=5.0,
            signal_strength_dbm=-40.0,
        )
        assert len(result.recommendations) == 1
        assert "healthy parameters" in result.recommendations[0].lower()

    def test_low_battery_recommendation(self):
        """Battery < 10% should trigger a 'critically low' recommendation."""
        result = compute_health_score(
            cpu_usage=30.0,
            memory_usage=50.0,
            disk_usage=40.0,
            cpu_temperature=52.0,
            battery_level=4.0,
            battery_health=90.0,
            power_source="battery",
        )
        assert any("critically low" in r.lower() for r in result.recommendations)

    def test_weak_wifi_recommendation(self):
        """Very weak WiFi should trigger a WiFi recommendation."""
        result = compute_health_score(
            cpu_usage=30.0,
            memory_usage=50.0,
            disk_usage=40.0,
            cpu_temperature=52.0,
            battery_level=80.0,
            battery_health=90.0,
            signal_strength_dbm=-91.0,
        )
        assert any("WiFi" in r or "signal" in r.lower() for r in result.recommendations)

    def test_score_is_deterministic(self):
        """Same inputs must always produce the same score."""
        kwargs = dict(
            cpu_usage=65.0, memory_usage=72.0, disk_usage=55.0,
            cpu_temperature=68.0, battery_level=45.0, battery_health=85.0,
            gpu_usage=20.0, signal_strength_dbm=-58.0,
        )
        r1 = compute_health_score(**kwargs)
        r2 = compute_health_score(**kwargs)
        assert r1.score == r2.score
        assert r1.category == r2.category
