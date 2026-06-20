from fastapi import APIRouter
from app.api.v1.telemetry import router as telemetry_router
from app.api.v1.twin import router as twin_router
from app.api.v1.health_score import router as health_score_router
from app.api.v1.alerts import router as alerts_router
from app.api.v1.summary import router as summary_router
from app.api.v1.chat import router as chat_router

router = APIRouter()

router.include_router(telemetry_router,    prefix="/telemetry",     tags=["telemetry"])
router.include_router(twin_router,         prefix="/twin",          tags=["digital-twin"])
router.include_router(health_score_router, prefix="/health-score",  tags=["health-score"])
router.include_router(alerts_router,       prefix="/alerts",        tags=["alerts"])
router.include_router(summary_router,      prefix="/summary",       tags=["summary"])
router.include_router(chat_router,         prefix="/chat",          tags=["chatbot"])

@router.get("/health", tags=["health"])
def health_check():
    """
    Health check endpoint for Kubernetes, Docker, or monitoring tools.
    """
    return {"status": "healthy", "version": "1.0.0"}
