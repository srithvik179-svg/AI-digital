from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.ai_reasoning import AIReasoningStateResponse
from app.services.ai_reasoning.orchestrator import AIReasoningOrchestrator

router = APIRouter()
orchestrator = AIReasoningOrchestrator()

@router.get("/state/{device_id}", response_model=AIReasoningStateResponse, tags=["ai-reasoning"])
def get_ai_reasoning_state(device_id: str, db: Session = Depends(get_db)):
    """
    GET /api/v1/ai-reasoning/state/{device_id}
    Retrieves the complete AI reasoning and prediction state for a specific device,
    consolidating multi-factor states, scikit-learn models (decision trees, isolation forests),
    recursive gradient boosted regression, and failure forecasts with confidence bounds.
    """
    try:
        state = orchestrator.get_unified_reasoning_state(device_id, db)
        return state
    except ValueError as val_err:
        raise HTTPException(status_code=404, detail=str(val_err))
    except Exception as err:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal error compiling AI reasoning state: {str(err)}")
