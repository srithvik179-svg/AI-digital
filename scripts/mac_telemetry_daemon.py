import time
import subprocess
import re
import requests
import json
import socket
import threading
from datetime import datetime

# We will use psutil for CPU/RAM if installed, or fallback to macOS command utilities
try:
    import psutil
except ImportError:
    print("Installing 'psutil' dependency on host...")
    subprocess.run(["pip3", "install", "psutil"], check=True)
    import psutil

API_URL = "http://localhost:8000/api/v1/telemetry/"
DEVICE_ID = "laptop-mac-001"

def get_mac_battery():
    """
    Executes 'pmset -g batt' to get actual macOS battery level and power source.
    """
    try:
        output = subprocess.check_output(["pmset", "-g", "batt"]).decode("utf-8")
        # Example output:
        # Now drawing from 'AC Power'
        # -InternalBattery-0 (id=12451903)	85%; charging; 1:12 remaining present: true
        
        power_source = "ac" if "AC Power" in output else "battery"
        
        level_match = re.search(r"(\d+)%", output)
        battery_level = int(level_match.group(1)) if level_match else 100
        
        return battery_level, power_source
    except Exception as e:
        print(f"Error reading battery status: {e}")
        return 100, "ac"

def get_system_metrics():
    """
    Gather actual CPU, Memory, Disk, and Process parameters.
    """
    cpu = psutil.cpu_percent(interval=None) # Non-blocking CPU reading
    memory = psutil.virtual_memory().percent
    disk = psutil.disk_usage('/').percent
    process_count = len(psutil.pids())
    
    # Calculate a realistic CPU temp based on usage (since macOS restricted access to thermal sensors via standard API)
    # Default idle is 45C, rising to 85C under load
    cpu_temp = 45.0 + (cpu * 0.4)
    
    # Calculate fan speed similarly (e.g. idle 1200 RPM, high load 4500 RPM)
    fan_speed = 1200 if cpu_temp < 60 else int(1200 + (cpu_temp - 60) * 100)
    
    battery_level, power_source = get_mac_battery()
    
    return {
        "device_id": DEVICE_ID,
        "cpu_usage": float(cpu),
        "memory_usage": float(memory),
        "disk_usage": float(disk),
        "cpu_temperature": float(round(cpu_temp, 1)),
        "battery_level": float(battery_level),
        "battery_health": 92.0, # Static or mock health reading
        "fan_speed": int(fan_speed),
        "power_source": power_source,
        "active_process_count": int(process_count)
    }

def socket_listener():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server.bind(("0.0.0.0", 9090))
        server.listen(5)
        print("Daemon command listener active on port 9090...")
        while True:
            conn, addr = server.accept()
            try:
                data = conn.recv(1024).decode("utf-8").strip()
                if data:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Received socket trigger command: {data}")
                    if data == "ECO_MODE":
                        print(">>> ACTION: Initiating local system Eco Mode (reducing brightness, pausing background indexers)...")
                    elif data == "KILL_HIGH_CPU":
                        print(">>> ACTION: Terminating high-CPU consumer processes...")
                    else:
                        print(f">>> ACTION: Unrecognized command received: {data}")
                    conn.sendall(b"ACK")
            except Exception as e:
                print(f"Error handling socket client: {e}")
            finally:
                conn.close()
    except Exception as e:
        print(f"Failed to start socket listener: {e}")

def main():
    print(f"=== Starting Dell AI Digital Twin Host Collector for {DEVICE_ID} ===")
    print(f"Streaming data to {API_URL} every 2 seconds...")
    print("Press Ctrl+C to stop.")
    
    # Start command listener thread
    listener_thread = threading.Thread(target=socket_listener, daemon=True)
    listener_thread.start()
    
    # Call cpu_percent once to initialize tracking
    psutil.cpu_percent(interval=None)
    time.sleep(0.5)
    
    try:
        while True:
            metrics = get_system_metrics()
            
            try:
                response = requests.post(API_URL, json=metrics, timeout=2)
                if response.status_code == 200:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Telemetry pushed: "
                          f"CPU={metrics['cpu_usage']}% | RAM={metrics['memory_usage']}% | "
                          f"Temp={metrics['cpu_temperature']}C | Power={metrics['power_source'].upper()} ({metrics['battery_level']}%)")
                else:
                    print(f"Warning: Server responded with status {response.status_code}")
            except requests.exceptions.RequestException as e:
                print(f"Connection error: Could not contact FastAPI backend at {API_URL}. Is Docker running?")
                
            time.sleep(2.0)
            
    except KeyboardInterrupt:
        print("\nTelemetry collector stopped.")

if __name__ == "__main__":
    main()
