# Changelog

All notable changes to the Laptop Telemetry Digital Twin project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.6.0] - 2026-06-20

### Added
- **Digital Twin Core Model (`services/digital_twin_model.py`)**: Object-oriented simulator engine modeling CPU, GPU, RAM, Battery, Disk, WiFi, and Thermal using thermodynamic rules.
- **Relationship Mapper (`services/relationship_mapper.py`)**: Dynamic Pearson and Spearman correlation engine calculating hardware dependencies and saving them to PostgreSQL.
- **Statistical Correlation API (`relationships.py`)**: Added `/relationships/matrix` endpoint for $8 \times 8$ Pearson and Spearman matrices.
- **Correlation Matrix Heatmap UI (`CorrelationDashboard.tsx`)**: Heatmap dashboard grid with positive/negative color gradients, method toggles, and detail tooltips.
- **Test Automation**: Added unit tests for digital twin simulation (`test_twin_model.py`), relationship mapping (`test_relationship_mapper.py`), and Spearman/Pearson matrices (`test_correlation_matrix.py`).

## [1.5.0] - 2026-06-20

### Added
- **Natural Language Search (`services/search_engine.py`)**: Implemented search engine compiling natural language inputs (e.g. *"Show battery drain events"*) to SQL database filters.
- **Search Router (`search.py`)**: Added `GET /api/v1/search` endpoint.
- **Search UI Panel (`TelemetrySearch.tsx`)**: Created search card with template suggestions, results table, and expandable telemetry snapshot detail cards.
- **MVP Production Build**: Tested and validated full Next.js production build (`next build`) compilation without warnings/errors.
- **Search Test Suite**: Added 12 unit tests in `test_search.py` verifying parsing filters and logical operators.

## [1.4.0] - 2026-06-20

### Added
- **Natural Language Summary Engine (`services/summary_engine.py`)**: Built pure-Python template summary generator compiling snapshot metrics to paragraphs, headlines, and bullet points in < 0.03 ms.
- **Summary API Router (`summary.py`)**: Added `/summary/generate` endpoint.
- **Telemetry Chatbot (`services/chatbot_engine.py`)**: Built a deterministic, rule-based chatbot answering CPU, GPU, battery, and disk telemetry questions strictly from data snapshots.
- **Chat Router (`chat.py`)**: Added `/chat/query` endpoint.
- **Summary Banner UI (`SummaryCard.tsx`)**: Integrated typewriter-animated summary banner on frontend.
- **Test Automation**: Added 26 tests for summary engine and 8 tests for chatbot engine.

## [1.3.0] - 2026-06-20

### Added
- **Laptop Health Score Engine (`services/health_score.py`)**: Designed a 7-component scoring engine returning 0-100 score and categories (Healthy, Warning, Critical) with recommendation cards.
- **Health API Router (`health_score.py`)**: Added compute, latest, history, and summary endpoints.
- **Alert Detection Engine (`services/alert_engine.py`)**: Created rule-based anomaly detector containing 16 rules across overheating, battery, disk, and network categories with severity suppression.
- **Alert API Router (`alerts.py`)**: Added compute, active, history, acknowledge, and global feed endpoints.
- **Health score HUD UI (`TwinStatus.tsx`)**: Integrated animated SVG arc health score gauge and 7-component breakdown bars.
- **Alerts Panel UI (`AlertsPanel.tsx`)**: Added grouped alerts view with acknowledge toggles.
- **Test Automation**: Added 13 tests for health scoring and 27 tests for alert engine.

## [1.2.0] - 2026-06-20

### Added
- **Database Schema Normalization**: Split single telemetry table into 9 tables (snapshots + 8 metrics categories) with indexes.
- **Recharts Dashboard (`TelemetryCharts.tsx`)**: Upgraded charts UI into a 5-panel real-time Recharts grid covering CPU/Mem, GPU, Temperature, Battery, and WiFi.

## [1.1.0] - 2026-06-20

### Added
- **CSV Ingestion Route**: Added `POST /api/v1/telemetry/upload` endpoint in FastAPI supporting multipart upload.
- **Validation Pipeline**: Created ingestion service (`app/services/ingestion.py`) parsing telemetry fields, normalizing headers via aliases, checking bounds, and interpolating missing variables.
- **Bulk Data Handling**: Bulk inserted logs into PostgreSQL in batches of 5,000 to process huge sets efficiently.
- **AI Vector Store Batching**: Buffered and batched ChromaDB vector embeddings for 1 in 50 rows.
- **Test Automation**: Wrote integration performance test (`app/tests/test_ingestion.py`) uploading 50,000+ mock records and verifying import speed.

### Fixed
- **WebSocket URL**: Corrected the WebSocket connection path configuration to point to `/api/v1/telemetry/ws` instead of `/api/v1/ws`.

## [1.0.0] - 2026-06-20

### Added
- **Docker Compose**: Orchestration config coordinating postgres, redis, chromadb, fastapi, and next.js containers.
- **FastAPI Backend**: Versioned routing under `/api/v1` with RAG, database engine mappings, WebSockets streams, and logging middleware.
- **Next.js Frontend**: Custom glassmorphism Tailwind styling with WebSockets subscriber and Recharts components.
- **Daemon**: Local macOS metrics collection agent script.
