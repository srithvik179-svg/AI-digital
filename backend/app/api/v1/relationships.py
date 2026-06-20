from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any
from app.core.database import get_db
from app.core.logging import logger
from app.services.relationship_mapper import map_and_store_relationships

router = APIRouter()

@router.get("", response_model=Dict[str, Any])
def get_telemetry_relationships(
    device_id: str,
    db: Session = Depends(get_db)
):
    """
    Get the telemetry dependency and relationship graph for a laptop.
    Computes Pearson correlation coefficients dynamically from database logs and saves findings.
    """
    try:
        logger.info(f"Computing telemetry relationship map for device '{device_id}'")
        graph = map_and_store_relationships(device_id=device_id, db_session=db)
        return graph
    except Exception as e:
        logger.error(f"Failed to compute relationships: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to compute telemetry relationships: {str(e)}"
        )
