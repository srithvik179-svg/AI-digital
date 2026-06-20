from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, File, UploadFile
from sqlalchemy.orm import Session, joinedload
from typing import List, Dict, Any
import json
import codecs
import csv
import asyncio
from datetime import datetime
import uuid

from app.core.database import get_db
from app.core.logging import logger
from app.models.telemetry import (
    TelemetrySnapshot,
    CPUMetrics,
    GPUMetrics,
    MemoryMetrics,
    BatteryMetrics,
    DiskMetrics,
    WiFiMetrics,
    ThermalMetrics,
    PowerMetrics
)
from app.schemas.telemetry import TelemetryCreate, TelemetryResponse
from app.services.langchain_twin import index_telemetry_in_vector_db
from app.services.ingestion import (
    resolve_headers,
    clean_and_validate_row,
    bulk_insert_normalized_telemetry
)

router = APIRouter()

# Connection Manager for WebSockets
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"New client connected. Total active connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"Client disconnected. Total active connections: {len(self.active_connections)}")

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Error broadcasting to client: {str(e)}")

manager = ConnectionManager()

def flatten_snapshot(snapshot: TelemetrySnapshot) -> Dict[str, Any]:
    """
    Helper function to flatten a TelemetrySnapshot model and its related entities
    into a dictionary structure matching TelemetryResponse.
    """
    return {
        "id": snapshot.id,
        "device_id": snapshot.device_id,
        "timestamp": snapshot.timestamp,
        
        # Core performance metrics
        "cpu_usage": snapshot.cpu.cpu_usage if snapshot.cpu else 0.0,
        "memory_usage": snapshot.memory.memory_usage if snapshot.memory else 0.0,
        "disk_usage": snapshot.disk.disk_usage if snapshot.disk else 0.0,
        
        # Thermal and power metrics
        "cpu_temperature": snapshot.thermal.cpu_temperature if snapshot.thermal else 0.0,
        "battery_level": snapshot.battery.battery_level if snapshot.battery else 0.0,
        "battery_health": snapshot.battery.battery_health if snapshot.battery else 0.0,
        "fan_speed": snapshot.thermal.fan_speed_rpm if snapshot.thermal else 0,
        
        # Status and environment metrics
        "power_source": snapshot.power.power_source if snapshot.power else "ac",
        "active_process_count": snapshot.cpu.active_process_count if snapshot.cpu else 0,
        
        # Extended metrics
        "cpu_frequency_mhz": snapshot.cpu.cpu_frequency_mhz if snapshot.cpu else None,
        "gpu_usage": snapshot.gpu.gpu_usage if snapshot.gpu else None,
        "gpu_temperature": snapshot.gpu.gpu_temperature if snapshot.gpu else None,
        "gpu_memory_usage": snapshot.gpu.gpu_memory_usage if snapshot.gpu else None,
        "battery_temperature": snapshot.battery.battery_temperature if snapshot.battery else None,
        "cycle_count": snapshot.battery.cycle_count if snapshot.battery else None,
        "read_bytes_sec": snapshot.disk.read_bytes_sec if snapshot.disk else None,
        "write_bytes_sec": snapshot.disk.write_bytes_sec if snapshot.disk else None,
        "signal_strength_dbm": snapshot.wifi.signal_strength_dbm if snapshot.wifi else None,
        "ssid": snapshot.wifi.ssid if snapshot.wifi else None,
        "link_speed_mbps": snapshot.wifi.link_speed_mbps if snapshot.wifi else None,
        "thermal_state": snapshot.thermal.thermal_state if snapshot.thermal else None,
        "power_draw_watts": snapshot.power.power_draw_watts if snapshot.power else None,
        "voltage_mv": snapshot.power.voltage_mv if snapshot.power else None,
    }

