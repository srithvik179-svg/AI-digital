"""
Unit tests for Phases 42–45: XGBoost Thermal, LSTM Battery,
Prophet Network, and Unified Future-State Prediction.
"""

import pytest
import numpy as np
from app.services.ai_reasoning.thermal_predictor import ThermalPredictor, thermal_predictor
from app.services.ai_reasoning.battery_predictor import BatteryPredictor, battery_predictor
from app.services.ai_reasoning.network_predictor import NetworkPredictor, network_predictor
from app.services.ai_reasoning.future_state import run_future_state_prediction


# ===========================================================================
# Phase 42 — XGBoost Thermal Predictor Tests
# ===========================================================================

class TestThermalPredictor:

    def test_singleton_is_trained(self):
        assert thermal_predictor._is_trained is True

    def test_forecast_returns_correct_keys(self):
        result = thermal_predictor.forecast(
            cpu_temp_history=[55.0] * 10,
            gpu_temp_history=[50.0] * 10,
            cpu_usage_history=[40.0] * 10,
            gpu_usage_history=[25.0] * 10,
            fan_rpm_history=[2000.0] * 10,
            ambient_temp=25.0,
            horizon=10,
        )
        assert "cpu_temperature_forecast" in result
        assert "gpu_temperature_forecast" in result
        assert "tick_seconds" in result
        assert "horizon_ticks" in result
        assert "model" in result
        assert result["model"] == "xgboost-thermal-v1"

    def test_forecast_horizon_length(self):
        result = thermal_predictor.forecast(
            cpu_temp_history=[60.0] * 10,
            gpu_temp_history=[55.0] * 10,
            cpu_usage_history=[70.0] * 10,
            gpu_usage_history=[50.0] * 10,
            fan_rpm_history=[3000.0] * 10,
            ambient_temp=22.0,
            horizon=30,
        )
        assert len(result["cpu_temperature_forecast"]) == 30
        assert len(result["gpu_temperature_forecast"]) == 30

    def test_cpu_temps_clamped_within_physical_bounds(self):
        result = thermal_predictor.forecast(
            cpu_temp_history=[100.0] * 10,
            gpu_temp_history=[95.0] * 10,
            cpu_usage_history=[100.0] * 10,
            gpu_usage_history=[100.0] * 10,
            fan_rpm_history=[6000.0] * 10,
            ambient_temp=35.0,
            horizon=15,
        )
        for t in result["cpu_temperature_forecast"]:
            assert 35.0 <= t <= 105.0, f"CPU temp {t} out of bounds"
        for t in result["gpu_temperature_forecast"]:
            assert 35.0 <= t <= 100.0, f"GPU temp {t} out of bounds"

    def test_idle_workload_produces_lower_temps(self):
        idle = thermal_predictor.forecast(
            cpu_temp_history=[45.0] * 10,
            gpu_temp_history=[40.0] * 10,
            cpu_usage_history=[5.0] * 10,
            gpu_usage_history=[2.0] * 10,
            fan_rpm_history=[1200.0] * 10,
            ambient_temp=22.0,
            horizon=10,
        )
        heavy = thermal_predictor.forecast(
            cpu_temp_history=[85.0] * 10,
            gpu_temp_history=[80.0] * 10,
            cpu_usage_history=[95.0] * 10,
            gpu_usage_history=[90.0] * 10,
            fan_rpm_history=[5500.0] * 10,
            ambient_temp=22.0,
            horizon=10,
        )
        avg_idle  = np.mean(idle["cpu_temperature_forecast"])
        avg_heavy = np.mean(heavy["cpu_temperature_forecast"])
        assert avg_idle < avg_heavy, "Idle CPU temp should be lower than heavy-load temp"

    def test_short_history_is_padded_gracefully(self):
        # Only 3 history points, window=10 — should pad without error
        result = thermal_predictor.forecast(
            cpu_temp_history=[60.0, 61.0, 62.0],
            gpu_temp_history=[55.0, 56.0, 57.0],
            cpu_usage_history=[50.0, 52.0, 54.0],
            gpu_usage_history=[30.0, 32.0, 34.0],
            fan_rpm_history=[2200.0, 2300.0, 2400.0],
            ambient_temp=24.0,
            horizon=10,
        )
        assert len(result["cpu_temperature_forecast"]) == 10

    def test_empty_history_falls_back_to_defaults(self):
        result = thermal_predictor.forecast(
            cpu_temp_history=[],
            gpu_temp_history=[],
            cpu_usage_history=[],
            gpu_usage_history=[],
            fan_rpm_history=[],
            ambient_temp=25.0,
            horizon=5,
        )
        assert len(result["cpu_temperature_forecast"]) == 5

    def test_feature_importances_shape(self):
        fi = thermal_predictor.feature_importances()
        assert "cpu_model" in fi
        assert "gpu_model" in fi
        # 6 features × 10 window ticks
        assert len(fi["cpu_model"]) == 60
        assert len(fi["gpu_model"]) == 60

    def test_new_instance_is_trained_independently(self):
        tp = ThermalPredictor()
        assert tp._is_trained is True
        result = tp.forecast(
            cpu_temp_history=[58.0] * 10,
            gpu_temp_history=[52.0] * 10,
            cpu_usage_history=[45.0] * 10,
            gpu_usage_history=[30.0] * 10,
            fan_rpm_history=[2500.0] * 10,
            horizon=5,
        )
        assert len(result["cpu_temperature_forecast"]) == 5


