# Deployment Guide — AI Digital Twin for Laptop Telemetry

## Prerequisites

| Tool | Version |
|------|---------|
| Docker | ≥ 24 |
| Docker Compose | ≥ 2.20 |
| Git | ≥ 2.40 |

---

## Environment Setup

Create a `.env` file in the project root:

```dotenv
# ── PostgreSQL ──────────────────────────
POSTGRES_USER=postgres
POSTGRES_PASSWORD=<strong-password>
POSTGRES_DB=telemetry_db

# ── Redis ───────────────────────────────
REDIS_PASSWORD=<strong-redis-password>

# ── Neo4j ───────────────────────────────
NEO4J_USER=neo4j
NEO4J_PASSWORD=<strong-neo4j-password>

# ── AI ──────────────────────────────────
OPENAI_API_KEY=<your-openai-api-key>
MOCK_LLM=false

# ── Security ────────────────────────────
ALLOWED_ORIGINS=https://your-domain.com
DEBUG=false

# ── Frontend ────────────────────────────
API_BASE_URL=https://api.your-domain.com
NEXT_PUBLIC_API_BASE_URL=https://api.your-domain.com
```

---

## Development (local)

```bash
# Start all services with hot-reload
docker compose up -d

# View backend logs
docker compose logs -f backend

# Run backend unit tests
cd backend && pip install -r requirements.txt
pytest app/tests/ -v

# Run frontend dev server
cd frontend && npm install && npm run dev
```

Access:
- **Frontend**: http://localhost:3000
- **Backend API docs**: http://localhost:8000/docs
- **Backend metrics**: http://localhost:8000/api/v1/metrics/

---

## Production Deployment

```bash
# Build and start all production services
docker compose -f docker-compose.prod.yml up -d --build

# Check service health
docker compose -f docker-compose.prod.yml ps

# Run database migrations
docker compose -f docker-compose.prod.yml exec backend \
  python -c "from app.core.database import engine, Base; Base.metadata.create_all(engine)"

# Stream production logs
docker compose -f docker-compose.prod.yml logs -f backend frontend
```

---

## Database Migrations

SQL migrations live in `backend/migrations/` and are automatically applied on container startup via `docker-entrypoint-initdb.d`.

To apply manually:
```bash
docker compose exec db psql -U postgres -d telemetry_db \
  -f /docker-entrypoint-initdb.d/V7__adaptive_learning.sql
```

---

## Monitoring

| Endpoint | Description |
|----------|-------------|
| `GET /api/v1/health` | Service liveness check |
| `GET /api/v1/metrics/` | JSON operational metrics |
| `GET /api/v1/metrics/prometheus` | Prometheus-format metrics |

### Prometheus Scrape Configuration

Add to `prometheus.yml`:
```yaml
scrape_configs:
  - job_name: telemetry-twin-backend
    scrape_interval: 30s
    static_configs:
      - targets: ['backend:8000']
    metrics_path: /api/v1/metrics/prometheus
```

---

## Scaling

```bash
# Scale backend workers
docker compose -f docker-compose.prod.yml up -d --scale backend=3
```

> Ensure Nginx upstream `backend` includes all replicas for load balancing.

---

## Backup & Restore

```bash
# Backup PostgreSQL
docker compose exec db pg_dump -U postgres telemetry_db | gzip > backup_$(date +%Y%m%d).sql.gz

# Restore
gunzip -c backup_20260622.sql.gz | docker compose exec -T db psql -U postgres telemetry_db

# Backup Neo4j
docker compose exec neo4j neo4j-admin database dump neo4j --to-path=/backups/
```

---

## CI/CD Pipeline

The GitHub Actions workflow at `.github/workflows/ci-cd.yml` automatically:

1. **On every push / PR**:
   - Runs backend pytest suite with PostgreSQL service container
   - Lints Python code with flake8
   - Builds Next.js frontend and checks for compilation errors

2. **On push to `develop`**:
   - Builds Docker images and pushes to GitHub Container Registry (GHCR)
   - Deploys to staging environment

3. **On push to `main`**:
   - Builds Docker images and pushes with `latest` tag
   - Deploys to production environment

---

## Troubleshooting

| Problem | Resolution |
|---------|-----------|
| Backend fails to start | Check `DATABASE_URL` is reachable; run `docker compose logs db` |
| Frontend can't reach API | Verify `NEXT_PUBLIC_API_BASE_URL` and CORS `ALLOWED_ORIGINS` match |
| Neo4j authentication error | Confirm `NEO4J_PASSWORD` in `.env` matches Neo4j initialization |
| ChromaDB connection refused | Ensure `CHROMA_HOST=chromadb` and port 8000 is not blocked |
| Metrics endpoint 500 | DB tables may not be initialized; run migration step above |
