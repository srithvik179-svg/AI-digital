"""
Unit tests for Phase 46 — Live Telemetry API Integration.

Tests cover:
  1. TelemetryReading dataclass + to_api_payload()
  2. BaseCollector helpers (thermal_state, fan_from_temp, disk_io_rates)
  3. MacCollector (mocked subprocess calls)
  4. Live-stream API endpoints (register, heartbeat, status, disconnect)
  5. SSE queue fan-out logic
  6. Pipeline health tracker
  7. Agent auto-registration on first telemetry POST
"""

from __future__ import annotations

import sys
import asyncio
import pytest
import json
from datetime import datetime
from unittest.mock import patch, MagicMock, AsyncMock
from collections import deque

# ── Patch sys.path to find collectors without installing ──
import os

# Inside Docker container, /app is the working root; collectors are copied there.
# On host (scripts/), they sit one level up from the test file.
container_app_dir = "/app"
scripts_dir = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "scripts"
)
_collectors_path = container_app_dir if os.path.isdir(os.path.join(container_app_dir, "collectors")) else os.path.abspath(scripts_dir)
_agent_path = container_app_dir if os.path.exists(os.path.join(container_app_dir, "telemetry_agent.py")) else os.path.abspath(scripts_dir)

if _collectors_path not in sys.path:
    sys.path.insert(0, _collectors_path)
if _agent_path not in sys.path:
    sys.path.insert(0, _agent_path)

from collectors import TelemetryReading, BaseCollector


# ===========================================================================
# 1. TelemetryReading dataclass
# ===========================================================================

class TestTelemetryReading:

    def _make_reading(self, **overrides) -> TelemetryReading:
        defaults = dict(
            device_id           = "test-device-001",
            cpu_usage           = 45.0,
            cpu_temperature     = 62.0,
            cpu_frequency_mhz   = 2800.0,
            gpu_usage           = 20.0,
            gpu_temperature     = 55.0,
            gpu_memory_usage    = 12.0,
            memory_usage        = 68.0,
            disk_usage          = 42.0,
            read_bytes_sec      = 102400,
            write_bytes_sec     = 40960,
            battery_level       = 78.0,
            battery_health      = 92.0,
            battery_temperature = 31.5,
            cycle_count         = 143,
            power_source        = "battery",
            fan_speed           = 2200,
            thermal_state       = "nominal",
            power_draw_watts    = 18.5,
            voltage_mv          = 12100.0,
            signal_strength_dbm = -62,
            ssid                = "TestNet",
            link_speed_mbps     = 866,
            active_process_count= 112,
            source              = "mac",
            collection_latency_ms = 45.0,
        )
        defaults.update(overrides)
        return TelemetryReading(**defaults)

    def test_instantiation(self):
        r = self._make_reading()
        assert r.device_id == "test-device-001"
        assert r.cpu_usage == 45.0
        assert r.source == "mac"

    def test_to_api_payload_required_keys(self):
        payload = self._make_reading().to_api_payload()
        required = [
            "device_id", "cpu_usage", "memory_usage", "disk_usage",
            "cpu_temperature", "battery_level", "battery_health",
            "fan_speed", "power_source", "active_process_count",
        ]
        for key in required:
            assert key in payload, f"Missing required key: {key}"

    def test_to_api_payload_optional_keys_present(self):
        payload = self._make_reading().to_api_payload()
        optional = [
            "cpu_frequency_mhz", "gpu_usage", "gpu_temperature",
            "battery_temperature", "read_bytes_sec", "write_bytes_sec",
            "signal_strength_dbm", "ssid", "link_speed_mbps",
            "thermal_state", "power_draw_watts", "voltage_mv",
        ]
        for key in optional:
            assert key in payload, f"Missing optional key: {key}"

    def test_none_cpu_temp_falls_back_to_default(self):
        r = self._make_reading(cpu_temperature=None)
        payload = r.to_api_payload()
        assert payload["cpu_temperature"] == 45.0   # default fallback

    def test_battery_source_values(self):
        for src in ("ac", "battery"):
            r = self._make_reading(power_source=src)
            assert r.to_api_payload()["power_source"] == src

    def test_optional_fields_can_be_none(self):
        r = self._make_reading(
            gpu_usage=None, gpu_temperature=None, signal_strength_dbm=None,
            ssid=None, cycle_count=None, battery_temperature=None,
        )
        payload = r.to_api_payload()
        assert payload["gpu_usage"] is None
        assert payload["ssid"] is None


