"""
Unit tests for the Phase 12 Telemetry Relationship Mapper.
Validates Pearson correlation math, database updates, and graph representation.
"""
import pytest
from unittest.mock import MagicMock
from datetime import datetime

from app.services.relationship_mapper import pearson_correlation, map_and_store_relationships
from app.models.relationship import TelemetryRelationship
from app.models.telemetry import TelemetrySnapshot, CPUMetrics, BatteryMetrics, ThermalMetrics, PowerMetrics

# ─── Tests ────────────────────────────────────────────────────────────

class TestPearsonCorrelation:
    def test_perfect_positive_correlation(self):
        """r = 1.0 for perfectly linear scaling."""
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [2.0, 4.0, 6.0, 8.0, 10.0]
        assert abs(pearson_correlation(x, y) - 1.0) < 1e-7

    def test_perfect_negative_correlation(self):
        """r = -1.0 for perfectly inverse scaling."""
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [5.0, 4.0, 3.0, 2.0, 1.0]
        assert abs(pearson_correlation(x, y) - (-1.0)) < 1e-7

    def test_flat_line_returns_zero(self):
        """r = 0.0 if one of the lines is completely flat (no variance)."""
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [3.0, 3.0, 3.0, 3.0, 3.0]
        assert pearson_correlation(x, y) == 0.0

    def test_insufficient_length_returns_zero(self):
        x = [1.0]
        y = [2.0]
        assert pearson_correlation(x, y) == 0.0


class TestRelationshipMapperService:
    def test_stores_and_returns_relationships(self):
        """Service queries database, computes relationships, updates/adds records, and returns graph schema."""
        db = MagicMock()
        
        # Build 6 mock snapshots to satisfy minimum requirement (>=5 snapshots)
        snapshots = []
        for i in range(6):
            s = TelemetrySnapshot(
                id=f"snap-{i}",
                device_id="test-device",
                timestamp=datetime.utcnow()
            )
            s.cpu = CPUMetrics(cpu_usage=10.0 + i*5.0, active_process_count=90)
            s.thermal = ThermalMetrics(cpu_temperature=45.0 + i*3.0, fan_speed_rpm=1200 + i*200)
            s.battery = BatteryMetrics(battery_level=90.0 - i, battery_health=95.0)
            s.power = PowerMetrics(power_source="battery")
            snapshots.append(s)
            
        db.query.return_value.options.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = snapshots
        
        # Mock database get/filter check for upsert queries
        db.query.return_value.filter.return_value.first.return_value = None
        
        graph = map_and_store_relationships("test-device", db)
        
        # Verify database addition called 3 times (for 3 relationships)
        assert db.add.call_count == 3
        # Verify db transaction committed
        assert db.commit.called
        
        # Verify graph output structure
        assert graph["device_id"] == "test-device"
        assert len(graph["nodes"]) == 5
        assert len(graph["edges"]) == 3
        
        # Inspect specific edge
        cpu_temp_edge = next(e for e in graph["edges"] if e["source"] == "cpu_usage" and e["target"] == "cpu_temperature")
        assert cpu_temp_edge["relationship_type"] == "thermal_influence"
        # Since CPU and Temp are perfectly linear in mock data: 10->35 and 45->60, r should be close to 1.0
        assert cpu_temp_edge["correlation_strength"] > 0.9
