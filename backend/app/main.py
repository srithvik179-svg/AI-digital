from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.config import settings
from app.core.logging import logger
from app.core.database import engine, Base
from app.models.relationship import TelemetryRelationship
from app.models.reasoning import ReasoningRule
from app.api.v1.router import router as api_v1_router

# Initialize PostgreSQL database tables
try:
    logger.info("Initializing database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables initialized successfully.")
except Exception as e:
    logger.error(f"Error initializing database tables: {str(e)}")

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Backend API and AI Digital Twin reasoning system for Laptop Telemetry logging",
    version="1.0.0"
)

# Security hardening: parameterized CORS origins from environment variable
allowed_origins = [
    origin.strip()
    for origin in settings.ALLOWED_ORIGINS.split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Request-ID"],
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Inject security HTTP response headers on every response."""
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if not settings.DEBUG:
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
        return response


app.add_middleware(SecurityHeadersMiddleware)

# Include unified API router
app.include_router(api_v1_router, prefix=settings.API_V1_STR)

@app.get("/")
def read_root():
    """
    Base endpoint to check API name and description.
    """
    return {
        "project": settings.PROJECT_NAME,
        "description": "FastAPI service containing laptop analytics, RAG logic and WebSocket streams.",
        "docs_url": "/docs"
    }
