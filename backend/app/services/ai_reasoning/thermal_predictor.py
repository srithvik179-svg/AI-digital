"""
Phase 42 — XGBoost Thermal Regressor.

Predicts CPU and GPU temperature trajectories up to 30 ticks into the future
using a multi-output XGBoost regressor trained on synthetic thermal sequences
that capture workload-driven heat generation and fan-cooling dynamics.

Features per window tick:
  cpu_temp, gpu_temp, cpu_usage, gpu_usage, fan_rpm, ambient_temp
"""

from __future__ import annotations

import numpy as np
from typing import List, Dict, Any, Optional
from xgboost import XGBRegressor

# ---------------------------------------------------------------------------
# Feature engineering helpers
# ---------------------------------------------------------------------------

_FEATURE_NAMES = ["cpu_temp", "gpu_temp", "cpu_usage", "gpu_usage", "fan_rpm", "ambient_temp"]
_WINDOW = 10         # look-back ticks used per prediction step
_HORIZON = 30        # forecast ticks produced
_TICK_SECONDS = 5    # seconds per tick


def _build_feature_vector(
    cpu_temps: List[float],
    gpu_temps: List[float],
    cpu_usages: List[float],
    gpu_usages: List[float],
    fan_rpms: List[float],
    ambient_temps: List[float],
) -> np.ndarray:
    """
    Flattens the last _WINDOW ticks of each feature series into a 1-D array.
    Missing / short histories are forward-padded with the first observed value.
    """
    def _pad(seq: List[float], default: float) -> List[float]:
        if not seq:
            return [default] * _WINDOW
        if len(seq) >= _WINDOW:
            return list(seq[-_WINDOW:])
        return [seq[0]] * (_WINDOW - len(seq)) + list(seq)

    c_t = _pad(cpu_temps,   55.0)
    g_t = _pad(gpu_temps,   50.0)
    c_u = _pad(cpu_usages,  30.0)
    g_u = _pad(gpu_usages,  20.0)
    f_r = _pad(fan_rpms,  1800.0)
    a_t = _pad(ambient_temps, 25.0)

    return np.array(c_t + g_t + c_u + g_u + f_r + a_t, dtype=np.float32)


# ---------------------------------------------------------------------------
# Synthetic dataset generator
# ---------------------------------------------------------------------------

def _generate_training_data(n_sequences: int = 800, seed: int = 42):
    rng = np.random.default_rng(seed)
    X_cpu, y_cpu = [], []
    X_gpu, y_gpu = [], []

    for _ in range(n_sequences):
        ambient = rng.uniform(20.0, 35.0)

        # Workload profile: idle / normal / heavy / burst
        workload_type = rng.choice(["idle", "normal", "heavy", "burst"])
        if workload_type == "idle":
            cpu_base, gpu_base = rng.uniform(5, 20), rng.uniform(0, 10)
        elif workload_type == "normal":
            cpu_base, gpu_base = rng.uniform(25, 60), rng.uniform(10, 40)
        elif workload_type == "heavy":
            cpu_base, gpu_base = rng.uniform(60, 85), rng.uniform(40, 75)
        else:  # burst
            cpu_base, gpu_base = rng.uniform(80, 100), rng.uniform(70, 100)

        # Fan ramps up with thermal load
        fan_base = 1200 + (cpu_base + gpu_base) * 20
        fan_base = float(np.clip(fan_base, 1200, 6000))

        # Simulate thermal sequence of length (_WINDOW + 1)
        total_len = _WINDOW + 1
        cpu_u = np.clip(cpu_base + rng.normal(0, 5, total_len), 0, 100)
        gpu_u = np.clip(gpu_base + rng.normal(0, 5, total_len), 0, 100)
        fan_r = np.clip(fan_base + rng.normal(0, 150, total_len), 1000, 6500)
        a_arr = np.full(total_len, ambient)

        # Steady-state approximation per tick
        def _steady(cu, gu, fan, amb):
            q = cu * 0.25 + gu * 0.15
            coeff = 0.03 + 0.00005 * fan
            return amb + q / coeff

        cpu_t = np.array([_steady(cpu_u[i], gpu_u[i], fan_r[i], a_arr[i]) for i in range(total_len)])
        gpu_t = cpu_t * rng.uniform(0.85, 0.95) + rng.normal(0, 1.5, total_len)

        cpu_t = np.clip(cpu_t, ambient, 105.0)
        gpu_t = np.clip(gpu_t, ambient, 100.0)

        feat = _build_feature_vector(
            list(cpu_t[:_WINDOW]),
            list(gpu_t[:_WINDOW]),
            list(cpu_u[:_WINDOW]),
            list(gpu_u[:_WINDOW]),
            list(fan_r[:_WINDOW]),
            list(a_arr[:_WINDOW]),
        )
        X_cpu.append(feat)
        y_cpu.append(float(cpu_t[_WINDOW]))

        X_gpu.append(feat)
        y_gpu.append(float(gpu_t[_WINDOW]))

    return (
        np.array(X_cpu, dtype=np.float32), np.array(y_cpu, dtype=np.float32),
        np.array(X_gpu, dtype=np.float32), np.array(y_gpu, dtype=np.float32),
    )