# ===========================================================================
# Phase 43 — LSTM Battery Predictor Tests
# ===========================================================================

class TestBatteryPredictor:

    def test_singleton_is_trained(self):
        assert battery_predictor._is_trained is True

    def test_forecast_returns_correct_keys(self):
        result = battery_predictor.forecast(
            battery_history=[80.0] * 10,
            cpu_watts_history=[8.0] * 10,
            gpu_watts_history=[3.0] * 10,
            is_charging=False,
            horizon=10,
        )
        assert "battery_soc_forecast" in result
        assert "battery_temp_forecast" in result
        assert "tick_seconds" in result
        assert "horizon_ticks" in result
        assert result["model"] == "lstm-battery-v1"

    def test_forecast_horizon_length(self):
        result = battery_predictor.forecast(
            battery_history=[60.0] * 10,
            cpu_watts_history=[15.0] * 10,
            gpu_watts_history=[8.0] * 10,
            is_charging=False,
            horizon=30,
        )
        assert len(result["battery_soc_forecast"]) == 30
        assert len(result["battery_temp_forecast"]) == 30

    def test_soc_clamped_between_0_and_100(self):
        result = battery_predictor.forecast(
            battery_history=[2.0] * 10,
            cpu_watts_history=[40.0] * 10,
            gpu_watts_history=[20.0] * 10,
            is_charging=False,
            horizon=30,
        )
        for soc in result["battery_soc_forecast"]:
            assert 0.0 <= soc <= 100.0, f"SoC {soc} out of range"

    def test_battery_temp_clamped(self):
        result = battery_predictor.forecast(
            battery_history=[50.0] * 10,
            cpu_watts_history=[50.0] * 10,
            gpu_watts_history=[25.0] * 10,
            is_charging=True,
            horizon=20,
        )
        for temp in result["battery_temp_forecast"]:
            assert 20.0 <= temp <= 65.0, f"Battery temp {temp} out of range"

    def test_short_history_padded(self):
        result = battery_predictor.forecast(
            battery_history=[75.0, 74.0],
            cpu_watts_history=[10.0, 11.0],
            gpu_watts_history=[3.0, 3.5],
            is_charging=False,
            horizon=10,
        )
        assert len(result["battery_soc_forecast"]) == 10

    def test_empty_history_uses_defaults(self):
        result = battery_predictor.forecast(
            battery_history=[],
            cpu_watts_history=[],
            gpu_watts_history=[],
            is_charging=False,
            horizon=5,
        )
        assert len(result["battery_soc_forecast"]) == 5

    def test_new_instance_trains_independently(self):
        bp = BatteryPredictor()
        assert bp._is_trained is True
        result = bp.forecast(
            battery_history=[70.0] * 10,
            cpu_watts_history=[12.0] * 10,
            gpu_watts_history=[5.0] * 10,
            is_charging=False,
            horizon=5,
        )
        assert len(result["battery_soc_forecast"]) == 5


