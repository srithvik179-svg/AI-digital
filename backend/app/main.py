from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.logging import logger
from app.core.database import engine, Base
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

# Set up CORS middleware
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "*"  # In development, allow all. In production, lock this down.
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
