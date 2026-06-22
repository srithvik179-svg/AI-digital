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
from app.api.v1.copilot import router as copilot_router
from app.api.v1.what_if import router as what_if_router
from app.api.v1.future_state import router as future_state_router
from app.api.v1.live_stream import router as live_stream_router
from app.api.v1.fleet import router as fleet_router
from app.api.v1.executive import router as executive_router
from app.api.v1.feedback import router as feedback_router
from app.api.v1.metrics import router as metrics_router

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
router.include_router(copilot_router,         prefix="/copilot",         tags=["copilot"])
router.include_router(what_if_router,         prefix="/what-if-simulation", tags=["what-if-simulation"])
router.include_router(future_state_router,    prefix="/future-state",       tags=["future-state"])
router.include_router(live_stream_router,     prefix="/live-stream",        tags=["live-stream"])
router.include_router(fleet_router,           prefix="/fleet",              tags=["fleet"])
router.include_router(executive_router,       prefix="/executive",          tags=["executive"])
router.include_router(feedback_router,        prefix="/feedback",            tags=["adaptive-learning"])
router.include_router(metrics_router,         prefix="/metrics",             tags=["monitoring"])

@router.get("/health", tags=["health"])
def health_check():
    """
    Health check endpoint for Kubernetes, Docker, or monitoring tools.
    """
    return {"status": "healthy", "version": "1.0.0"}

