from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.core.logging import logger
from app.schemas.telemetry import TelemetryResponse
from app.services.search_engine import search_telemetry_records
from app.api.v1.telemetry import flatten_snapshot

router = APIRouter()

@router.get("", response_model=List[TelemetryResponse])
def get_telemetry_search(
    device_id: str,
    query: str,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """
    Search telemetry records for a device using natural language queries.
    Retrieves and flattens matching snapshots.
    """
    try:
        logger.info(f"Searching telemetry for device '{device_id}' with NL query: '{query}'")
        snapshots = search_telemetry_records(
            device_id=device_id,
            query=query,
            db_session=db,
            limit=limit
        )
        return [flatten_snapshot(s) for s in snapshots]
    except Exception as e:
        logger.error(f"Error performing telemetry search: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to search telemetry: {str(e)}")
