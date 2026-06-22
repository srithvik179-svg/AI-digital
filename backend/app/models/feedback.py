"""
Adaptive Learning Feedback Model.
Stores user ratings (thumbs up/down) for chatbot answers,
recommendations, and RCA diagnoses to enable future model improvement.
"""
from sqlalchemy import Column, String, Integer, Float, DateTime, Text, Enum
from datetime import datetime
import enum
import uuid
from app.core.database import Base


class FeedbackType(str, enum.Enum):
    chatbot = "chatbot"
    recommendation = "recommendation"
    rca = "rca"
    prediction = "prediction"


class RecommendationFeedback(Base):
    __tablename__ = "recommendation_feedback"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    device_id = Column(String, nullable=False, index=True)
    feedback_type = Column(Enum(FeedbackType), nullable=False, index=True)
    rating = Column(Integer, nullable=False)           # +1 = helpful, -1 = not helpful
    query_text = Column(Text, nullable=True)           # The user question (for chatbot)
    response_text = Column(Text, nullable=True)        # The AI answer (for chatbot)
    recommendation_id = Column(String, nullable=True)  # Recommendation or RCA ID
    comments = Column(Text, nullable=True)
    confidence_at_time = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
