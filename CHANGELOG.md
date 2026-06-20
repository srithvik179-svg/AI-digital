# Changelog

All notable changes to the Dell AI Digital Twin project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-06-20

### Added
- **CSV Ingestion Route**: Added `POST /api/v1/telemetry/upload` endpoint in FastAPI supporting multipart upload.
- **Validation Pipeline**: Created ingestion service (`app/services/ingestion.py`) parsing telemetry fields, normalizing headers via aliases, checking bounds, and interpolating missing variables.
- **Bulk Data Handling**: Bulk inserted logs into PostgreSQL in batches of 5,000 to process huge sets efficiently.
- **AI Vector Store Batching**: Buffered and batched ChromaDB vector embeddings for 1 in 50 rows to protect ChromaDB against performance lags during bulk uploads.
- **Test Automation**: Wrote integration performance test (`app/tests/test_ingestion.py`) uploading 50,000+ mock records and verifying import speed (<1.5s in memory).

## [1.0.0] - 2026-06-20

### Added
- **Docker Compose**: Orchestration config coordinating postgres, redis, chromadb, fastapi, and next.js containers.
- **FastAPI Backend**:
  - Pydantic Settings, database engine session mapping, and custom logging middleware.
  - Telemetry database schema and ingestion routes.
  - WebSockets telemetry stream with built-in mock telemetry simulator.
  - LangChain RAG pipeline with ChromaDB integration supporting mock/production LLMs.
  - Versioned routing under prefix `/api/v1`.
- **Next.js Frontend**:
  - TypeScript interfaces, Tailwind styling, and custom glassmorphism effects.
  - Real-time WebSockets telemetry subscription handler.
  - Telemetry charts (utilization & thermals) built via Recharts.
  - TwinStatus analytics panels.
  - Interactive AI Twin Chat consult interface.
- **Repository Guidelines**: Created standard `README.md`, `CHANGELOG.md`, and `PROJECT_STATUS.md`.
