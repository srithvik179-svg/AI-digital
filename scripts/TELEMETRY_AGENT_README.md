# Phase 46 — Live Telemetry Agent Setup Guide

## Quick Start

### macOS / Linux (current machine)
```bash
# From the project root
python scripts/telemetry_agent.py \
  --api http://localhost:8000/api/v1 \
  --device laptop-mac-001 \
  --interval 2
```

### Windows (Performance Counters only)
```batch
pip install psutil wmi pywin32 requests
python scripts\telemetry_agent.py ^
  --api http://<twin-server-ip>:8000/api/v1 ^
  --device laptop-win-001
```

### Windows + OpenHardwareMonitor (full GPU + fan + voltage data)
1. Download OpenHardwareMonitor ≥ 0.9.6  
   https://openhardwaremonitor.org/downloads/

2. Run as **Administrator** → Options → ✅ **Enable WMI Provider**

3. Keep OHM running in the background, then:
```batch
pip install psutil wmi pywin32 requests
python scripts\telemetry_agent.py --device laptop-win-001
```

---

## Architecture

```
Host Machine (any OS)
└── telemetry_agent.py
      ├── collectors/
      │     ├── mac_collector.py          (psutil + pmset + airport CLI)
      │     ├── windows_ohm_collector.py  (OHM WMI namespace: full sensors)
      │     ├── windows_wmi_collector.py  (Win32_* + ACPI thermal zones)
      │     └── linux_collector.py        (psutil + /sys + iw + nvidia-smi)
      ├── TCP socket :9090               (AI Copilot command channel)
      └── SSE server :9091               (supplementary HTTP event stream)

Docker Backend
└── FastAPI
      ├── POST /api/v1/telemetry/        (primary ingestion)
      ├── GET  /api/v1/live-stream/sse   (SSE fan-out to frontend)
      ├── GET  /api/v1/live-stream/status (pipeline health)
      ├── POST /api/v1/live-stream/register
      ├── POST /api/v1/live-stream/heartbeat
      └── POST /api/v1/live-stream/disconnect
```

## Data Sources per Platform

| Metric               | macOS          | Windows OHM       | Windows WMI     | Linux               |
|----------------------|----------------|-------------------|-----------------|---------------------|
| CPU %                | psutil         | psutil            | psutil          | psutil              |
| CPU Temp             | SMC / estimate | OHM (exact cores) | ACPI thermal    | /sys/class/thermal  |
| CPU Freq (MHz)       | psutil         | OHM clocks        | Win32_Processor | psutil              |
| GPU %                | powermetrics   | OHM GPU load      | N/A             | nvidia-smi          |
| GPU Temp             | N/A            | OHM GPU temp      | N/A             | nvidia-smi          |
| Fan RPM              | estimate       | OHM fan sensors   | estimate        | hwmon / psutil fans |
| Battery %            | pmset          | Win32_Battery     | Win32_Battery   | /sys/power_supply   |
| Battery Health       | system_profiler| Win32_Battery     | Win32_Battery   | energy_full ratio   |
| Cycle Count          | system_profiler| Win32_Battery     | Win32_Battery   | cycle_count         |
| Power Draw (W)       | N/A            | OHM CPU package   | N/A             | N/A                 |
| Voltage (mV)         | N/A            | OHM voltage       | DesignVoltage   | voltage_now         |
| WiFi SSID / RSSI     | airport CLI    | netsh wlan        | netsh wlan      | iw / iwconfig       |
| Disk I/O rate        | psutil         | psutil            | psutil          | psutil              |
| Process count        | psutil         | psutil            | psutil          | psutil              |

## SSE Event Format

Subscribe to `GET http://localhost:8000/api/v1/live-stream/sse`:

```javascript
const es = new EventSource('http://localhost:8000/api/v1/live-stream/sse');
es.addEventListener('telemetry_tick', e => {
  const data = JSON.parse(e.data);
  console.log(data.cpu_usage, data.cpu_temperature, data.battery_level);
});
```

## CLI Options

| Flag          | Default                          | Description                   |
|---------------|----------------------------------|-------------------------------|
| `--api`       | `http://localhost:8000/api/v1`   | Backend API base URL          |
| `--device`    | `laptop-<platform>-001`          | Device identifier             |
| `--interval`  | `2`                              | Collection interval (seconds) |
| `--log-level` | `INFO`                           | DEBUG / INFO / WARNING        |

## Environment Variables

```bash
TWIN_API_URL=http://192.168.1.100:8000/api/v1
TWIN_DEVICE_ID=my-custom-device-id
TWIN_INTERVAL=1   # 1-second polling
```
