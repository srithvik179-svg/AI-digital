"""
Unit tests for the Phase 7 Natural Language Summary Generator.
Validates template outputs, sentence content, severity, latency, and edge cases.
"""
import pytest
import time
from app.services.summary_engine import generate_summary, NLSummary


# ─── Helpers ──────────────────────────────────────────────────────────

def healthy_input():
    return dict(
        cpu_usage=20.0,
        memory_usage=35.0,
        disk_usage=40.0,
        cpu_temperature=48.0,
        battery_level=85.0,
        battery_health=92.0,
        fan_speed=1500,
        gpu_usage=10.0,
        signal_strength_dbm=-52.0,
        power_source="ac",
        health_score=95.0,
        health_category="Healthy",
        active_process_count=95,
        thermal_state="nominal",
        link_speed_mbps=300,
    )

def critical_input():
    return dict(
        cpu_usage=95.0,
        memory_usage=92.0,
        disk_usage=96.0,
        cpu_temperature=91.0,
        battery_level=5.0,
        battery_health=52.0,
        fan_speed=5200,
        gpu_usage=90.0,
        signal_strength_dbm=-88.0,
        power_source="battery",
        health_score=18.0,
        health_category="Critical",
        active_process_count=145,
        thermal_state="critical",
        link_speed_mbps=12,
    )


# ─── Output structure ─────────────────────────────────────────────────

class TestOutputStructure:
    def test_returns_nl_summary_dataclass(self):
        result = generate_summary(**healthy_input())
        assert isinstance(result, NLSummary)

    def test_headline_is_nonempty_string(self):
        result = generate_summary(**healthy_input())
        assert isinstance(result.headline, str)
        assert len(result.headline) > 10

    def test_paragraph_is_nonempty_string(self):
        result = generate_summary(**healthy_input())
        assert isinstance(result.paragraph, str)
        assert len(result.paragraph) > 20

    def test_observations_is_nonempty_list(self):
        result = generate_summary(**healthy_input())
        assert isinstance(result.observations, list)
        assert len(result.observations) >= 1

    def test_severity_is_valid_category(self):
        valid = {"Healthy", "Warning", "Critical"}
        for kwargs in [healthy_input(), critical_input()]:
            r = generate_summary(**kwargs)
            assert r.severity in valid, f"Invalid severity: {r.severity}"

    def test_generated_in_ms_is_positive_float(self):
        result = generate_summary(**healthy_input())
        assert isinstance(result.generated_in_ms, float)
        assert result.generated_in_ms >= 0.0


# ─── Latency requirement ──────────────────────────────────────────────

class TestLatency:
    def test_generates_in_under_1_second(self):
        """Phase 7 success criterion: summary must complete < 1 second."""
        t0 = time.perf_counter()
        generate_summary(**healthy_input())
        elapsed = time.perf_counter() - t0
        assert elapsed < 1.0, f"Summary took {elapsed:.3f}s — exceeds 1s limit"

    def test_generates_in_under_10ms_typically(self):
        """Expect sub-10ms (template engine should be < 1ms typically)."""
        times = []
        for _ in range(20):
            t0 = time.perf_counter()
            generate_summary(**healthy_input())
            times.append((time.perf_counter() - t0) * 1000)
        avg_ms = sum(times) / len(times)
        assert avg_ms < 10.0, f"Average latency {avg_ms:.2f}ms exceeds 10ms"

    def test_generated_in_ms_field_is_accurate(self):
        """The generated_in_ms field should match wall-clock within 5ms."""
        t0 = time.perf_counter()
        result = generate_summary(**healthy_input())
        elapsed_ms = (time.perf_counter() - t0) * 1000
        assert abs(result.generated_in_ms - elapsed_ms) < 5.0


# ─── Severity mapping ─────────────────────────────────────────────────

