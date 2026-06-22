"""
Adaptive Learning Feedback API Router.
Receives user ratings for chatbot, recommendations, and RCA results.
Stores votes to PostgreSQL for future model improvement analytics.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from datetime import datetime

from app.core.database import get_db
from app.core.logging import logger
from app.models.feedback import RecommendationFeedback
from app.schemas.feedback import FeedbackSubmit, FeedbackResponse, FeedbackStats

router = APIRouter()


@router.post("/submit", response_model=FeedbackResponse, status_code=201)
def submit_feedback(payload: FeedbackSubmit, db: Session = Depends(get_db)):
    """
    Submit a thumbs-up (+1) or thumbs-down (-1) rating for an AI response.
    Records chatbot answers, recommendations, RCA diagnoses, or predictions.
    """
    try:
        VALID_TYPES = {"chatbot", "recommendation", "rca", "prediction"}
        if payload.feedback_type not in VALID_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid feedback_type. Must be one of: {VALID_TYPES}"
            )
        if payload.rating not in (-1, 1):
            raise HTTPException(
                status_code=400,
                detail="Rating must be exactly +1 (helpful) or -1 (not helpful)."
            )

        record = RecommendationFeedback(
            device_id=payload.device_id,
            feedback_type=payload.feedback_type,
            rating=payload.rating,
            query_text=payload.query_text,
            response_text=payload.response_text,
            recommendation_id=payload.recommendation_id,
            comments=payload.comments,
            confidence_at_time=payload.confidence_at_time,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        logger.info(
            f"Feedback recorded: device={payload.device_id} "
            f"type={payload.feedback_type} rating={payload.rating}"
        )
        return record
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error recording feedback: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to save feedback.")


@router.get("/stats", response_model=FeedbackStats)
def get_feedback_stats(device_id: str = None, db: Session = Depends(get_db)):
    """
    Aggregate feedback statistics. Optionally filter by device_id.
    Returns total ratings, helpfulness ratio, and breakdown per feedback type.
    """
    try:
        query = db.query(RecommendationFeedback)
        if device_id:
            query = query.filter(RecommendationFeedback.device_id == device_id)

        records = query.all()
        total = len(records)
        helpful = sum(1 for r in records if r.rating == 1)
        not_helpful = sum(1 for r in records if r.rating == -1)
        ratio = round(helpful / total, 3) if total > 0 else 0.0

        # Breakdown by type
        by_type: dict = {}
        for fb_type in ["chatbot", "recommendation", "rca", "prediction"]:
            type_records = [r for r in records if r.feedback_type == fb_type]
            type_helpful = sum(1 for r in type_records if r.rating == 1)
            by_type[fb_type] = {
                "total": len(type_records),
                "helpful": type_helpful,
                "not_helpful": len(type_records) - type_helpful,
                "ratio": round(type_helpful / len(type_records), 3) if type_records else 0.0,
            }

        return FeedbackStats(
            total_ratings=total,
            helpful_count=helpful,
            not_helpful_count=not_helpful,
            helpfulness_ratio=ratio,
            by_type=by_type,
        )
    except Exception as e:
        logger.error(f"Error fetching feedback stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve feedback statistics.")


@router.get("/recent", response_model=List[FeedbackResponse])
def get_recent_feedback(
    device_id: str = None,
    feedback_type: str = None,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    """
    Retrieve recent feedback entries. Optionally filter by device_id and feedback_type.
    """
    query = db.query(RecommendationFeedback).order_by(
        RecommendationFeedback.created_at.desc()
    )
    if device_id:
        query = query.filter(RecommendationFeedback.device_id == device_id)
    if feedback_type:
        query = query.filter(RecommendationFeedback.feedback_type == feedback_type)
    return query.limit(limit).all()