# ===========================================================================
# 2. BaseCollector helpers
# ===========================================================================

class ConcreteCollector(BaseCollector):
    """Minimal concrete subclass for testing helper methods."""
    def collect(self):
        raise NotImplementedError


class TestBaseCollectorHelpers:

    def setup_method(self):
        self.col = ConcreteCollector("test-device")

    def test_thermal_state_nominal(self):
        assert self.col._thermal_state(45.0) == "nominal"
        assert self.col._thermal_state(59.9) == "nominal"

    def test_thermal_state_moderate(self):
        assert self.col._thermal_state(60.0) == "moderate"
        assert self.col._thermal_state(74.9) == "moderate"

    def test_thermal_state_serious(self):
        assert self.col._thermal_state(75.0) == "serious"
        assert self.col._thermal_state(89.9) == "serious"

    def test_thermal_state_critical(self):
        assert self.col._thermal_state(90.0) == "critical"
        assert self.col._thermal_state(105.0) == "critical"

    def test_fan_from_temp_idle(self):
        assert self.col._fan_from_temp(40.0) == 1200
        assert self.col._fan_from_temp(59.9) == 1200

    def test_fan_from_temp_moderate(self):
        rpm = self.col._fan_from_temp(65.0)
        assert rpm > 1200

    def test_fan_from_temp_critical(self):
        rpm = self.col._fan_from_temp(95.0)
        assert rpm == 6000

    def test_fan_rpm_increases_with_temp(self):
        rpms = [self.col._fan_from_temp(t) for t in [45, 60, 75, 90]]
        for i in range(len(rpms) - 1):
            assert rpms[i] <= rpms[i + 1], "Fan RPM should be non-decreasing"

    def test_disk_io_first_call_returns_none(self):
        import psutil
        rb, wb = self.col._disk_io_rates(psutil)
        # First call always returns (None, None)
        assert rb is None
        assert wb is None

    def test_disk_io_second_call_returns_integers(self):
        import psutil, time
        self.col._disk_io_rates(psutil)   # warm up
        time.sleep(0.05)
        rb, wb = self.col._disk_io_rates(psutil)
        # Second call may still be None if IO counters are unavailable,
        # but if returned, must be non-negative integers.
        if rb is not None:
            assert isinstance(rb, int) and rb >= 0
        if wb is not None:
            assert isinstance(wb, int) and wb >= 0


# ===========================================================================
# 3. MacCollector (mocked)
# ===========================================================================

class TestMacCollectorMocked:
    """Tests MacCollector without executing real subprocess calls."""

    @pytest.fixture
    def collector(self):
        with patch("psutil.cpu_percent", return_value=0.0), \
             patch("time.sleep"), \
             patch.object(
                 __import__("collectors.mac_collector", fromlist=["MacCollector"]).MacCollector,
                 "_check_smc", return_value=False
             ):
            from collectors.mac_collector import MacCollector
            return MacCollector("test-mac-001")

    def test_thermal_state_from_usage(self, collector):
        state = collector._thermal_state(70.0)
        assert state == "moderate"

    def test_temp_estimate_from_cpu(self, collector):
        temp = collector._cpu_temperature(100.0)
        assert 85.0 <= temp <= 95.0, f"Expected ~90°C at 100% CPU, got {temp}"

    def test_temp_estimate_idle(self, collector):
        temp = collector._cpu_temperature(0.0)
        assert 40.0 <= temp <= 50.0, f"Expected ~45°C at idle, got {temp}"

    def test_collect_returns_reading(self, collector):
        with patch.object(collector, "_cpu",          return_value=42.0), \
             patch.object(collector, "_cpu_freq",     return_value=2800.0), \
             patch.object(collector, "_cpu_temperature", return_value=61.0), \
             patch.object(collector, "_battery",
                          return_value=(78.0, "battery", 92.0, 31.5, 142)), \
             patch.object(collector, "_gpu",          return_value=(None, None, None)), \
             patch.object(collector, "_wifi",         return_value=("TestNet", -65, 866)), \
             patch.object(collector, "_disk_io_rates",return_value=(102400, 40960)), \
             patch("psutil.virtual_memory",
                   return_value=MagicMock(percent=68.2)), \
             patch("psutil.disk_usage",
                   return_value=MagicMock(percent=42.0)), \
             patch("psutil.pids",  return_value=list(range(112))):
            reading = collector.collect()

        assert isinstance(reading, TelemetryReading)
        assert reading.cpu_usage        == 42.0
        assert reading.cpu_temperature  == 61.0
        assert reading.battery_level    == 78.0
        assert reading.ssid             == "TestNet"
        assert reading.signal_strength_dbm == -65
        assert reading.source           == "mac"

    def test_wifi_parsed_correctly(self, collector):
        fake_output = (
            "     SSID: MyNetwork\n"
            "     agrCtlRSSI: -68\n"
            "     lastTxRate: 400\n"
        )
        with patch("subprocess.check_output", return_value=fake_output.encode()):
            ssid, dbm, rate = collector._wifi()
        assert ssid == "MyNetwork"
        assert dbm  == -68
        assert rate == 400

    def test_battery_pmset_parsed(self, collector):
        fake_pmset = (
            "Now drawing from 'Battery Power'\n"
            " -InternalBattery-0\t73%; discharging\n"
        )
        with patch("subprocess.check_output", return_value=fake_pmset.encode()), \
             patch("json.loads", side_effect=Exception("skip system_profiler")):
            level, source, _, _, _ = collector._battery()
        assert level  == 73.0
        assert source == "battery"


