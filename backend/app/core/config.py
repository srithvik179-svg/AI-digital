import os
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Digital Twin for Laptop Telemetry"
    API_V1_STR: str = "/api/v1"
    
    # Databases
    DATABASE_URL: str = Field(default="postgresql://postgres:postgres@localhost:5432/telemetry_db")
    REDIS_URL: str = Field(default="redis://localhost:6379/0")
    
    # ChromaDB (Vector store)
    CHROMA_HOST: str = Field(default="localhost")
    CHROMA_PORT: int = Field(default=8001)
    
    # AI Settings
    MOCK_LLM: bool = Field(default=True)
    OPENAI_API_KEY: str = Field(default="mock_key")
    
    # Logging
    LOG_LEVEL: str = Field(default="info")

    # Security
    DEBUG: bool = Field(default=True, description="Disable in production to enable HSTS and stricter policies.")
    ALLOWED_ORIGINS: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000",
        description="Comma-separated list of allowed CORS origins."
    )

    class Config:
        case_sensitive = True
        env_file = ".env"

settings = Settings()
