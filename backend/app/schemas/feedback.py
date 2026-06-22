"""
Pydantic schemas for the Adaptive Learning Feedback API.
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class FeedbackSubmit(BaseModel):
    device_id: str = Field(..., description="Device identifier")
    feedback_type: str = Field(..., description="Type: chatbot | recommendation | rca | prediction")
    rating: int = Field(..., ge=-1, le=1, description="+1 = helpful, -1 = not helpful")
    query_text: Optional[str] = Field(default=None, description="The user's original query")
    response_text: Optional[str] = Field(default=None, description="The AI-generated response")
    recommendation_id: Optional[str] = Field(default=None, description="ID of the rated recommendation or RCA")
    comments: Optional[str] = Field(default=None, description="Optional free-text feedback")
    confidence_at_time: Optional[float] = Field(default=None, description="Confidence score of the response at rating time")


class FeedbackResponse(BaseModel):
    id: str
    device_id: str
    feedback_type: str
    rating: int
    query_text: Optional[str] = None
    recommendation_id: Optional[str] = None
    comments: Optional[str] = None
    confidence_at_time: Optional[float] = None
    created_at: datetime

    class Config:
        from_attributes = True


class FeedbackStats(BaseModel):
    total_ratings: int
    helpful_count: int
    not_helpful_count: int
    helpfulness_ratio: float
    by_type: dict
