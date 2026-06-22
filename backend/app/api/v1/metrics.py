"""
System Metrics API Router.
Reports process resource consumption and key system KPIs for monitoring.
Compatible with standard Prometheus text-format scraping via HTTP.
"""
import os
import time
import psutil
from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.database import get_db
from app.core.logging import logger

router = APIRouter()

_start_time = time.time()


def _get_process_metrics():
    """Collect CPU and memory metrics for the current process."""
    try:
        proc = psutil.Process(os.getpid())
        return {
            "cpu_percent": proc.cpu_percent(interval=0.1),
            "memory_rss_mb": round(proc.memory_info().rss / 1024 / 1024, 2),
            "memory_vms_mb": round(proc.memory_info().vms / 1024 / 1024, 2),
            "threads": proc.num_threads(),
            "uptime_seconds": round(time.time() - _start_time, 1),
        }
    except Exception:
        return {"error": "unable to collect process metrics"}


def _get_db_stats(db: Session) -> dict:
    """Query key telemetry system KPIs from PostgreSQL."""
    try:
        snapshot_count = db.execute(text("SELECT COUNT(*) FROM telemetry_snapshots")).scalar() or 0
        alert_count    = db.execute(text("SELECT COUNT(*) FROM telemetry_alerts WHERE acknowledged = FALSE")).scalar() or 0
        feedback_count = db.execute(text("SELECT COUNT(*) FROM recommendation_feedback")).scalar() or 0
        helpful_count  = db.execute(text("SELECT COUNT(*) FROM recommendation_feedback WHERE rating = 1")).scalar() or 0
        return {
            "telemetry_snapshots_total": snapshot_count,
            "active_unacknowledged_alerts": alert_count,
            "feedback_submissions_total": feedback_count,
            "feedback_helpful_total": helpful_count,
            "feedback_helpfulness_ratio": round(helpful_count / feedback_count, 3) if feedback_count > 0 else 0.0,
        }
    except Exception as e:
        logger.warning(f"DB stats query failed: {e}")
        return {"error": "db unavailable"}


@router.get("/", summary="JSON system metrics")
def get_metrics_json(db: Session = Depends(get_db)):
    """
    Returns operational system metrics in JSON format.
    Includes process resource consumption and key database KPIs.
    """
    return {
        "process": _get_process_metrics(),
        "system": _get_db_stats(db),
        "meta": {
            "service": "telemetry-twin-backend",
            "version": "1.0.0",
        }
    }


@router.get("/prometheus", response_class=PlainTextResponse, summary="Prometheus-format metrics")
def get_metrics_prometheus(db: Session = Depends(get_db)):
    """
    Returns metrics in Prometheus text exposition format.
    Compatible with Prometheus scrape jobs targeting /api/v1/metrics/prometheus.
    """
    proc = _get_process_metrics()
    db_stats = _get_db_stats(db)

    lines = [
        "# HELP twin_process_cpu_percent Current process CPU usage percentage",
        "# TYPE twin_process_cpu_percent gauge",
        f'twin_process_cpu_percent{{service="backend"}} {proc.get("cpu_percent", 0)}',
        "",
        "# HELP twin_process_memory_rss_mb Resident Set Size memory in megabytes",
        "# TYPE twin_process_memory_rss_mb gauge",
        f'twin_process_memory_rss_mb{{service="backend"}} {proc.get("memory_rss_mb", 0)}',
        "",
        "# HELP twin_process_uptime_seconds Process uptime in seconds",
        "# TYPE twin_process_uptime_seconds counter",
        f'twin_process_uptime_seconds{{service="backend"}} {proc.get("uptime_seconds", 0)}',
        "",
        "# HELP twin_telemetry_snapshots_total Total number of ingested telemetry snapshots",
        "# TYPE twin_telemetry_snapshots_total counter",
        f'twin_telemetry_snapshots_total {db_stats.get("telemetry_snapshots_total", 0)}',
        "",
        "# HELP twin_active_alerts_total Active unacknowledged alerts",
        "# TYPE twin_active_alerts_total gauge",
        f'twin_active_alerts_total {db_stats.get("active_unacknowledged_alerts", 0)}',
        "",
        "# HELP twin_feedback_total Total feedback submissions",
        "# TYPE twin_feedback_total counter",
        f'twin_feedback_total {db_stats.get("feedback_submissions_total", 0)}',
        "",
        "# HELP twin_feedback_helpfulness_ratio Fraction of helpful ratings",
        "# TYPE twin_feedback_helpfulness_ratio gauge",
        f'twin_feedback_helpfulness_ratio {db_stats.get("feedback_helpfulness_ratio", 0)}',
        "",
    ]
    return "\n".join(lines)