@router.post("/", response_model=TelemetryResponse)
async def create_telemetry(record: TelemetryCreate, db: Session = Depends(get_db)):
    """
    Ingest a new laptop telemetry record.
    Saves to PostgreSQL database, indexes in ChromaDB, and broadcasts to active websocket dashboard clients.
    """
    try:
        # Convert record schema to dict
        record_dict = record.dict()
        
        # Insert into normalized database tables
        snapshot_ids = bulk_insert_normalized_telemetry(db, [record_dict])
        db.commit()
        snapshot_id = snapshot_ids[0]
        
        # Retrieve the newly created snapshot joined with all entities
        db_snapshot = (
            db.query(TelemetrySnapshot)
            .options(
                joinedload(TelemetrySnapshot.cpu),
                joinedload(TelemetrySnapshot.gpu),
                joinedload(TelemetrySnapshot.memory),
                joinedload(TelemetrySnapshot.battery),
                joinedload(TelemetrySnapshot.disk),
                joinedload(TelemetrySnapshot.wifi),
                joinedload(TelemetrySnapshot.thermal),
                joinedload(TelemetrySnapshot.power)
            )
            .filter(TelemetrySnapshot.id == snapshot_id)
            .first()
        )
        
        # Index in Vector Database
        index_telemetry_in_vector_db(db_snapshot)
        
        # Broadcast update to websocket clients
        response_data = flatten_snapshot(db_snapshot)
        # Convert datetime to string for JSON serialization
        response_data_json = response_data.copy()
        response_data_json["timestamp"] = response_data_json["timestamp"].isoformat()
        
        await manager.broadcast(json.dumps({
            "type": "telemetry_update",
            "data": response_data_json
        }))
        
        return response_data
    except Exception as e:
        logger.error(f"Error ingesting telemetry: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error ingesting telemetry")


