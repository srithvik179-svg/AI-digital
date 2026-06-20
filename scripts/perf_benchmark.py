"""
Phase 3 Performance Benchmark
Seeds 50,000 telemetry snapshots across all normalized tables and runs EXPLAIN ANALYZE
to verify query performance stays under 500ms.
"""
import uuid
import random
import time
import psycopg2
import sys

DB_URL = "postgresql://postgres:postgres@localhost:5432/telemetry_db"

THERMAL_STATES = ["nominal", "moderate", "critical"]
POWER_SOURCES = ["battery", "ac"]
SSIDS = ["HomeNetwork", "Office5G", "CoffeeShop", "HotSpot"]

def seed_records(conn, num_records=50_000, batch_size=5_000):
    cur = conn.cursor()
    total_inserted = 0
    t0 = time.time()

    for batch_start in range(0, num_records, batch_size):
        batch_count = min(batch_size, num_records - batch_start)

        snapshots = []
        cpu_rows, gpu_rows, mem_rows = [], [], []
        bat_rows, disk_rows, wifi_rows = [], [], []
        thermal_rows, power_rows = [], []

        for i in range(batch_count):
            sid = str(uuid.uuid4())
            ts = f"2026-06-{random.randint(1,20):02d} {random.randint(0,23):02d}:{random.randint(0,59):02d}:{random.randint(0,59):02d}"
            device = random.choice(["laptop-mac-001", "laptop-mac-002", "laptop-mac-003"])

            snapshots.append((sid, device, ts))
            cpu_rows.append((sid, round(random.uniform(5, 95), 2), random.randint(100, 400), round(random.uniform(1200, 3600), 1)))
            gpu_rows.append((sid, round(random.uniform(0, 80), 2), round(random.uniform(30, 85), 1), round(random.uniform(0, 60), 1)))
            mem_rows.append((sid, round(random.uniform(20, 95), 2), 16384.0, round(random.uniform(4000, 15000), 1)))
            bat_rows.append((sid, round(random.uniform(5, 100), 1), round(random.uniform(70, 100), 1), round(random.uniform(25, 45), 1), random.randint(0, 800)))
            disk_rows.append((sid, round(random.uniform(10, 90), 2), random.randint(0, 500_000_000), random.randint(0, 200_000_000)))
            wifi_rows.append((sid, random.randint(-90, -30), random.choice(SSIDS), random.choice([54, 150, 300, 600])))
            thermal_rows.append((sid, round(random.uniform(35, 90), 1), random.randint(1000, 4000), random.choice(THERMAL_STATES)))
            power_rows.append((sid, random.choice(POWER_SOURCES), round(random.uniform(5, 65), 1), round(random.uniform(11000, 13000), 1)))

        cur.executemany(
            "INSERT INTO telemetry_snapshots(id, device_id, timestamp, created_at) VALUES (%s, %s, %s, NOW()) ON CONFLICT DO NOTHING",
            snapshots
        )
        cur.executemany(
            "INSERT INTO cpu_metrics(snapshot_id, cpu_usage, active_process_count, cpu_frequency_mhz, created_at) VALUES (%s,%s,%s,%s,NOW()) ON CONFLICT DO NOTHING",
            cpu_rows
        )
        cur.executemany(
            "INSERT INTO gpu_metrics(snapshot_id, gpu_usage, gpu_temperature, gpu_memory_usage, created_at) VALUES (%s,%s,%s,%s,NOW()) ON CONFLICT DO NOTHING",
            gpu_rows
        )
        cur.executemany(
            "INSERT INTO memory_metrics(snapshot_id, memory_usage, total_mb, used_mb, created_at) VALUES (%s,%s,%s,%s,NOW()) ON CONFLICT DO NOTHING",
            mem_rows
        )
        cur.executemany(
            "INSERT INTO battery_metrics(snapshot_id, battery_level, battery_health, battery_temperature, cycle_count, created_at) VALUES (%s,%s,%s,%s,%s,NOW()) ON CONFLICT DO NOTHING",
            bat_rows
        )
        cur.executemany(
            "INSERT INTO disk_metrics(snapshot_id, disk_usage, read_bytes_sec, write_bytes_sec, created_at) VALUES (%s,%s,%s,%s,NOW()) ON CONFLICT DO NOTHING",
            disk_rows
        )
        cur.executemany(
            "INSERT INTO wifi_metrics(snapshot_id, signal_strength_dbm, ssid, link_speed_mbps, created_at) VALUES (%s,%s,%s,%s,NOW()) ON CONFLICT DO NOTHING",
            wifi_rows
        )
        cur.executemany(
            "INSERT INTO thermal_metrics(snapshot_id, cpu_temperature, fan_speed_rpm, thermal_state, created_at) VALUES (%s,%s,%s,%s,NOW()) ON CONFLICT DO NOTHING",
            thermal_rows
        )
        cur.executemany(
            "INSERT INTO power_metrics(snapshot_id, power_source, power_draw_watts, voltage_mv, created_at) VALUES (%s,%s,%s,%s,NOW()) ON CONFLICT DO NOTHING",
            power_rows
        )
        conn.commit()
        total_inserted += batch_count
        print(f"  Seeded {total_inserted}/{num_records} rows...")

    elapsed = time.time() - t0
    print(f"\n✅ Seeded {total_inserted} records in {elapsed:.2f}s")
    cur.close()