class TestSeverityMapping:
    def test_healthy_inputs_yield_healthy_severity(self):
        result = generate_summary(**healthy_input())
        assert result.severity == "Healthy"

    def test_critical_inputs_yield_critical_severity(self):
        result = generate_summary(**critical_input())
        assert result.severity == "Critical"

    def test_health_category_overrides_computed_severity(self):
        """When health_category is provided, it should be used for severity."""
        kwargs = healthy_input()
        kwargs["health_category"] = "Warning"
        kwargs["cpu_usage"] = 72.0
        result = generate_summary(**kwargs)
        assert result.severity == "Warning"


# ─── Content correctness ──────────────────────────────────────────────

class TestContentCorrectness:
    def test_high_cpu_mentioned_in_headline_or_observations(self):
        kwargs = healthy_input()
        kwargs["cpu_usage"] = 92.0
        kwargs["health_category"] = None
        result = generate_summary(**kwargs)
        all_text = result.headline + " ".join(result.observations) + result.paragraph
        assert "CPU" in all_text or "cpu" in all_text.lower()

    def test_low_battery_mentioned(self):
        kwargs = healthy_input()
        kwargs["battery_level"] = 6.0
        kwargs["power_source"] = "battery"
        result = generate_summary(**kwargs)
        all_text = result.headline + " ".join(result.observations) + result.paragraph
        assert "battery" in all_text.lower()

    def test_thermal_critical_state_mentioned(self):
        kwargs = healthy_input()
        kwargs["thermal_state"] = "critical"
        kwargs["cpu_temperature"] = 92.0
        result = generate_summary(**kwargs)
        all_text = result.headline + " ".join(result.observations) + result.paragraph
        assert "critical" in all_text.lower() or "thermal" in all_text.lower()

    def test_disk_critical_mentioned(self):
        kwargs = healthy_input()
        kwargs["disk_usage"] = 96.0
        result = generate_summary(**kwargs)
        all_text = " ".join(result.observations) + result.paragraph
        assert "disk" in all_text.lower()

    def test_weak_wifi_mentioned(self):
        kwargs = healthy_input()
        kwargs["signal_strength_dbm"] = -87.0
        result = generate_summary(**kwargs)
        all_text = " ".join(result.observations) + result.paragraph
        assert "signal" in all_text.lower() or "network" in all_text.lower()

    def test_headline_ends_with_period(self):
        result = generate_summary(**healthy_input())
        assert result.headline.endswith("."), f"Headline missing period: {result.headline}"

    def test_headline_starts_with_capital(self):
        result = generate_summary(**healthy_input())
        assert result.headline[0].isupper(), f"Headline not capitalised: {result.headline}"

    def test_paragraph_non_empty_for_all_tiers(self):
        for kwargs in [healthy_input(), critical_input()]:
            r = generate_summary(**kwargs)
            assert r.paragraph.strip() != ""

    def test_observations_all_non_empty(self):
        result = generate_summary(**critical_input())
        for obs in result.observations:
            assert obs.strip() != "", "Empty observation found"

    def test_deterministic_output(self):
        """Same inputs must produce identical outputs."""
        k = healthy_input()
        r1 = generate_summary(**k)
        r2 = generate_summary(**k)
        assert r1.headline == r2.headline
        assert r1.paragraph == r2.paragraph
        assert r1.severity == r2.severity


# ─── Optional params ──────────────────────────────────────────────────

class TestOptionalParams:
    def test_minimal_required_params_only(self):
        """Only 6 required params — must not raise."""
        result = generate_summary(
            cpu_usage=50.0,
            memory_usage=60.0,
            disk_usage=45.0,
            cpu_temperature=55.0,
            battery_level=70.0,
            battery_health=88.0,
        )
        assert result.headline
        assert result.paragraph
        assert result.severity in ("Healthy", "Warning", "Critical")

    def test_all_optional_params_provided(self):
        result = generate_summary(**critical_input())
        assert result.headline
        assert len(result.observations) >= 3

    def test_no_gpu_does_not_crash(self):
        kwargs = healthy_input()
        kwargs["gpu_usage"] = None
        result = generate_summary(**kwargs)
        assert result.headline

    def test_no_wifi_does_not_crash(self):
        kwargs = healthy_input()
        kwargs["signal_strength_dbm"] = None
        result = generate_summary(**kwargs)
        assert result.headline
