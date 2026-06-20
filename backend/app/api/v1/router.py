from fastapi import APIRouter
from app.api.v1.telemetry import router as telemetry_router
from app.api.v1.twin import router as twin_router
from app.api.v1.health_score import router as health_score_router
from app.api.v1.alerts import router as alerts_router
from app.api.v1.summary import router as summary_router
from app.api.v1.chat import router as chat_router
from app.api.v1.search import router as search_router
from app.api.v1.twin_state import router as twin_state_router
from app.api.v1.relationships import router as relationships_router
from app.api.v1.knowledge_graph import router as knowledge_graph_router
from app.api.v1.reasoning import router as reasoning_router
from app.api.v1.rca import router as rca_router
from app.api.v1.ai_reasoning import router as ai_reasoning_router

router = APIRouter()

router.include_router(telemetry_router,    prefix="/telemetry",     tags=["telemetry"])
router.include_router(twin_router,         prefix="/twin",          tags=["digital-twin"])
router.include_router(health_score_router, prefix="/health-score",  tags=["health-score"])
router.include_router(alerts_router,       prefix="/alerts",        tags=["alerts"])
router.include_router(summary_router,      prefix="/summary",       tags=["summary"])
router.include_router(chat_router,         prefix="/chat",          tags=["chatbot"])
router.include_router(search_router,       prefix="/search",        tags=["search"])
router.include_router(twin_state_router,  prefix="/twin-state",    tags=["digital-twin-core-model"])
router.include_router(relationships_router,prefix="/relationships", tags=["relationships-mapper"])
router.include_router(knowledge_graph_router, prefix="/knowledge-graph", tags=["knowledge-graph"])
router.include_router(reasoning_router,       prefix="/reasoning",       tags=["reasoning"])
router.include_router(rca_router,             prefix="/rca",             tags=["rca"])
router.include_router(ai_reasoning_router,    prefix="/ai-reasoning",    tags=["ai-reasoning"])

@router.get("/health", tags=["health"])
def health_check():
    """
    Health check endpoint for Kubernetes, Docker, or monitoring tools.
    """
    return {"status": "healthy", "version": "1.0.0"}

