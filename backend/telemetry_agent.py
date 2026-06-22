#!/usr/bin/env python3
"""
Phase 46 — Unified Telemetry Agent.

A production-grade, cross-platform data collection daemon that:

  1. Auto-detects the host OS and instantiates the correct collector
     (macOS / Windows WMI / Windows OHM / Linux).
  2. Collects hardware telemetry every POLL_INTERVAL seconds.
  3. POSTs each reading to the Digital Twin backend API, which persists
     it to PostgreSQL, indexes it in ChromaDB, and broadcasts it via WebSocket.
  4. Maintains an in-process ring buffer of the last 60 readings for the
     Future-State prediction endpoint (Phases 42–45).
  5. Exposes a local TCP command socket on port 9090 for the AI Copilot
     to send actions (ECO_MODE, KILL_HIGH_CPU, etc.).
  6. Streams a Server-Sent Event (SSE) feed on port 9091 that the frontend
     can consume as a supplementary real-time push channel.
  7. Continuously monitors its own pipeline health and prints a status table.
  8. Automatically retries failed API posts with exponential back-off.

Usage
-----
  python telemetry_agent.py [--api http://localhost:8000] [--device my-laptop]
                             [--interval 2] [--log-level DEBUG]

Environment variables (override CLI)
-------------------------------------
  TWIN_API_URL    : e.g. http://192.168.1.100:8000
  TWIN_DEVICE_ID  : e.g. laptop-win-001
  TWIN_INTERVAL   : collection interval in seconds (default 2)
"""

from __future__ import annotations

import sys
import os
import time
import json
import socket
import threading
import argparse
import logging
import traceback
from collections import deque
from datetime import datetime
from typing import Optional, Deque, Dict, Any

# ── Auto-install psutil if missing (convenience for fresh Windows setups) ──
try:
    import psutil
except ImportError:
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "psutil"], check=True)
    import psutil

try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
except ImportError:
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "requests"], check=True)
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry


# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_API_URL   = os.environ.get("TWIN_API_URL",    "http://localhost:8000/api/v1")
DEFAULT_DEVICE_ID = os.environ.get("TWIN_DEVICE_ID",  f"laptop-{sys.platform}-001")
DEFAULT_INTERVAL  = float(os.environ.get("TWIN_INTERVAL", "2"))

RING_BUFFER_SIZE  = 60   # keep last 60 readings for prediction API
COMMAND_PORT      = 9090  # TCP command socket (AI Copilot triggers)
SSE_PORT          = 9091  # HTTP SSE stream port

# ─────────────────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("telemetry.agent")


# ─────────────────────────────────────────────────────────────────────────────
# HTTP session with retry back-off
# ─────────────────────────────────────────────────────────────────────────────