def run_explain_analyze(conn, label, sql):
    cur = conn.cursor()
    t0 = time.time()
    cur.execute(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT) {sql}")
    rows = cur.fetchall()
    elapsed_ms = (time.time() - t0) * 1000
    plan = "\n".join(r[0] for r in rows)

    # Extract actual time from EXPLAIN output
    actual_time = None
    for line in rows:
        if "Execution Time:" in line[0]:
            parts = line[0].split(":")
            actual_time = float(parts[1].strip().split(" ")[0])
            break

    print(f"\n--- {label} ---")
    print(plan)
    status = "✅ PASS" if (actual_time and actual_time < 500) else "❌ FAIL"
    print(f"\n{status}  Wall time: {elapsed_ms:.1f}ms | PG Execution: {actual_time}ms")
    cur.close()
    return actual_time


def main():
    print("Connecting to PostgreSQL...")
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = False

    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM telemetry_snapshots;")
    existing = cur.fetchone()[0]
    cur.close()
    print(f"Existing snapshot count: {existing}")

    if existing < 50_000:
        needed = 50_000 - existing
        print(f"\nSeeding {needed} additional records to reach 50,000...")
        seed_records(conn, num_records=needed)
    else:
        print("Already have 50,000+ records - skipping seed.")

    print("\n\n=== QUERY PERFORMANCE BENCHMARK ===\n")

    # Q1: Latest 100 snapshots for a device (dashboard)
    q1 = """
        SELECT s.id, s.timestamp, c.cpu_usage, m.memory_usage, t.cpu_temperature, b.battery_level
        FROM telemetry_snapshots s
        JOIN cpu_metrics c ON c.snapshot_id = s.id
        JOIN memory_metrics m ON m.snapshot_id = s.id
        JOIN thermal_metrics t ON t.snapshot_id = s.id
        JOIN battery_metrics b ON b.snapshot_id = s.id
        WHERE s.device_id = 'laptop-mac-001'
        ORDER BY s.timestamp DESC
        LIMIT 100;
    """
    run_explain_analyze(conn, "Q1: Latest 100 dashboard snapshots (device_id + timestamp index)", q1)

    # Q2: High CPU alert scan
    q2 = """
        SELECT s.device_id, s.timestamp, c.cpu_usage
        FROM telemetry_snapshots s
        JOIN cpu_metrics c ON c.snapshot_id = s.id
        WHERE c.cpu_usage > 85.0
        ORDER BY s.timestamp DESC
        LIMIT 50;
    """
    run_explain_analyze(conn, "Q2: High CPU alert scan (cpu_usage > 85%)", q2)

    # Q3: Thermal warning state scan
    q3 = """
        SELECT s.device_id, s.timestamp, t.cpu_temperature, t.thermal_state, t.fan_speed_rpm
        FROM telemetry_snapshots s
        JOIN thermal_metrics t ON t.snapshot_id = s.id
        WHERE t.thermal_state = 'critical'
        ORDER BY s.timestamp DESC
        LIMIT 50;
    """
    run_explain_analyze(conn, "Q3: Critical thermal state scan (indexed thermal_state)", q3)

    # Q4: Aggregate CPU stats per device over time range
    q4 = """
        SELECT s.device_id,
               AVG(c.cpu_usage) AS avg_cpu,
               MAX(c.cpu_usage) AS peak_cpu,
               MIN(b.battery_level) AS min_battery
        FROM telemetry_snapshots s
        JOIN cpu_metrics c ON c.snapshot_id = s.id
        JOIN battery_metrics b ON b.snapshot_id = s.id
        WHERE s.timestamp >= NOW() - INTERVAL '7 days'
        GROUP BY s.device_id;
    """
    run_explain_analyze(conn, "Q4: 7-day aggregate stats per device", q4)

    # Q5: Full join across all 8 child tables (RAG context fetch)
    q5 = """
        SELECT s.id, s.device_id, s.timestamp,
               c.cpu_usage, c.active_process_count,
               g.gpu_usage,
               m.memory_usage,
               b.battery_level, b.battery_health,
               d.disk_usage,
               w.ssid, w.signal_strength_dbm,
               t.cpu_temperature, t.thermal_state,
               p.power_source, p.power_draw_watts
        FROM telemetry_snapshots s
        JOIN cpu_metrics c ON c.snapshot_id = s.id
        JOIN gpu_metrics g ON g.snapshot_id = s.id
        JOIN memory_metrics m ON m.snapshot_id = s.id
        JOIN battery_metrics b ON b.snapshot_id = s.id
        JOIN disk_metrics d ON d.snapshot_id = s.id
        JOIN wifi_metrics w ON w.snapshot_id = s.id
        JOIN thermal_metrics t ON t.snapshot_id = s.id
        JOIN power_metrics p ON p.snapshot_id = s.id
        WHERE s.device_id = 'laptop-mac-001'
        ORDER BY s.timestamp DESC
        LIMIT 10;
    """
    run_explain_analyze(conn, "Q5: Full 8-table join for RAG context (latest 10)", q5)

    conn.close()
    print("\n\n=== BENCHMARK COMPLETE ===")


if __name__ == "__main__":
    main()
