import io
import time
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.database import Base, get_db
from app.models.telemetry import TelemetryRecord

# Setup local SQLite database for fast unit testing, avoiding postgres interference
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Override the DB dependency
def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    # Create tables
    Base.metadata.create_all(bind=engine)
    yield
    # Drop tables
    Base.metadata.drop_all(bind=engine)

def generate_mock_csv_content(num_rows: int) -> str:
    """
    Generate mock CSV data in memory matching standard telemetry keys.
    Includes some rows with missing values or invalid values for verification.
    """
    header = "device_id,cpu_usage,memory_usage,disk_usage,cpu_temperature,battery_level,battery_health,fan_speed,power_source,active_process_count,timestamp\n"
    lines = [header]
    
    # 50,000 standard valid rows
    for i in range(num_rows):
        lines.append(f"laptop-mac-test,{20.0 + (i % 10)},65.0,42.0,55.0,80.0,95.0,1500,ac,120,2026-06-20 12:00:00\n")
        
    # Append a few skipped bad rows to test validation
    lines.append("laptop-mac-test,-10.0,65.0,42.0,55.0,80.0,95.0,1500,ac,120,2026-06-20 12:00:00\n") # Bad CPU (negative)
    lines.append("laptop-mac-test,120.0,65.0,42.0,55.0,80.0,95.0,1500,ac,120,2026-06-20 12:00:00\n") # Bad CPU (>100)
    lines.append("laptop-mac-test,50.0,150.0,42.0,55.0,80.0,95.0,1500,ac,120,2026-06-20 12:00:00\n") # Bad RAM
    lines.append("laptop-mac-test,50.0,65.0,42.0,180.0,80.0,95.0,1500,ac,120,2026-06-20 12:00:00\n") # Bad Temp (>150)
    
    return "".join(lines)

@patch("app.api.v1.telemetry.index_telemetry_in_vector_db")
def test_bulk_csv_upload_performance_and_validation(mock_index):
    """
    Test uploading 50,000+ telemetry rows.
    Verifies that the success criteria is met (50,000+ records imported without failure)
    and validation skips exactly 4 invalid rows.
    """
    num_rows = 50005
    csv_data = generate_mock_csv_content(num_rows)
    csv_file = io.BytesIO(csv_data.encode('utf-8'))
    
    start_time = time.time()
    
    response = client.post(
        "/api/v1/telemetry/upload",
        files={"file": ("test_telemetry.csv", csv_file, "text/csv")}
    )
    
    duration = time.time() - start_time
    
    assert response.status_code == 200
    res_json = response.json()
    
    assert res_json["status"] == "success"
    assert res_json["imported_count"] == num_rows
    assert res_json["skipped_count"] == 4
    assert len(res_json["errors"]) == 4 # Returns exactly the 4 skip errors we generated
    
    # Query database to confirm count
    db = TestingSessionLocal()
    count = db.query(TelemetryRecord).count()
    db.close()
    
    assert count == num_rows
    print(f"\nImported {count} records successfully in {duration:.2f} seconds.")
    # Ensure performance is high (e.g. 50,000 rows in less than 5 seconds in memory)
    assert duration < 5.0
