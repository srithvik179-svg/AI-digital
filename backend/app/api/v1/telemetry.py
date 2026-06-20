from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from typing import List, Dict
import json
import asyncio
from datetime import datetime

from app.core.database import get_db
from app.core.logging import logger
from app.models.telemetry import TelemetryRecord
from app.schemas.telemetry import TelemetryCreate, TelemetryResponse
from app.services.langchain_twin import index_telemetry_in_vector_db

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
                # Connection might be dead, but we will clean up in disconnect

manager = ConnectionManager()

@router.post("/", response_model=TelemetryResponse)
def create_telemetry(record: TelemetryCreate, db: Session = Depends(get_db)):
    """
    Ingest a new laptop telemetry record.
    Saves to PostgreSQL database, indexes in ChromaDB, and broadcasts to active websocket dashboard clients.
    """
    try:
        db_record = TelemetryRecord(
            device_id=record.device_id,
            timestamp=datetime.utcnow(),
            cpu_usage=record.cpu_usage,
            memory_usage=record.memory_usage,
            disk_usage=record.disk_usage,
            cpu_temperature=record.cpu_temperature,
            battery_level=record.battery_level,
            battery_health=record.battery_health,
            fan_speed=record.fan_speed,
            power_source=record.power_source,
            active_process_count=record.active_process_count,
            metadata_info=record.metadata_info
        )
        db.add(db_record)
        db.commit()
        db.refresh(db_record)
        
        # Index in Vector Database
        index_telemetry_in_vector_db(db_record)
        
        # Broadcast update to websocket clients
        response_data = TelemetryResponse.from_orm(db_record).dict()
        # Convert datetime to string for JSON serialization
        response_data["timestamp"] = response_data["timestamp"].isoformat()
        
        asyncio.create_task(manager.broadcast(json.dumps({
            "type": "telemetry_update",
            "data": response_data
        })))
        
        return db_record
    except Exception as e:
        logger.error(f"Error ingesting telemetry: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error ingesting telemetry")

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
        db.query(TelemetryRecord)
        .filter(TelemetryRecord.device_id == device_id)
        .order_by(TelemetryRecord.timestamp.desc())
        .limit(limit)
        .all()
    )
    return records

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time telemetry streaming and dashboard updates.
    """
    await manager.connect(websocket)
    try:
        while True:
            # Receive message from client if any
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Allow clients to request a start of mock telemetry generation
            if message.get("type") == "start_mock_stream":
                device_id = message.get("device_id", "laptop-mac-001")
                asyncio.create_task(generate_mock_stream(websocket, device_id))
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        manager.disconnect(websocket)

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
                    power_source = "battery" # Unplugged
            else:
                battery_level = max(0.0, battery_level - 0.2)
                if battery_level <= 15.0:
                    power_source = "ac" # Plugged in automatically
            
            mock_data = {
                "type": "telemetry_update",
                "data": {
                    "id": random.randint(1000, 9999),
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
                    "metadata_info": {"mock": True}
                }
            }
            
            # Send message to client
            await websocket.send_text(json.dumps(mock_data))
            
            # Sleep 2 seconds between ticks
            await asyncio.sleep(2)
    except Exception as e:
        logger.info(f"Stopped mock telemetry stream: {str(e)}")
