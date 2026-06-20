# Changelog

All notable changes to the Dell AI Digital Twin project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
