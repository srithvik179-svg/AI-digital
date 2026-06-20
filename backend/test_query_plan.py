from app.core.database import SessionLocal
from sqlalchemy import text

def run_diagnostics():
    db = SessionLocal()
    try:
        # Diagnostic Query: Fetch CPU metrics joined with Snapshots
        query = """
        EXPLAIN (ANALYZE, BUFFERS) 
        SELECT ts.timestamp, cpu.cpu_usage 
        FROM telemetry_snapshots ts 
        JOIN cpu_metrics cpu ON ts.id = cpu.snapshot_id 
        WHERE ts.device_id = 'laptop-mac-001' 
        ORDER BY ts.timestamp DESC 
        LIMIT 50
        """
        
        print("=== RUNNING EXPLAIN ANALYZE ON HISTORICAL DASHBOARD QUERY ===")
        res = db.execute(text(query)).all()
        for r in res:
            print(r[0])
            
        print("\n=== RUNNING EXPLAIN ANALYZE ON WARNING SCAN QUERY ===")
        warning_query = """
        EXPLAIN (ANALYZE, BUFFERS)
        SELECT ts.device_id, ts.timestamp, th.cpu_temperature
        FROM thermal_metrics th
        JOIN telemetry_snapshots ts ON th.snapshot_id = ts.id
        WHERE th.thermal_state = 'critical'
        LIMIT 50
        """
        res_warning = db.execute(text(warning_query)).all()
        for r in res_warning:
            print(r[0])
            
    except Exception as e:
        print("Error running diagnostics:", str(e))
    finally:
        db.close()

if __name__ == "__main__":
    run_diagnostics()
