from fastapi import APIRouter
from app.api.v1.telemetry import router as telemetry_router
from app.api.v1.twin import router as twin_router
from app.api.v1.health_score import router as health_score_router

router = APIRouter()

router.include_router(telemetry_router, prefix="/telemetry", tags=["telemetry"])
router.include_router(twin_router, prefix="/twin", tags=["digital-twin"])
router.include_router(health_score_router, prefix="/health-score", tags=["health-score"])

@router.get("/health", tags=["health"])
def health_check():
    """
    Health check endpoint for Kubernetes, Docker, or monitoring tools.
    """
    return {"status": "healthy", "version": "1.0.0"}