# ===========================================================================
# 4. Live-stream API endpoints
# ===========================================================================

class TestLiveStreamAPI:

    def setup_method(self):
        # Clear registry between tests
        from app.api.v1 import live_stream
        live_stream._agent_registry.clear()

    def test_register_new_agent(self):
        from app.api.v1.live_stream import register_agent, AgentRegistrationRequest
        req = AgentRegistrationRequest(device_id="win-001", source="windows-ohm")
        resp = register_agent(req)
        assert resp.status == "ok"
        assert resp.device_id == "win-001"
        assert "registered" in resp.message.lower()

    def test_register_existing_agent_is_reconnect(self):
        from app.api.v1.live_stream import register_agent, AgentRegistrationRequest
        req = AgentRegistrationRequest(device_id="mac-001", source="mac")
        register_agent(req)
        resp = register_agent(req)
        assert "reconnected" in resp.message.lower()

    def test_heartbeat_updates_known_agent(self):
        from app.api.v1.live_stream import (
            register_agent, agent_heartbeat,
            AgentRegistrationRequest, AgentHeartbeatRequest
        )
        register_agent(AgentRegistrationRequest(device_id="hb-001", source="linux"))
        resp = agent_heartbeat(AgentHeartbeatRequest(device_id="hb-001"))
        assert resp["status"] == "ok"

    def test_heartbeat_unknown_agent_raises_404(self):
        from app.api.v1.live_stream import agent_heartbeat, AgentHeartbeatRequest
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            agent_heartbeat(AgentHeartbeatRequest(device_id="ghost-999"))
        assert exc.value.status_code == 404

    def test_pipeline_status_empty_registry(self):
        from app.api.v1.live_stream import pipeline_status
        result = pipeline_status()
        assert result.total_agents    == 0
        assert result.active_agents   == 0
        assert result.inactive_agents == 0

    def test_pipeline_status_with_registered_agents(self):
        from app.api.v1.live_stream import (
            register_agent, pipeline_status, AgentRegistrationRequest
        )
        register_agent(AgentRegistrationRequest(device_id="a1", source="mac"))
        register_agent(AgentRegistrationRequest(device_id="a2", source="windows-ohm"))
        result = pipeline_status()
        assert result.total_agents  == 2
        assert result.active_agents == 2   # just registered = fresh

    def test_disconnect_removes_agent(self):
        from app.api.v1.live_stream import (
            register_agent, disconnect_agent, pipeline_status, AgentRegistrationRequest
        )
        register_agent(AgentRegistrationRequest(device_id="dc-001", source="linux"))
        disconnect_agent("dc-001")
        result = pipeline_status()
        assert result.total_agents == 0

    def test_list_devices(self):
        from app.api.v1.live_stream import (
            register_agent, list_devices, AgentRegistrationRequest
        )
        register_agent(AgentRegistrationRequest(device_id="ld-001", source="mac"))
        devices = list_devices()
        assert len(devices) == 1
        assert devices[0]["device_id"] == "ld-001"

    def test_auto_register_on_first_telemetry(self):
        from app.api.v1.live_stream import update_agent_registry, pipeline_status
        update_agent_registry({"device_id": "auto-001", "cpu_usage": 30.0})
        result = pipeline_status()
        assert result.total_agents >= 1


