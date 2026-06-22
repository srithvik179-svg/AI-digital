"""
Unit tests for the /api/v1/metrics endpoints.
Uses a minimal FastAPI test app with only the metrics router to avoid importing
the full application stack (which requires Docker services like ChromaDB/Neo4j).
Tests JSON response structure and Prometheus text-format output.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base, get_db
from app.api.v1.metrics import router as metrics_router

# ── Isolated test app ──────────────────────────────────────────────────
test_app = FastAPI()
test_app.include_router(metrics_router, prefix="/api/v1/metrics")

SQLALCHEMY_DATABASE_URL = "sqlite:///./test_metrics_isolated.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


test_app.dependency_overrides[get_db] = override_get_db
client = TestClient(test_app)


# ═══════════════════════════════════════════════════════════
# Tests: JSON metrics endpoint
# ═══════════════════════════════════════════════════════════
class TestMetricsJSON:
    def test_metrics_endpoint_returns_200(self):
        resp = client.get("/api/v1/metrics/")
        assert resp.status_code == 200

    def test_metrics_json_structure(self):
        resp = client.get("/api/v1/metrics/")
        data = resp.json()
        assert "process" in data
        assert "system" in data
        assert "meta" in data

    def test_metrics_process_fields_present(self):
        resp = client.get("/api/v1/metrics/")
        proc = resp.json()["process"]
        # Either populated fields OR graceful error key
        assert "cpu_percent" in proc or "error" in proc
        assert "uptime_seconds" in proc or "error" in proc

    def test_metrics_meta_service_name(self):
        resp = client.get("/api/v1/metrics/")
        meta = resp.json()["meta"]
        assert meta["service"] == "telemetry-twin-backend"

    def test_metrics_meta_version(self):
        resp = client.get("/api/v1/metrics/")
        meta = resp.json()["meta"]
        assert meta["version"] == "1.0.0"

    def test_metrics_system_graceful_on_sqlite(self):
        """In SQLite test mode, DB stats should either succeed or return graceful error."""
        resp = client.get("/api/v1/metrics/")
        system = resp.json()["system"]
        # Gracefully handles missing tables in SQLite
        assert isinstance(system, dict)

    def test_metrics_uptime_positive(self):
        resp = client.get("/api/v1/metrics/")
        proc = resp.json()["process"]
        if "uptime_seconds" in proc:
            assert proc["uptime_seconds"] >= 0


# ═══════════════════════════════════════════════════════════
# Tests: Prometheus endpoint
# ═══════════════════════════════════════════════════════════
class TestMetricsPrometheus:
    def test_prometheus_endpoint_returns_200(self):
        resp = client.get("/api/v1/metrics/prometheus")
        assert resp.status_code == 200

    def test_prometheus_content_type_is_text(self):
        resp = client.get("/api/v1/metrics/prometheus")
        assert "text/plain" in resp.headers.get("content-type", "")

    def test_prometheus_contains_cpu_metric(self):
        resp = client.get("/api/v1/metrics/prometheus")
        assert "twin_process_cpu_percent" in resp.text

    def test_prometheus_contains_memory_metric(self):
        resp = client.get("/api/v1/metrics/prometheus")
        assert "twin_process_memory_rss_mb" in resp.text

    def test_prometheus_contains_uptime_metric(self):
        resp = client.get("/api/v1/metrics/prometheus")
        assert "twin_process_uptime_seconds" in resp.text

    def test_prometheus_contains_snapshot_counter(self):
        resp = client.get("/api/v1/metrics/prometheus")
        assert "twin_telemetry_snapshots_total" in resp.text

    def test_prometheus_contains_alert_gauge(self):
        resp = client.get("/api/v1/metrics/prometheus")
        assert "twin_active_alerts_total" in resp.text

    def test_prometheus_contains_feedback_metrics(self):
        resp = client.get("/api/v1/metrics/prometheus")
        assert "twin_feedback_total" in resp.text
        assert "twin_feedback_helpfulness_ratio" in resp.text

    def test_prometheus_has_help_comments(self):
        resp = client.get("/api/v1/metrics/prometheus")
        assert "# HELP" in resp.text

    def test_prometheus_has_type_comments(self):
        resp = client.get("/api/v1/metrics/prometheus")
        assert "# TYPE" in resp.text
