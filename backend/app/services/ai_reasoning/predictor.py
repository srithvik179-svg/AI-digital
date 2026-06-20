import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from typing import Dict, Any, List

class TrendPredictor:
    """
    Phase 26: XGBoost/Gradient Boosting Time-Series Predictor
    Uses Scikit-learn's GradientBoostingRegressor to perform recursive autoregressive
    forecasting 10 ticks into the future for CPU temperature and Battery Level.
    """
    def __init__(self):
        self.cpu_model = GradientBoostingRegressor(n_estimators=30, max_depth=3, random_state=42)
        self.battery_model = GradientBoostingRegressor(n_estimators=30, max_depth=3, random_state=42)
        self.window_size = 10
        self.forecast_horizon = 10
        self.is_trained = False
        self._bootstrap_and_train()

    def _bootstrap_and_train(self):
        """Generates synthetic time-series data and trains the autoregressive regressor models."""
        np.random.seed(101)
        n_sequences = 500
        
        # CPU temp sequences: normal ranges (45 to 90C)
        cpu_X = []
        cpu_y = []
        
        # Battery sequences: normal discharge (100 down to 0)
        bat_X = []
        bat_y = []
        
        for _ in range(n_sequences):
            # CPU Temperature random walk / workload spike simulation
            base_temp = np.random.uniform(45.0, 75.0)
            noise = np.random.normal(0, 1.0, self.window_size + 1)
            # Add trend
            trend = np.random.choice([-1.5, 0.0, 1.5, 3.0])
            cpu_seq = [base_temp + (i * trend) + noise[i] for i in range(self.window_size + 1)]
            cpu_X.append(cpu_seq[:self.window_size])
            cpu_y.append(cpu_seq[self.window_size])
            
            # Battery discharging (linear decay + minor noise)
            start_bat = np.random.uniform(20.0, 100.0)
            decay = np.random.uniform(-0.8, -0.1) # Discharging rate
            noise_bat = np.random.normal(0, 0.05, self.window_size + 1)
            bat_seq = [max(0.0, min(100.0, start_bat + (i * decay) + noise_bat[i])) for i in range(self.window_size + 1)]
            bat_X.append(bat_seq[:self.window_size])
            bat_y.append(bat_seq[self.window_size])

        self.cpu_model.fit(np.array(cpu_X), np.array(cpu_y))
        self.battery_model.fit(np.array(bat_X), np.array(bat_y))
        self.is_trained = True

    def predict_trajectories(self, cpu_history: List[float], battery_history: List[float]) -> Dict[str, Any]:
        """
        Predicts the next 10 ticks recursively.
        If inputs are shorter than 10 ticks, pad them with the earliest/latest values.
        """
        if not self.is_trained:
            self._bootstrap_and_train()

        # Ensure historical inputs have length 10
        def pad_history(hist: List[float], default_val: float) -> List[float]:
            if not hist:
                return [default_val] * self.window_size
            if len(hist) >= self.window_size:
                return hist[-self.window_size:]
            # Pad beginning with the first element
            return [hist[0]] * (self.window_size - len(hist)) + hist

        cpu_seq = pad_history(cpu_history, 55.0)
        bat_seq = pad_history(battery_history, 80.0)

        cpu_forecast = []
        bat_forecast = []

        # Autoregressive recursive forecasting loop
        current_cpu = list(cpu_seq)
        current_bat = list(bat_seq)

        for _ in range(self.forecast_horizon):
            # Predict CPU Temp
            cpu_in = np.array([current_cpu[-self.window_size:]])
            pred_cpu = float(self.cpu_model.predict(cpu_in)[0])
            # Cap realistic temperature boundaries
            pred_cpu = max(35.0, min(105.0, pred_cpu))
            cpu_forecast.append(round(pred_cpu, 1))
            current_cpu.append(pred_cpu)
            
            # Predict Battery
            bat_in = np.array([current_bat[-self.window_size:]])
            pred_bat = float(self.battery_model.predict(bat_in)[0])
            pred_bat = max(0.0, min(100.0, pred_bat))
            bat_forecast.append(round(pred_bat, 1))
            current_bat.append(pred_bat)

        return {
            "cpu_temperature_forecast": cpu_forecast,
            "battery_level_forecast": bat_forecast
        }