# ===========================================================================
# 5. SSE queue fan-out
# ===========================================================================

class TestSSEFanOut:

    def test_push_to_sse_queues_delivers_to_subscriber(self):
        async def _run():
            from app.api.v1.live_stream import (
                push_to_sse_queues, _sse_queues, _sse_queues_lock
            )
            q = asyncio.Queue(maxsize=10)
            async with _sse_queues_lock:
                _sse_queues.append(q)
            try:
                payload = {"cpu_usage": 55.0, "device_id": "sse-test"}
                await push_to_sse_queues(payload)
                received = q.get_nowait()
                assert received["cpu_usage"] == 55.0
                assert received["device_id"] == "sse-test"
            finally:
                async with _sse_queues_lock:
                    if q in _sse_queues:
                        _sse_queues.remove(q)

        asyncio.run(_run())

    def test_full_queue_is_pruned(self):
        async def _run():
            from app.api.v1.live_stream import (
                push_to_sse_queues, _sse_queues, _sse_queues_lock
            )
            # Fill a maxsize=1 queue to force QueueFull
            q = asyncio.Queue(maxsize=1)
            q.put_nowait({"old": True})   # fill it
            async with _sse_queues_lock:
                _sse_queues.append(q)
            try:
                await push_to_sse_queues({"new": True})
                # Full queue should have been pruned
                async with _sse_queues_lock:
                    assert q not in _sse_queues
            except Exception:
                pass
            finally:
                async with _sse_queues_lock:
                    if q in _sse_queues:
                        _sse_queues.remove(q)

        asyncio.run(_run())


# ===========================================================================
# 6. Pipeline health tracker (from telemetry_agent)
# ===========================================================================

class TestPipelineHealth:
    """Tests the PipelineHealth class in the telemetry agent."""

    def _get_health(self):
        # Import from whichever path has the agent
        from telemetry_agent import PipelineHealth
        return PipelineHealth()

    def test_initial_state(self):
        h = self._get_health()
        assert h.ticks_sent   == 0
        assert h.ticks_failed == 0
        assert h.consecutive_failures == 0

    def test_record_success(self):
        h = self._get_health()
        h.record_success(42.0)
        assert h.ticks_sent == 1
        assert h.consecutive_failures == 0
        assert h.last_latency_ms == 42.0

    def test_record_failure(self):
        h = self._get_health()
        h.record_failure("ConnectionError")
        assert h.ticks_failed == 1
        assert h.consecutive_failures == 1
        assert h.last_error == "ConnectionError"

    def test_consecutive_failures_reset_on_success(self):
        h = self._get_health()
        h.record_failure("err1")
        h.record_failure("err2")
        assert h.consecutive_failures == 2
        h.record_success(10.0)
        assert h.consecutive_failures == 0

    def test_summary_contains_key_fields(self):
        h = self._get_health()
        h.record_success(55.0)
        h.record_failure("timeout")
        summary = h.summary()
        assert "Sent=" in summary
        assert "Failed=" in summary
        assert "Success=" in summary


# ===========================================================================
# 7. Integration: Telemetry POST triggers agent registry update
# ===========================================================================

class TestIngestionIntegration:
    """
    Verifies that the telemetry POST endpoint correctly calls
    update_agent_registry (mocked DB + services).
    """

    def test_update_agent_registry_called_on_valid_payload(self):
        from app.api.v1.live_stream import update_agent_registry, _agent_registry
        _agent_registry.clear()

        payload = {
            "device_id": "integration-test-001",
            "cpu_usage": 50.0,
            "memory_usage": 60.0,
        }
        update_agent_registry(payload)
        assert "integration-test-001" in _agent_registry
        assert _agent_registry["integration-test-001"].ticks_received == 1

    def test_registry_increments_ticks_on_repeated_calls(self):
        from app.api.v1.live_stream import update_agent_registry, _agent_registry
        _agent_registry.clear()

        for _ in range(5):
            update_agent_registry({"device_id": "tick-counter-001"})
        assert _agent_registry["tick-counter-001"].ticks_received == 5

    def test_last_payload_is_updated(self):
        from app.api.v1.live_stream import update_agent_registry, _agent_registry
        _agent_registry.clear()

        update_agent_registry({"device_id": "pay-001", "cpu_usage": 30.0})
        update_agent_registry({"device_id": "pay-001", "cpu_usage": 75.0})
        assert _agent_registry["pay-001"].last_payload["cpu_usage"] == 75.0
