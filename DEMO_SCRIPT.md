# Demo Script — AI Digital Twin for Laptop Telemetry
## Dell AI Challenge · Phase 53 Final Presentation

**Estimated Duration**: 12–15 minutes  
**Audience**: Technical judges / Product stakeholders  
**System State**: Backend + Frontend running (`docker compose up -d`)

---

## Pre-Demo Checklist

- [ ] `docker compose up -d` — all 6 services healthy
- [ ] Browser open at http://localhost:3000
- [ ] Sample CSV ready: `backend/app/tests/sample_telemetry.csv`
- [ ] Terminal open for live log viewing: `docker compose logs -f backend`

---

## Act 1 · Landing Page (1 min)

**Narrative**: *"The system presents two isolated intelligence modules — Historical Telemetry Analysis powered by CSV data, and a Live AI Digital Twin powered by real-time sensors."*

1. Open http://localhost:3000
2. Point out the two module cards: **Historical Telemetry Intelligence** and **Live AI Digital Twin**
3. Explain the strict data isolation: historical dashboards never show live telemetry and vice-versa.

---

## Act 2 · Historical Telemetry Intelligence (4 min)

**Narrative**: *"Let's analyze a week of historical sensor data to understand past patterns and anomalies."*

### Step 1 — Upload CSV
1. Click **"Historical Telemetry Intelligence"**
2. Upload `backend/app/tests/sample_telemetry.csv`
3. Wait for ingestion confirmation toast

### Step 2 — Dashboard Overview
1. Navigate to the **Dashboard** tab
2. Point out:
   - **CPU Trend** — time-series graph from CSV records only
   - **Temperature** — thermal envelope over time
   - **Battery SoH** — health degradation curve
   - **Health Score** — composite AI-computed score
3. Say: *"Every data point on these graphs traces directly to a CSV record — no synthetic or live data ever contaminates historical analysis."*

### Step 3 — Anomaly & Alert Review
1. Click the **Alerts** tab
2. Show a critical temperature spike alert
3. Click **Root Cause Analysis** — display the causal chain graph
4. Say: *"The system identified the anomaly, traced the root cause to sustained CPU load during a specific time window, and generated an evidence-backed explanation — not a hallucination."*

### Step 4 — Correlation Analysis
1. Open the **Correlation** tab
2. Show the CPU ↔ Temperature correlation heatmap
3. Point out high-correlation pairs and their evidence source

### Step 5 — Knowledge Graph
1. Open **Knowledge Graph**
2. Zoom in on the causal node cluster
3. Say: *"The knowledge graph maps causal relationships between telemetry metrics, not just correlations."*

---

## Act 3 · AI Copilot — Evidence-Driven Chat (3 min)

**Narrative**: *"The chatbot is our key differentiator — it never invents facts."*

### Demo Questions (type each, show response)

| Question | Expected Behavior |
|----------|------------------|
| "What is the average CPU usage?" | Retrieves CSV aggregate, cites rows |
| "Why did the laptop overheat on day 3?" | Root Cause Analysis — traces to CPU load spike, evidence cited |
| "How healthy is this laptop?" | Health Assessment — composite score with metric breakdown |
| "What are your top 3 recommendations?" | Evidence-backed prioritized actions |
| "What happens if CPU reaches 95% for 2 hours?" | Simulation result — no hallucination |

1. Type first question, show answer with **Evidence Panel** expanded
2. Point out: *"Every answer cites the exact telemetry records it used. If the data doesn't support an answer, the system says so."*
3. Click **👍 Helpful** — demonstrate adaptive learning feedback recorded
4. Check `GET /api/v1/feedback/stats` in a new tab — show the rating logged

---

## Act 4 · Live AI Digital Twin (3 min)

**Narrative**: *"Now let's switch to the live module — monitoring the actual laptop in real time."*

1. Return to landing page, click **"Live AI Digital Twin"**
2. Show the **Live Dashboard** with real-time gauges (psutil data)
3. Open the **Digital Twin 3D View** — the animated laptop model
4. Show the **Live Prediction** panel: 30-day failure risk forecast
5. Open **What-If Simulation**: drag CPU load to 95%, show simulated thermal response
6. Say: *"The simulation model is grounded in the physics of the telemetry — it models how the system would actually behave."*

---

## Act 5 · Explainable AI & Predictions (1 min)

1. Click a prediction card to open the **Explainability Panel**
2. Show feature importance chart (which sensors drove the prediction)
3. Say: *"Every prediction is explained — judges and operators can understand why the model flagged a risk."*

---

## Act 6 · Production Readiness (1 min)

**Narrative**: *"This is production-grade, not a prototype."*

Open a terminal and run:

```bash
# Show all services are healthy
docker compose ps

# Show metrics endpoint
curl http://localhost:8000/api/v1/metrics/ | python3 -m json.tool

# Show Prometheus-format metrics
curl http://localhost:8000/api/v1/metrics/prometheus

# Show CI/CD pipeline YAML
cat .github/workflows/ci-cd.yml | head -40
```

Say: *"GitHub Actions runs lint, test, and Docker push on every commit. The production compose enforces network isolation, no-new-privileges, and read-only root filesystems."*

---

## Closing (30 sec)

> *"The AI Digital Twin for Laptop Telemetry solves all five Dell Challenge objectives:*
> *Diagnostics, Root Cause Analysis, Evidence-Driven Recommendations, What-If Simulation, Failure Prediction — all with Explainable AI and Minimal Hallucination.*
> *Historical and Live data are strictly isolated. Every answer is evidence-backed.*
> *It's containerized, monitored, CI/CD-ready, and production-hardened."*

---

## Key URLs

| URL | Description |
|-----|-------------|
| http://localhost:3000 | Frontend |
| http://localhost:8000/docs | Backend Swagger UI |
| http://localhost:8000/api/v1/health | Health check |
| http://localhost:8000/api/v1/metrics/ | JSON metrics |
| http://localhost:8000/api/v1/metrics/prometheus | Prometheus metrics |
| http://localhost:8000/api/v1/feedback/stats | Feedback analytics |