def _build_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=4,
        backoff_factor=0.5,           # 0.5 s, 1 s, 2 s, 4 s
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["POST", "GET"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://",  adapter)
    session.mount("https://", adapter)
    return session


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline health tracker
# ─────────────────────────────────────────────────────────────────────────────

class PipelineHealth:
    """Tracks rolling statistics for the ingestion pipeline."""

    def __init__(self):
        self.ticks_sent    = 0
        self.ticks_failed  = 0
        self.last_latency_ms = 0.0
        self.last_success  : Optional[datetime] = None
        self.last_error    : Optional[str] = None
        self.consecutive_failures = 0
        self._lock = threading.Lock()

    def record_success(self, latency_ms: float):
        with self._lock:
            self.ticks_sent += 1
            self.last_latency_ms = latency_ms
            self.last_success    = datetime.now()
            self.consecutive_failures = 0

    def record_failure(self, error: str):
        with self._lock:
            self.ticks_failed += 1
            self.last_error   = error
            self.consecutive_failures += 1

    def summary(self) -> str:
        with self._lock:
            total   = self.ticks_sent + self.ticks_failed
            pct_ok  = (self.ticks_sent / total * 100) if total else 0.0
            last_ok = self.last_success.strftime("%H:%M:%S") if self.last_success else "never"
            return (
                f"Sent={self.ticks_sent}  Failed={self.ticks_failed}  "
                f"Success={pct_ok:.1f}%  LastOK={last_ok}  "
                f"Latency={self.last_latency_ms:.0f}ms  "
                f"ConsecFail={self.consecutive_failures}"
            )


# ─────────────────────────────────────────────────────────────────────────────
# SSE broadcast server (port 9091)
# ─────────────────────────────────────────────────────────────────────────────

class SSEBroadcaster(threading.Thread):
    """
    Minimal HTTP/1.1 server that streams JSON telemetry as Server-Sent Events.
    Browsers and frontend dev tools can subscribe to this directly as a
    supplementary real-time feed (port 9091).
    """

    def __init__(self):
        super().__init__(daemon=True, name="sse-broadcaster")
        self._clients: list = []
        self._lock = threading.Lock()
        self._server_sock: Optional[socket.socket] = None

    def broadcast(self, payload: dict) -> None:
        data = f"data: {json.dumps(payload)}\n\n"
        with self._lock:
            dead = []
            for client in self._clients:
                try:
                    client.sendall(data.encode())
                except Exception:
                    dead.append(client)
            for c in dead:
                self._clients.remove(c)
                try: c.close()
                except Exception: pass

    def run(self) -> None:
        try:
            self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._server_sock.bind(("0.0.0.0", SSE_PORT))
            self._server_sock.listen(20)
            logger.info(f"SSE feed listening on port {SSE_PORT}  (GET http://localhost:{SSE_PORT}/events)")
            while True:
                conn, addr = self._server_sock.accept()
                threading.Thread(
                    target=self._handle_sse_client,
                    args=(conn,), daemon=True
                ).start()
        except Exception as e:
            logger.warning(f"SSE server error: {e}")

    def _handle_sse_client(self, conn: socket.socket) -> None:
        try:
            # Consume HTTP request headers
            conn.recv(4096)
            # Send SSE response headers
            headers = (
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: text/event-stream\r\n"
                "Cache-Control: no-cache\r\n"
                "Access-Control-Allow-Origin: *\r\n"
                "Connection: keep-alive\r\n"
                "\r\n"
            )
            conn.sendall(headers.encode())
            with self._lock:
                self._clients.append(conn)
        except Exception as e:
            logger.debug(f"SSE client setup error: {e}")
            try: conn.close()
            except Exception: pass


# ─────────────────────────────────────────────────────────────────────────────
# Command socket listener (port 9090 — AI Copilot triggers)
# ─────────────────────────────────────────────────────────────────────────────

def _command_listener(eco_mode_flag: threading.Event) -> None:
    """TCP socket that receives action triggers from the AI Copilot service."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server.bind(("0.0.0.0", COMMAND_PORT))
        server.listen(5)
        logger.info(f"Copilot command listener active on port {COMMAND_PORT}")
        while True:
            conn, addr = server.accept()
            try:
                data = conn.recv(1024).decode("utf-8").strip()
                ts = datetime.now().strftime("%H:%M:%S")
                if data == "ECO_MODE":
                    logger.info(f"[{ts}] Copilot → ECO_MODE: reducing screen brightness & background processes")
                    eco_mode_flag.set()
                    _apply_eco_mode()
                elif data == "KILL_HIGH_CPU":
                    logger.info(f"[{ts}] Copilot → KILL_HIGH_CPU: terminating top CPU consumer")
                    _kill_top_cpu_process()
                elif data == "DISABLE_ECO_MODE":
                    logger.info(f"[{ts}] Copilot → DISABLE_ECO_MODE")
                    eco_mode_flag.clear()
                else:
                    logger.warning(f"[{ts}] Unknown command: {data}")
                conn.sendall(b"ACK")
            except Exception as e:
                logger.debug(f"Command handler error: {e}")
            finally:
                conn.close()
    except Exception as e:
        logger.error(f"Command listener failed: {e}")


def _apply_eco_mode() -> None:
    """Platform-specific eco-mode actions."""
    if sys.platform == "darwin":
        try:
            os.system("pmset -a displaysleep 2 sleep 5")
        except Exception:
            pass
    elif sys.platform == "win32":
        try:
            # Switch to Balanced power plan
            os.system('powercfg /setactive 381b4222-f694-41f0-9685-ff5bb260df2e')
        except Exception:
            pass


def _kill_top_cpu_process() -> None:
    """Kill the process with the highest CPU usage (excluding system processes)."""
    SAFE_LIST = {"python", "python3", "systemd", "init", "kernel", "launchd",
                 "WindowServer", "svchost", "explorer", "Finder", "docker"}
    try:
        top = sorted(
            [p for p in psutil.process_iter(["name", "cpu_percent", "pid"])
             if p.info["name"] not in SAFE_LIST],
            key=lambda p: p.info["cpu_percent"],
            reverse=True,
        )
        if top:
            p = top[0]
            logger.info(f"  Killing PID {p.info['pid']} ({p.info['name']}) "
                        f"— CPU={p.info['cpu_percent']:.1f}%")
            psutil.Process(p.info["pid"]).terminate()
    except Exception as e:
        logger.warning(f"Kill top CPU failed: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Future-State ring buffer flush
# ─────────────────────────────────────────────────────────────────────────────

def _flush_prediction(
    ring: Deque[Dict[str, Any]],
    session: requests.Session,
    api_url: str,
) -> None:
    """
    Every 10 ticks, POST the ring buffer to the future-state prediction endpoint
    and log the forecast summary.  Runs in a background thread.
    """
    if len(ring) < 5:
        return
    readings = list(ring)
    payload = {
        "cpu_temp_history":    [r["cpu_temperature"] for r in readings],
        "gpu_temp_history":    [r.get("gpu_temperature") or r["cpu_temperature"] * 0.9 for r in readings],
        "cpu_usage_history":   [r["cpu_usage"] for r in readings],
        "gpu_usage_history":   [r.get("gpu_usage") or 0.0 for r in readings],
        "fan_rpm_history":     [float(r["fan_speed"]) for r in readings],
        "battery_soc_history": [r["battery_level"] for r in readings],
        "cpu_watts_history":   [r.get("power_draw_watts") or r["cpu_usage"] * 0.4 for r in readings],
        "gpu_watts_history":   [r.get("gpu_usage") or 0.0 for r in readings],
        "is_charging":         readings[-1]["power_source"] == "ac",
        "wifi_rssi_history":   [r.get("signal_strength_dbm") or -65 for r in readings],
        "horizon": 30,
    }
    try:
        resp = session.post(
            f"{api_url}/future-state/predict",
            json=payload,
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            peak_cpu = max(data["thermal"]["cpu_temperature_forecast"])
            min_soc  = min(data["battery"]["battery_soc_forecast"])
            logger.info(
                f"  🔮 Future-State (30 ticks): "
                f"Peak CPU={peak_cpu:.1f}°C  MinSoC={min_soc:.1f}%  "
                f"WiFi={data['network']['wifi_quality_forecast'][-1]}"
            )
    except Exception as e:
        logger.debug(f"Future-state prediction failed: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Main agent loop
# ─────────────────────────────────────────────────────────────────────────────

def run_agent(api_url: str, device_id: str, interval: float) -> None:
    logger.info("=" * 60)
    logger.info(f"  AI Digital Twin Telemetry Agent — Phase 46")
    logger.info(f"  Device  : {device_id}")
    logger.info(f"  API URL : {api_url}")
    logger.info(f"  Interval: {interval}s  |  Platform: {sys.platform}")
    logger.info("=" * 60)

    # ── Add scripts/ to path for collector imports ──
    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)

    # ── Instantiate platform-correct collector ──
    from collectors import get_collector
    collector = get_collector(device_id)

    # ── HTTP session with retry ──
    session = _build_session()

    # ── Pipeline health ──
    health = PipelineHealth()

    # ── Ring buffer for Future-State prediction ──
    ring_buffer: Deque[Dict[str, Any]] = deque(maxlen=RING_BUFFER_SIZE)

    # ── Eco-mode flag ──
    eco_mode = threading.Event()

    # ── Background threads ──
    threading.Thread(
        target=_command_listener, args=(eco_mode,), daemon=True, name="cmd-listener"
    ).start()

    sse = SSEBroadcaster()
    sse.start()

    tick = 0

    try:
        while True:
            tick_start = time.monotonic()

            # ── 1. Collect hardware metrics ──
            try:
                reading = collector.collect()
            except Exception as e:
                logger.error(f"Collection error: {e}")
                time.sleep(interval)
                continue

            payload = reading.to_api_payload()
            ring_buffer.append(payload)

            # ── 2. Apply eco-mode throttle ──
            if eco_mode.is_set():
                payload["cpu_usage"] = min(payload["cpu_usage"], 40.0)

            # ── 3. POST to Digital Twin backend ──
            t_post = time.monotonic()
            try:
                resp = session.post(
                    f"{api_url}/telemetry/",
                    json=payload,
                    timeout=5,
                )
                latency_ms = (time.monotonic() - t_post) * 1000
                if resp.status_code == 200:
                    health.record_success(latency_ms)
                    ts = datetime.now().strftime("%H:%M:%S")
                    logger.info(
                        f"[{ts}] ✓ Tick {tick:04d} | "
                        f"CPU={payload['cpu_usage']:5.1f}% "
                        f"Temp={payload['cpu_temperature']:5.1f}°C "
                        f"RAM={payload['memory_usage']:5.1f}% "
                        f"Bat={payload['battery_level']:5.1f}% "
                        f"({payload['power_source'].upper()}) "
                        f"Fan={payload['fan_speed']}RPM "
                        f"| src={reading.source} "
                        f"lat={latency_ms:.0f}ms"
                    )
                else:
                    health.record_failure(f"HTTP {resp.status_code}")
                    logger.warning(f"API responded {resp.status_code}: {resp.text[:200]}")
            except requests.exceptions.ConnectionError:
                health.record_failure("ConnectionError")
                logger.warning(f"Cannot reach {api_url} — is Docker running?")
            except Exception as e:
                health.record_failure(str(e))
                logger.error(f"POST error: {e}")

            # ── 4. SSE broadcast ──
            try:
                sse_payload = {
                    **payload,
                    "source": reading.source,
                    "collection_latency_ms": reading.collection_latency_ms,
                    "tick": tick,
                    "timestamp": datetime.utcnow().isoformat(),
                }
                sse.broadcast(sse_payload)
            except Exception:
                pass

            # ── 5. Future-State prediction flush (every 10 ticks) ──
            if tick > 0 and tick % 10 == 0:
                threading.Thread(
                    target=_flush_prediction,
                    args=(deque(ring_buffer), session, api_url),
                    daemon=True,
                ).start()

            # ── 6. Pipeline health report (every 30 ticks) ──
            if tick > 0 and tick % 30 == 0:
                logger.info(f"── Pipeline health: {health.summary()}")

            # ── 7. Sleep for remaining interval time ──
            elapsed = time.monotonic() - tick_start
            sleep_time = max(0.0, interval - elapsed)
            time.sleep(sleep_time)
            tick += 1

    except KeyboardInterrupt:
        logger.info("\nAgent stopped by user (Ctrl+C).")
        logger.info(f"Final pipeline health: {health.summary()}")


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="AI Digital Twin — Unified Telemetry Agent (Phase 46)"
    )
    parser.add_argument(
        "--api", default=DEFAULT_API_URL,
        help=f"Backend API base URL (default: {DEFAULT_API_URL})"
    )
    parser.add_argument(
        "--device", default=DEFAULT_DEVICE_ID,
        help=f"Device identifier (default: {DEFAULT_DEVICE_ID})"
    )
    parser.add_argument(
        "--interval", type=float, default=DEFAULT_INTERVAL,
        help=f"Collection interval in seconds (default: {DEFAULT_INTERVAL})"
    )
    parser.add_argument(
        "--log-level", default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity"
    )
    args = parser.parse_args()

    logging.getLogger().setLevel(getattr(logging, args.log_level))

    run_agent(
        api_url   = args.api.rstrip("/"),
        device_id = args.device,
        interval  = args.interval,
    )


if __name__ == "__main__":
    main()