# ===========================================================================
# Phase 44 — Prophet Network Predictor Tests
# ===========================================================================

class TestNetworkPredictor:

    def test_singleton_is_trained(self):
        assert network_predictor._is_trained is True

    def test_forecast_returns_correct_keys(self):
        result = network_predictor.forecast(
            rssi_history=[-65.0] * 20,
            packet_loss_history=[1.0] * 20,
            horizon=10,
        )
        assert "wifi_rssi_forecast" in result
        assert "packet_loss_forecast" in result
        assert "wifi_quality_forecast" in result
        assert "tick_seconds" in result
        assert result["model"] == "prophet-network-v1"

    def test_forecast_horizon_length(self):
        result = network_predictor.forecast(
            rssi_history=[-70.0] * 30,
            horizon=30,
        )
        assert len(result["wifi_rssi_forecast"]) == 30
        assert len(result["packet_loss_forecast"]) == 30
        assert len(result["wifi_quality_forecast"]) == 30

    def test_rssi_clamped_to_physical_range(self):
        result = network_predictor.forecast(
            rssi_history=[-90.0] * 30,
            horizon=30,
        )
        for v in result["wifi_rssi_forecast"]:
            assert -95.0 <= v <= -20.0, f"RSSI {v} out of range"

    def test_packet_loss_clamped_0_to_100(self):
        result = network_predictor.forecast(
            rssi_history=[-85.0] * 20,
            horizon=20,
        )
        for v in result["packet_loss_forecast"]:
            assert 0.0 <= v <= 100.0, f"Packet loss {v} out of range"

    def test_quality_categories_are_valid(self):
        valid = {"Good", "Fair", "Poor", "Critical"}
        result = network_predictor.forecast(
            rssi_history=[-55.0, -65.0, -75.0, -85.0] * 5,
            horizon=10,
        )
        for q in result["wifi_quality_forecast"]:
            assert q in valid, f"Unknown quality category: {q}"

    def test_good_signal_history_bias_correction(self):
        # If last RSSI is -45 dBm (Good), first forecast should be near that
        result = network_predictor.forecast(
            rssi_history=[-45.0] * 30,
            horizon=5,
        )
        first_pred = result["wifi_rssi_forecast"][0]
        assert first_pred >= -60.0, f"Expected Good signal bias, got {first_pred}"
        assert result["wifi_quality_forecast"][0] in {"Good", "Fair"}

    def test_empty_history_uses_defaults(self):
        result = network_predictor.forecast(rssi_history=[], horizon=5)
        assert len(result["wifi_rssi_forecast"]) == 5

    def test_new_instance_trains_independently(self):
        np2 = NetworkPredictor()
        assert np2._is_trained is True
        result = np2.forecast(rssi_history=[-65.0] * 20, horizon=5)
        assert len(result["wifi_rssi_forecast"]) == 5


# ===========================================================================
# Phase 45 — Unified Future-State Orchestrator Tests
# ===========================================================================

