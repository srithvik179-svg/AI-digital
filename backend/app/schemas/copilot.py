"""
Pydantic Schemas for Phase 40 AI Copilot.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class CopilotChatRequest(BaseModel):
    session_id: str = Field(..., example="session-user-123")
    device_id: str = Field(..., example="laptop-mac-001")
    query: str = Field(..., example="Engage Eco Mode for me please.")
    personality: Optional[str] = Field(default="diagnostic_engineer", example="eco_assistant")

class CopilotChatResponse(BaseModel):
    query: str
    response: str
    source_documents: List[str] = []
    evidence: List[Dict[str, Any]] = []
    steps: List[Dict[str, Any]] = []
    explainability_attributions: Dict[str, Any] = {}
    action_triggered: Optional[str] = None

class QueryValidationRequest(BaseModel):
    query: str = Field(..., example="Engage Eco Mode.")

class QueryValidationResponse(BaseModel):
    is_valid: bool
    reason: Optional[str] = None
