"""
Unit tests for Phase 13 Statistical Correlation Analysis.
Validates Spearman rank correlation coefficient, get_ranks handling ties,
and the generation of the N x N correlation matrix.
"""
import pytest
from unittest.mock import MagicMock
from datetime import datetime

from app.services.relationship_mapper import (
    get_ranks,
    spearman_correlation,
    generate_correlation_matrix
)
from app.models.telemetry import (
    TelemetrySnapshot,
    CPUMetrics,
    GPUMetrics,
    MemoryMetrics,
    BatteryMetrics,
    DiskMetrics,
    ThermalMetrics,
    PowerMetrics
)

class TestSpearmanCorrelationMath:
    def test_get_ranks_no_ties(self):
        """Should return correct 1-based ranks for values without ties."""
        data = [10.0, 50.0, 30.0, 20.0]
        # Sorted: 10.0 (rank 1), 20.0 (rank 2), 30.0 (rank 3), 50.0 (rank 4)
        expected = [1.0, 4.0, 3.0, 2.0]
        assert get_ranks(data) == expected

    def test_get_ranks_with_ties(self):
        """Should return average ranks (fractional ranks) for tied values."""
        data = [10.0, 20.0, 20.0, 40.0]
        # Sorted: 
        # 10.0 is rank 1
        # 20.0 and 20.0 occupy positions 2 and 3. Average rank is (2 + 3) / 2 = 2.5
        # 40.0 is rank 4
        expected = [1.0, 2.5, 2.5, 4.0]
        assert get_ranks(data) == expected

    def test_get_ranks_all_tied(self):
        """Should return the same average rank for all elements if all are tied."""
        data = [5.0, 5.0, 5.0]
        # Average of 1, 2, 3 is (1 + 2 + 3) / 3 = 2.0
        expected = [2.0, 2.0, 2.0]
        assert get_ranks(data) == expected

    def test_spearman_perfect_positive(self):
        """Perfect monotonic relationship should yield Spearman r = 1.0."""
        x = [1, 2, 3, 4, 5]
        # Monotonic but not strictly linear
        y = [10, 20, 25, 45, 90]
        assert abs(spearman_correlation(x, y) - 1.0) < 1e-7

    def test_spearman_perfect_negative(self):
        """Perfect inverse monotonic relationship should yield Spearman r = -1.0."""
        x = [1, 2, 3, 4, 5]
        y = [100, 50, 40, 20, 5]
        assert abs(spearman_correlation(x, y) - (-1.0)) < 1e-7

    def test_spearman_zero_correlation(self):
        """No relationship or constant input yields 0 or near 0."""
        x = [1, 2, 3, 4, 5]
        y = [5, 5, 5, 5, 5]  # no variance, correlation should be 0.0
        assert spearman_correlation(x, y) == 0.0


class TestCorrelationMatrixService:
    def test_insufficient_snapshots_returns_identity(self):
        """Fewer than 5 snapshots should return an identity matrix (1s on diagonal, 0s elsewhere)."""
        db = MagicMock()
        # 3 snapshots
        snapshots = [
            TelemetrySnapshot(id="snap-1", device_id="dev-123"),
            TelemetrySnapshot(id="snap-2", device_id="dev-123"),
            TelemetrySnapshot(id="snap-3", device_id="dev-123")
        ]
        db.query.return_value.options.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = snapshots

        result = generate_correlation_matrix("dev-123", db)
        
        assert result["device_id"] == "dev-123"
        assert result["total_records_analyzed"] == 3
        assert len(result["metrics"]) == 8
        
        # Pearson and Spearman should be 8x8 identity matrices
        for matrix_key in ["pearson", "spearman"]:
            matrix = result[matrix_key]
            assert len(matrix) == 8
            for i in range(8):
                assert len(matrix[i]) == 8
                for j in range(8):
                    if i == j:
                        assert matrix[i][j] == 1.0
                    else:
                        assert matrix[i][j] == 0.0

    def test_sufficient_snapshots_computes_correlation(self):
        """With >= 5 snapshots, correlations are calculated correctly for the 8x8 matrix."""
        db = MagicMock()
        snapshots = []
        for i in range(10):
            s = TelemetrySnapshot(id=f"snap-{i}", device_id="dev-123", timestamp=datetime.utcnow())
            
            # Linearly increasing CPU, GPU, temp, fan; battery decreasing
            s.cpu = CPUMetrics(cpu_usage=10.0 + i * 5.0)  # 10 to 55
            s.gpu = GPUMetrics(gpu_usage=5.0 + i * 2.0)   # 5 to 23
            s.memory = MemoryMetrics(memory_usage=40.0 + (i % 2) * 5.0)  # oscillating
            s.disk = DiskMetrics(disk_usage=15.0)         # constant
            s.thermal = ThermalMetrics(cpu_temperature=50.0 + i * 2.0, fan_speed_rpm=1500 + i * 100)
            s.battery = BatteryMetrics(battery_level=80.0 - i * 2.0, battery_temperature=30.0 + i * 0.5)
            s.power = PowerMetrics(power_source="battery")
            snapshots.append(s)

        db.query.return_value.options.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = snapshots

        result = generate_correlation_matrix("dev-123", db)
        
        assert result["device_id"] == "dev-123"
        assert result["total_records_analyzed"] == 10
        assert len(result["metrics"]) == 8
        
        pearson = result["pearson"]
        spearman = result["spearman"]
        
        assert len(pearson) == 8
        assert len(spearman) == 8
        
        # CPU Usage (index 0) and CPU Temp (index 3) should have perfect linear correlation (+1.0)
        # Because cpu_usage = 10 + 5i and cpu_temperature = 50 + 2i (perfect positive linear)
        assert pearson[0][3] == 1.0
        assert spearman[0][3] == 1.0
        
        # CPU Usage (index 0) and Battery Level (index 5) should have perfect negative correlation (-1.0)
        # cpu_usage = 10 + 5i, battery_level = 80 - 2i (perfect negative linear)
        assert pearson[0][5] == -1.0
        assert spearman[0][5] == -1.0
        
        # CPU Usage (index 0) and Disk Usage (index 2) (constant 15.0) should have 0 correlation due to no variance in disk
        assert pearson[0][2] == 0.0
        assert spearman[0][2] == 0.0
