"""
AI Copilot API Router — Phase 40.
Exposes /chat, /validate-query, /explain, and chat-history endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.logging import logger
from app.schemas.copilot import (
    CopilotChatRequest,
    CopilotChatResponse,
    QueryValidationRequest,
    QueryValidationResponse
)
from app.services.ai_reasoning.copilot import run_copilot_session
from app.services.ai_reasoning.guardrails import validate_input
from app.services.ai_reasoning.memory import session_memory
from app.services.ai_reasoning.explainable_ai import explain_prediction

router = APIRouter()

@router.post("/chat", response_model=CopilotChatResponse)
def copilot_chat(
    payload: CopilotChatRequest,
    db: Session = Depends(get_db)
):
    """
    Unified Copilot chat agent. Runs guardrails, loads history, executes RAG, computes attributions,
    checks and executes triggers, and saves message logs.
    """
    try:
        result = run_copilot_session(
            session_id=payload.session_id,
            device_id=payload.device_id,
            query=payload.query,
            personality=payload.personality,
            db_session=db
        )
        return CopilotChatResponse(**result)
    except Exception as e:
        logger.error(f"Error executing copilot session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/validate-query", response_model=QueryValidationResponse)
def validate_query(payload: QueryValidationRequest):
    """
    Validates a query against prompt/SQL injection and checks if it's in-scope.
    """
    try:
        status = validate_input(payload.query)
        return QueryValidationResponse(is_valid=status.is_valid, reason=status.reason)
    except Exception as e:
        logger.error(f"Error validating query: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/explain/{device_id}")
def explain_prediction_attributions(
    device_id: str,
    db: Session = Depends(get_db)
):
    """
    Returns feature attributions (Explainable AI weights) explaining predictions and health score.
    """
    try:
        return explain_prediction(device_id, db)
    except Exception as e:
        logger.error(f"Error fetching explainability attributions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/chat-history/{session_id}")
def get_chat_history(session_id: str):
    """
    Retrieves the stored chat history messages for a session.
    """
    try:
        return session_memory.get_history(session_id)
    except Exception as e:
        logger.error(f"Error fetching chat history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/chat-history/{session_id}")
def clear_chat_history(session_id: str):
    """
    Clears the stored chat history and summaries for a session.
    """
    try:
        session_memory.clear_session(session_id)
        return {"status": "success", "message": f"Session memory cleared for {session_id}"}
    except Exception as e:
        logger.error(f"Error clearing chat history: {e}")
        raise HTTPException(status_code=500, detail=str(e))
