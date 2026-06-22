from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.logging import logger
from app.schemas.telemetry import ChatQuery, ChatResponse
from app.services.evidence_chatbot import query_evidence_chatbot

router = APIRouter()

@router.post("/query", response_model=ChatResponse)
def query_chatbot(
    payload: ChatQuery,
    db: Session = Depends(get_db)
):
    """
    Query the telemetry chatbot.
    Retrieves the latest telemetry snapshot for CPU, GPU, Battery, and Disk and answers using RAG engine.
    """
    try:
        logger.info(f"Querying chatbot for device '{payload.device_id}' with question: '{payload.query}'")
        result = query_evidence_chatbot(
            device_id=payload.device_id,
            query=payload.query,
            db_session=db,
            mode=payload.mode
        )
        return ChatResponse(
            query=payload.query,
            response=result["response"],
            source_documents=result["source_documents"]
        )
    except Exception as e:
        logger.error(f"Error querying telemetry chatbot: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to query telemetry chatbot: {str(e)}")
