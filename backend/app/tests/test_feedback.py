"""
Unit tests for the Adaptive Learning Feedback API.
Uses a minimal FastAPI app with only the feedback router to avoid importing
the full application stack (which requires Docker services like ChromaDB/Neo4j).
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.database import Base, get_db
from app.models.feedback import RecommendationFeedback  # ensure table is created
from app.api.v1.feedback import router as feedback_router

# ── Isolated test app (no langchain_classic, no chromadb) ─────────────
test_app = FastAPI()
test_app.include_router(feedback_router, prefix="/api/v1/feedback")

SQLALCHEMY_DATABASE_URL = "sqlite:///./test_feedback_isolated.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


test_app.dependency_overrides[get_db] = override_get_db
client = TestClient(test_app)

DEVICE_ID = "test-device-001"


@pytest.fixture(autouse=True)
def clean_db():
    """Wipe feedback table between tests."""
    yield
    db = TestingSessionLocal()
    try:
        db.execute(text("DELETE FROM recommendation_feedback"))
        db.commit()
    except Exception:
        pass
    finally:
        db.close()


# ═══════════════════════════════════════════════════════════
# Tests: Submit
# ═══════════════════════════════════════════════════════════
class TestFeedbackSubmit:
    def test_submit_helpful_chatbot_feedback(self):
        resp = client.post("/api/v1/feedback/submit", json={
            "device_id": DEVICE_ID,
            "feedback_type": "chatbot",
            "rating": 1,
            "query_text": "What is my CPU usage?",
            "response_text": "Your CPU usage is 55%.",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["rating"] == 1
        assert data["feedback_type"] == "chatbot"

    def test_submit_not_helpful_recommendation(self):
        resp = client.post("/api/v1/feedback/submit", json={
            "device_id": DEVICE_ID,
            "feedback_type": "recommendation",
            "rating": -1,
            "recommendation_id": "rec-001",
            "comments": "Suggestion was not actionable.",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["rating"] == -1
        assert data["comments"] == "Suggestion was not actionable."

    def test_submit_rca_feedback(self):
        resp = client.post("/api/v1/feedback/submit", json={
            "device_id": DEVICE_ID,
            "feedback_type": "rca",
            "rating": 1,
            "confidence_at_time": 0.88,
        })
        assert resp.status_code == 201

    def test_submit_prediction_feedback(self):
        resp = client.post("/api/v1/feedback/submit", json={
            "device_id": DEVICE_ID,
            "feedback_type": "prediction",
            "rating": 1,
        })
        assert resp.status_code == 201

    def test_invalid_rating_too_high_rejected(self):
        resp = client.post("/api/v1/feedback/submit", json={
            "device_id": DEVICE_ID,
            "feedback_type": "chatbot",
            "rating": 5,
        })
        # Pydantic ge=-1, le=1 validation fails → 422
        assert resp.status_code == 422

    def test_invalid_rating_too_low_rejected(self):
        resp = client.post("/api/v1/feedback/submit", json={
            "device_id": DEVICE_ID,
            "feedback_type": "chatbot",
            "rating": -5,
        })
        assert resp.status_code == 422

    def test_invalid_feedback_type_rejected(self):
        resp = client.post("/api/v1/feedback/submit", json={
            "device_id": DEVICE_ID,
            "feedback_type": "unknown_type",
            "rating": 1,
        })
        assert resp.status_code == 400

    def test_response_contains_id_and_created_at(self):
        resp = client.post("/api/v1/feedback/submit", json={
            "device_id": DEVICE_ID,
            "feedback_type": "chatbot",
            "rating": 1,
        })
        data = resp.json()
        assert "id" in data
        assert "created_at" in data


# ═══════════════════════════════════════════════════════════
# Tests: Stats
# ═══════════════════════════════════════════════════════════
class TestFeedbackStats:
    def _seed(self):
        for fb_type, rating in [
            ("chatbot", 1), ("chatbot", 1), ("chatbot", -1),
            ("recommendation", 1), ("rca", -1), ("prediction", 1),
        ]:
            client.post("/api/v1/feedback/submit", json={
                "device_id": DEVICE_ID,
                "feedback_type": fb_type,
                "rating": rating,
            })

    def test_stats_aggregation(self):
        self._seed()
        resp = client.get("/api/v1/feedback/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_ratings"] == 6
        assert data["helpful_count"] == 4
        assert data["not_helpful_count"] == 2
        assert abs(data["helpfulness_ratio"] - round(4 / 6, 3)) < 0.01

    def test_stats_per_type(self):
        self._seed()
        resp = client.get("/api/v1/feedback/stats")
        data = resp.json()
        chatbot_stats = data["by_type"]["chatbot"]
        assert chatbot_stats["total"] == 3
        assert chatbot_stats["helpful"] == 2
        assert chatbot_stats["not_helpful"] == 1

    def test_stats_device_filter(self):
        self._seed()
        resp = client.get(f"/api/v1/feedback/stats?device_id={DEVICE_ID}")
        assert resp.status_code == 200
        assert resp.json()["total_ratings"] == 6

    def test_stats_empty_returns_zero(self):
        resp = client.get("/api/v1/feedback/stats")
        assert resp.status_code == 200
        assert resp.json()["total_ratings"] == 0
        assert resp.json()["helpfulness_ratio"] == 0.0

    def test_stats_prediction_type_present(self):
        self._seed()
        data = client.get("/api/v1/feedback/stats").json()
        assert "prediction" in data["by_type"]


# ═══════════════════════════════════════════════════════════
# Tests: Recent
# ═══════════════════════════════════════════════════════════
class TestFeedbackRecent:
    def test_recent_list(self):
        for _ in range(3):
            client.post("/api/v1/feedback/submit", json={
                "device_id": DEVICE_ID,
                "feedback_type": "chatbot",
                "rating": 1,
            })
        resp = client.get("/api/v1/feedback/recent")
        assert resp.status_code == 200
        assert len(resp.json()) == 3

    def test_recent_filter_by_type(self):
        client.post("/api/v1/feedback/submit", json={
            "device_id": DEVICE_ID, "feedback_type": "chatbot", "rating": 1,
        })
        client.post("/api/v1/feedback/submit", json={
            "device_id": DEVICE_ID, "feedback_type": "rca", "rating": -1,
        })
        resp = client.get("/api/v1/feedback/recent?feedback_type=rca")
        assert resp.status_code == 200
        assert all(r["feedback_type"] == "rca" for r in resp.json())

    def test_recent_limit_respected(self):
        for _ in range(10):
            client.post("/api/v1/feedback/submit", json={
                "device_id": DEVICE_ID,
                "feedback_type": "chatbot",
                "rating": 1,
            })
        resp = client.get("/api/v1/feedback/recent?limit=5")
        assert resp.status_code == 200
        assert len(resp.json()) == 5
