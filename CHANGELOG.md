# Changelog

All notable changes to the Laptop Telemetry Digital Twin project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.13.0] - 2026-06-22

### Added
- **Monolithic Architecture Split**: Restructured the TwinIntel portal into two isolated modules:
  - **Historical Telemetry Intelligence**: For examining uploaded CSV datasets, PostgreSQL history logs, statistical correlation matrix heatmaps, dependency topology flowcharts, custom rules engines, and Neo4j graph nodes.
  - **Live AI Digital Twin**: For real-time monitoring via 3D Three.js thermal models, WMI/psutil stream pipelines, and multi-device fleet views.
- **Isolated Navigation**: Built a glassmorphic Landing Page portal allowing users to explicitly select their active workspace.
- **Tabbed Live Twin Workspace**: Structured live telemetry into three operational tabs:
  - **Current State**: Displays live metrics (CPU, GPU, RAM, Temp, Fan, Battery, WiFi, Health Score), 3D laptop models, live charts, and fleet dashboards.
  - **Prediction**: Displays 7 & 30-day degradation forecasts (LSTM, XGBoost, Prophet future models).
  - **What-If Simulation**: Mounts steady-state simulation sliders and time-travel scenario projections.
- **Data Isolated Chatbots**: Added mode parameter routing (`historical` vs `live`) to query endpoints. The chatbots do not share context, and enforce strict queries limits (historical chatbot blocks predictions/simulations/live states; live chatbot blocks historical trends/correlations/root causes).

## [1.12.0] - 2026-06-22

### Added
- **Evidence-Driven Chatbot (Phase 50)**: Architected a strict 10-step chatbot pipeline compiling classification, Postgres retrievals, deterministic rules, root-cause heuristics, predictive models, and steady-state simulation math.
- **Post-Generation Hallucination Guard**: Cross-verifies output answer claims against structured evidence logs, blocking ungrounded numerical claims and filtering banned terms (dust, thermal paste, hardware defects).
- **Test Automation**: Added 22 unit and integration tests in `test_evidence_chatbot.py` and `test_hallucination_guard.py`, reaching 387 total backend tests.

## [1.11.0] - 2026-06-20

### Added
- **ChromaDB Vector Store RAG Ingestion**: Integrated ChromaDB for indexing and semantic query retrieval of telemetry logs.
- **Strict Grounded Response System**:
  - **OpenAI GPT Mode**: Implemented strict prompt templates for ChatOpenAI (GPT-4-turbo) forcing zero hallucinations, context-locked answers, and source timestamp citations.
  - **Local Grounded Cognitive Solver**: Created a local parsing engine fallback for offline mode matching metric keywords against retrieved context, extracting values, and compiling replies citing telemetry timestamps.
  - **Grounded Refusal Safeguard**: Guaranteed strict refusal response (*"I cannot find evidence in the telemetry logs to answer this question."*) for out-of-scope or missing telemetry.
- **PostgreSQL Fallback Synchronization**: Implemented automatic database retrieval and ChromaDB indexing sync if the vector DB is offline or empty.
- **Refactored APIs**: Updated `/chat/query` and `/twin/query` endpoints to utilize `query_digital_twin` from the RAG engine.
- **Test Automation**: Refactored `test_chatbot.py` unit tests to target the new RAG engine, adding a clean Chroma autouse isolation fixture.

## [1.10.0] - 2026-06-20

### Added
- **Rule-Based Reasoning Engine**: Designed custom condition evaluation operators and logic connectors (AND/OR) inside a dynamic Rule Editor dashboard component (`ReasoningEngine.tsx`).
- **Root Cause Analysis (RCA) Engine**: Integrated analytical RCA service (`services/rca_engine.py`) using Heuristic Decision Trees and relationship correlation weights causal traversal, accompanied by an interactive troubleshooting UI panel (`RootCauseAnalysis.tsx`).
- **AI Predictive Analytics**: Developed multi-factor system stress indexes, autoregressive time-series forecasting with confidence bounds, Isolation Forest anomaly ratings, and RUL Weibull degradation models in a unified `AIReasoningDashboard.tsx` component.
- **Test Automation**: Added unit tests for reasoning engine (`test_reasoning_engine.py`), RCA engine (`test_rca_engine.py`), and predictive analytics (`test_ai_reasoning.py`), reaching 141 backend tests.

## [1.9.0] - 2026-06-20

### Added
- **Dynamic Step-by-Step Simulation**: Integrated mathematical equations for thermodynamic dissipation, active fan speed ramping, clock throttling, battery CC/CV charging, cycle count increments, and disk writes in `VirtualLaptop`.
- **WebSocket State Updates**: Propagated live twin states (`twin_state`) in real-time JSON packets during mock streams and real daemon ingest ticks.
- **Historical Playback API**: Added `/replay` route retrieving chronological snapshots and tracking wear increments sequentially.
- **What-If Branch Projections API**: Added `/what-if` scenario planner running multi-step projections starting from specific historical timestamps.
- **ReplayConsole HUD Component**: Built a media playback card (`ReplayConsole.tsx`) with play/pause/stop, seek progress bar, speed rates, and history limits.
- **Time Travel Scenario Planner Component**: Built scenario configuration card (`TimeTravelPlayground.tsx`) overlaying future dashed paths on CPU temp, battery, and CPU load panels.
- **Unit Tests**: Added 4 unit tests in `test_twin_simulation_replay.py` validating thermodynamic calculations, battery cycles, replay streams, and what-if timesteps.

## [1.8.0] - 2026-06-20

### Added
- **Neo4j Graph Database**: Provisioned a Neo4j community database container in Docker Compose with health checks and data volumes.
- **Knowledge Graph Sync Service (`services/knowledge_graph.py`)**: Developed Postgres-to-Neo4j data synchronizer writing telemetry node properties and directed `INFLUENCES` relationships.
- **Neo4j API Router (`knowledge_graph.py`)**: Added query and sync endpoints, restricting query execution to read-only Cypher transactions.
- **Cypher Explorer Terminal (`KnowledgeGraphExplorer.tsx`)**: Created interactive playground on frontend that executes Cypher queries, renders nodes in an SVG circle layout, and reveals raw JSON results.
- **Knowledge Graph Tests**: Added 4 unit tests in `test_knowledge_graph.py` verifying driver mocking, sync logic, Cypher result formatting, and read-only validation.

## [1.7.0] - 2026-06-20

### Added
- **Dependency Graph UI (`DependencyGraph.tsx`)**: Created interactive directed topology visualization in SVG with animated flow pathways mapping hardware telemetry interactions.
- **Dynamic Causal Inspector**: Integrated node/edge selections highlighting focused paths and updating a detailed sidebar inspect panel with causal explanations.
- **Analytics Layout Grid**: Redesigned page.tsx to place the correlation matrix heatmap and hardware dependency graph side-by-side.

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