@router.post("/upload")
async def upload_telemetry_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload a CSV file containing laptop telemetry data.
    Validates, parses and bulk-inserts rows into PostgreSQL in batches of 5000.
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are supported.")
        
    try:
        # Stream reader to process line-by-line
        csv_reader = csv.DictReader(codecs.getreader("utf-8")(file.file))
        
        if not csv_reader.fieldnames:
            raise HTTPException(status_code=400, detail="Empty CSV file or missing headers.")
            
        header_mapping = resolve_headers(csv_reader.fieldnames)
        
        # Ensure we found at least some headers
        if not header_mapping:
            raise HTTPException(
                status_code=400, 
                detail="Could not map any headers to the expected telemetry schema. Check columns names."
            )
            
        logger.info(f"Resolved CSV headers: {header_mapping}")
        
        batch = []
        imported_count = 0
        skipped_count = 0
        errors = []
        
        BATCH_SIZE = 5000
        vector_index_interval = 50 # Index 1 in 50 records to prevent Chroma overload
        vector_batch = []
        
        for idx, raw_row in enumerate(csv_reader):
            cleaned, err = clean_and_validate_row(raw_row, header_mapping)
            if cleaned is None:
                skipped_count += 1
                if len(errors) < 10:
                    errors.append(f"Row {idx+2}: {err}")
                continue
                
            batch.append(cleaned)
            
            # Select subset for vector store
            if idx % vector_index_interval == 0:
                vector_batch.append(cleaned)
            
            if len(batch) >= BATCH_SIZE:
                # Bulk insert into DB
                bulk_insert_normalized_telemetry(db, batch)
                db.commit()
                imported_count += len(batch)
                batch.clear()
                
        # Insert remaining rows in final batch
        if batch:
            bulk_insert_normalized_telemetry(db, batch)
            db.commit()
            imported_count += len(batch)
            batch.clear()
            
        # Index subset of telemetry records in ChromaDB in batches
        if vector_batch:
            try:
                for item in vector_batch:
                    index_telemetry_in_vector_db(item)
                logger.info(f"Indexed {len(vector_batch)} summary records in ChromaDB.")
            except Exception as e:
                logger.error(f"Failed to bulk-index RAG context in ChromaDB: {str(e)}")
                
        return {
            "status": "success",
            "imported_count": imported_count,
            "skipped_count": skipped_count,
            "errors": errors
        }
        
    except Exception as e:
        logger.error(f"Error importing CSV: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"CSV Import failed: {str(e)}")


@router.get("/", response_model=List[TelemetryResponse])
def get_telemetry(
    device_id: str,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """
    Retrieve historical telemetry records for a specific device, sorted by timestamp descending.
    """
    records = (
        db.query(TelemetrySnapshot)
        .options(
            joinedload(TelemetrySnapshot.cpu),
            joinedload(TelemetrySnapshot.gpu),
            joinedload(TelemetrySnapshot.memory),
            joinedload(TelemetrySnapshot.battery),
            joinedload(TelemetrySnapshot.disk),
            joinedload(TelemetrySnapshot.wifi),
            joinedload(TelemetrySnapshot.thermal),
            joinedload(TelemetrySnapshot.power)
        )
        .filter(TelemetrySnapshot.device_id == device_id)
        .order_by(TelemetrySnapshot.timestamp.desc())
        .limit(limit)
        .all()
    )
    
    return [flatten_snapshot(r) for r in records]


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time telemetry streaming and dashboard updates.
    """
    await manager.connect(websocket)
    mock_task = None
    try:
        while True:
            # Receive message from client if any
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Allow clients to request a start of mock telemetry generation
            if message.get("type") == "start_mock_stream":
                device_id = message.get("device_id", "laptop-mac-001")
                if mock_task and not mock_task.done():
                    mock_task.cancel()
                mock_task = asyncio.create_task(generate_mock_stream(websocket, device_id))
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        if mock_task and not mock_task.done():
            mock_task.cancel()
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        manager.disconnect(websocket)
        if mock_task and not mock_task.done():
            mock_task.cancel()


async def generate_mock_stream(websocket: WebSocket, device_id: str):
    """
    A helper loop to generate mock laptop telemetry logs and stream them to the dashboard.
    Allows local testing and demoing without physical laptop agents.
    """
    import random
    logger.info(f"Starting mock telemetry stream for {device_id}")
    
    # Starting conditions
    cpu_temp = 48.0
    fan_speed = 1200
    battery_level = 90.0
    power_source = "ac"
    
    try:
        while True:
            # Random variations to simulate real usage
            cpu_usage = round(random.uniform(5.0, 95.0), 1)
            memory_usage = round(random.uniform(40.0, 85.0), 1)
            disk_usage = 42.4
            
            # Temp increases as CPU usage increases
            temp_delta = (cpu_usage / 10.0) - 3.0
            cpu_temp = max(40.0, min(95.0, round(cpu_temp + temp_delta + random.uniform(-1.0, 1.0), 1)))
            
            # Fans spin faster as temperature increases
            if cpu_temp > 70:
                fan_speed = min(5500, fan_speed + random.randint(100, 300))
            elif cpu_temp < 50:
                fan_speed = max(1000, fan_speed - random.randint(50, 150))
            else:
                fan_speed = max(1200, min(3000, fan_speed + random.randint(-50, 50)))
                
            # Simulate battery discharging/charging
            if power_source == "ac":
                battery_level = min(100.0, battery_level + 0.1)
                if battery_level >= 100.0 and random.random() < 0.05:
                    power_source = "battery"
            else:
                battery_level = max(0.0, battery_level - 0.2)
                if battery_level <= 15.0:
                    power_source = "ac"
            
            # Form standard telemetry dict matching TelemetryResponse
            mock_data = {
                "type": "telemetry_update",
                "data": {
                    "id": str(uuid.uuid4()),
                    "device_id": device_id,
                    "timestamp": datetime.utcnow().isoformat(),
                    
                    "cpu_usage": cpu_usage,
                    "memory_usage": memory_usage,
                    "disk_usage": disk_usage,
                    
                    "cpu_temperature": cpu_temp,
                    "battery_level": round(battery_level, 1),
                    "battery_health": 94.0,
                    "fan_speed": fan_speed,
                    
                    "power_source": power_source,
                    "active_process_count": random.randint(90, 140),
                    
                    # Extended mock fields
                    "cpu_frequency_mhz": 2800.0 + random.uniform(-400.0, 400.0),
                    "gpu_usage": round(random.uniform(0.0, 30.0), 1),
                    "gpu_temperature": max(35.0, cpu_temp - 5.0),
                    "gpu_memory_usage": round(random.uniform(5.0, 20.0), 1),
                    "battery_temperature": round(random.uniform(28.0, 35.0), 1),
                    "cycle_count": 142,
                    "read_bytes_sec": random.randint(1000, 500000),
                    "write_bytes_sec": random.randint(500, 200000),
                    "signal_strength_dbm": random.randint(-75, -40),
                    "ssid": "Dell_Secure_WiFi",
                    "link_speed_mbps": 866,
                    "thermal_state": "nominal" if cpu_temp < 75 else "serious",
                    "power_draw_watts": round(random.uniform(5.0, 25.0), 1),
                    "voltage_mv": 11800.0 + random.uniform(-200.0, 200.0)
                }
            }
            
            # Send message to client
            await websocket.send_text(json.dumps(mock_data))
            
            # Sleep 2 seconds between ticks
            await asyncio.sleep(2)
    except asyncio.CancelledError:
        logger.info(f"Cancelled mock telemetry stream for {device_id}")
    except Exception as e:
        logger.info(f"Stopped mock telemetry stream: {str(e)}")