# ---------------------------------------------------------------------------
# ThermalPredictor class
# ---------------------------------------------------------------------------

class ThermalPredictor:
    """
    XGBoost thermal regressor that produces 30-tick temperature trajectories
    for both CPU and GPU.  Training uses fully synthetic physics-based data
    so no DB access is required at import time.
    """

    def __init__(self):
        self._cpu_model = XGBRegressor(
            n_estimators=80,
            max_depth=4,
            learning_rate=0.12,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            verbosity=0,
        )
        self._gpu_model = XGBRegressor(
            n_estimators=80,
            max_depth=4,
            learning_rate=0.12,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            verbosity=0,
        )
        self._is_trained = False
        self._fit()

    # ------------------------------------------------------------------
    def _fit(self) -> None:
        X_c, y_c, X_g, y_g = _generate_training_data()
        self._cpu_model.fit(X_c, y_c)
        self._gpu_model.fit(X_g, y_g)
        self._is_trained = True

    # ------------------------------------------------------------------
    def forecast(
        self,
        cpu_temp_history:  List[float],
        gpu_temp_history:  List[float],
        cpu_usage_history: List[float],
        gpu_usage_history: List[float],
        fan_rpm_history:   List[float],
        ambient_temp:      float = 25.0,
        horizon:           int   = _HORIZON,
    ) -> Dict[str, Any]:
        """
        Autoregressively predict the next `horizon` temperature ticks.

        Returns
        -------
        {
          "cpu_temperature_forecast": [float, ...],   # °C
          "gpu_temperature_forecast": [float, ...],   # °C
          "tick_seconds": int,
          "horizon_ticks": int,
          "model": "xgboost-thermal-v1"
        }
        """
        if not self._is_trained:
            self._fit()

        # Running windows (mutable copies)
        c_t = list(cpu_temp_history)  or [55.0] * _WINDOW
        g_t = list(gpu_temp_history)  or [50.0] * _WINDOW
        c_u = list(cpu_usage_history) or [30.0] * _WINDOW
        g_u = list(gpu_usage_history) or [20.0] * _WINDOW
        f_r = list(fan_rpm_history)   or [1800.0] * _WINDOW
        a_t = [ambient_temp] * max(_WINDOW, len(c_t))

        cpu_forecast: List[float] = []
        gpu_forecast: List[float] = []

        for step in range(horizon):
            feat = _build_feature_vector(c_t, g_t, c_u, g_u, f_r, a_t)
            feat_2d = feat.reshape(1, -1)

            pred_cpu = float(self._cpu_model.predict(feat_2d)[0])
            pred_gpu = float(self._gpu_model.predict(feat_2d)[0])

            # Physical clamps
            pred_cpu = round(float(np.clip(pred_cpu, ambient_temp, 105.0)), 1)
            pred_gpu = round(float(np.clip(pred_gpu, ambient_temp, 100.0)), 1)

            cpu_forecast.append(pred_cpu)
            gpu_forecast.append(pred_gpu)

            # Slide the window forward (keep usages / fan roughly constant)
            c_t.append(pred_cpu)
            g_t.append(pred_gpu)
            c_u.append(c_u[-1] if c_u else 30.0)
            g_u.append(g_u[-1] if g_u else 20.0)
            # Fan ramps if temps rise
            new_fan = 1200 + (pred_cpu + pred_gpu) * 15
            f_r.append(float(np.clip(new_fan, 1000, 6500)))
            a_t.append(ambient_temp)

        return {
            "cpu_temperature_forecast": cpu_forecast,
            "gpu_temperature_forecast": gpu_forecast,
            "tick_seconds": _TICK_SECONDS,
            "horizon_ticks": horizon,
            "model": "xgboost-thermal-v1",
        }

    # ------------------------------------------------------------------
    def feature_importances(self) -> Dict[str, List[float]]:
        """Returns per-feature importance vectors for explainability."""
        cpu_imp = self._cpu_model.feature_importances_.tolist()
        gpu_imp = self._gpu_model.feature_importances_.tolist()
        return {"cpu_model": cpu_imp, "gpu_model": gpu_imp}


# Module-level singleton — instantiated once on import
thermal_predictor = ThermalPredictor()