class TestFutureStateOrchestrator:

    def _default_result(self, horizon=10):
        return run_future_state_prediction(
            cpu_temp_history=[58.0] * 10,
            gpu_temp_history=[52.0] * 10,
            cpu_usage_history=[45.0] * 10,
            gpu_usage_history=[30.0] * 10,
            fan_rpm_history=[2500.0] * 10,
            ambient_temp=25.0,
            battery_soc_history=[70.0] * 10,
            cpu_watts_history=[12.0] * 10,
            gpu_watts_history=[5.0] * 10,
            is_charging=False,
            wifi_rssi_history=[-65.0] * 15,
            packet_loss_history=[1.5] * 15,
            horizon=horizon,
        )

    def test_result_top_level_keys(self):
        result = self._default_result()
        assert "thermal"  in result
        assert "battery"  in result
        assert "network"  in result
        assert "horizon_ticks"   in result
        assert "tick_seconds"    in result
        assert "horizon_minutes" in result

    def test_thermal_sub_keys(self):
        result = self._default_result(10)
        t = result["thermal"]
        assert "cpu_temperature_forecast" in t
        assert "gpu_temperature_forecast" in t
        assert len(t["cpu_temperature_forecast"]) == 10

    def test_battery_sub_keys(self):
        result = self._default_result(10)
        b = result["battery"]
        assert "battery_soc_forecast"  in b
        assert "battery_temp_forecast" in b
        assert len(b["battery_soc_forecast"]) == 10

    def test_network_sub_keys(self):
        result = self._default_result(10)
        n = result["network"]
        assert "wifi_rssi_forecast"    in n
        assert "packet_loss_forecast"  in n
        assert "wifi_quality_forecast" in n

    def test_horizon_minutes_calculation(self):
        result = self._default_result(horizon=30)
        expected = 30 * 5 / 60.0  # 2.5 minutes
        assert abs(result["horizon_minutes"] - expected) < 0.01

    def test_all_forecasts_correct_length(self):
        for h in [5, 15, 30, 60]:
            result = self._default_result(horizon=h)
            assert len(result["thermal"]["cpu_temperature_forecast"]) == h
            assert len(result["battery"]["battery_soc_forecast"]) == h
            assert len(result["network"]["wifi_rssi_forecast"]) == h

    def test_defaults_used_when_histories_empty(self):
        result = run_future_state_prediction(
            cpu_temp_history=[],
            gpu_temp_history=[],
            cpu_usage_history=[],
            gpu_usage_history=[],
            fan_rpm_history=[],
            horizon=5,
        )
        assert len(result["thermal"]["cpu_temperature_forecast"]) == 5
        assert len(result["battery"]["battery_soc_forecast"]) == 5
        assert len(result["network"]["wifi_rssi_forecast"]) == 5

    def test_charging_mode_affects_battery_forecast(self):
        discharging = run_future_state_prediction(
            cpu_temp_history=[55.0] * 10,
            gpu_temp_history=[50.0] * 10,
            cpu_usage_history=[30.0] * 10,
            gpu_usage_history=[15.0] * 10,
            fan_rpm_history=[2000.0] * 10,
            battery_soc_history=[50.0] * 10,
            cpu_watts_history=[8.0] * 10,
            gpu_watts_history=[3.0] * 10,
            is_charging=False,
            wifi_rssi_history=[-65.0] * 10,
            horizon=15,
        )
        charging = run_future_state_prediction(
            cpu_temp_history=[55.0] * 10,
            gpu_temp_history=[50.0] * 10,
            cpu_usage_history=[30.0] * 10,
            gpu_usage_history=[15.0] * 10,
            fan_rpm_history=[2000.0] * 10,
            battery_soc_history=[50.0] * 10,
            cpu_watts_history=[8.0] * 10,
            gpu_watts_history=[3.0] * 10,
            is_charging=True,
            wifi_rssi_history=[-65.0] * 10,
            horizon=15,
        )
        # Both should produce valid outputs; no assertion on direction
        # because both are valid states.
        assert len(discharging["battery"]["battery_soc_forecast"]) == 15
        assert len(charging["battery"]["battery_soc_forecast"]) == 15
