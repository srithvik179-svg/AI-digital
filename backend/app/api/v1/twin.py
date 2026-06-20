from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.logging import logger
from app.schemas.telemetry import TwinQuery, TwinResponse
from app.services.langchain_twin import query_digital_twin

router = APIRouter()

@router.post("/query", response_model=TwinResponse)
def query_twin_agent(
    payload: TwinQuery,
    db: Session = Depends(get_db)
):
    """
    Query the AI Digital Twin for laptop diagnostics and analytics.
    Retrieves latest data from PostgreSQL, retrieves matching vectors from ChromaDB,
    and runs a LangChain chain (or local mock agent) to explain findings.
    """
    try:
        logger.info(f"Querying digital twin for device '{payload.device_id}' with question: '{payload.query}'")
        result = query_digital_twin(
            device_id=payload.device_id,
            query=payload.query,
            db_session=db
        )
        return TwinResponse(
            query=payload.query,
            response=result["response"],
            source_documents=result["source_documents"]
        )
    except Exception as e:
        logger.error(f"Error querying AI Digital Twin: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to query AI Digital Twin: {str(e)}")
