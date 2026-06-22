"""
Unit tests for Phase 32 Telemetry Embeddings Service.
"""
import pytest
import numpy as np
from app.services.ai_reasoning.embeddings import telemetry_embeddings

def test_embed_query_dimension():
    """Ensure query embeddings return the standard 1536 dimensions."""
    query = "What is the CPU usage?"
    embedding = telemetry_embeddings.embed_query(query)
    assert isinstance(embedding, list)
    assert len(embedding) == 1536
    # Verify values are floats
    assert all(isinstance(x, float) for x in embedding)

def test_embed_documents_batching():
    """Ensure embedding multiple documents returns a list of lists of correct dimensions."""
    docs = [
        "CPU load is 45% at 2026-06-20 12:00:00",
        "Battery is charging at 2026-06-20 12:05:00"
    ]
    embeddings = telemetry_embeddings.embed_documents(docs)
    assert isinstance(embeddings, list)
    assert len(embeddings) == 2
    assert len(embeddings[0]) == 1536
    assert len(embeddings[1]) == 1536

def test_mock_semantic_similarity():
    """Ensure similar texts are closer in cosine similarity than completely unrelated texts."""
    text1 = "high CPU usage alert"
    text2 = "high CPU load warning"
    text3 = "battery low WiFi signal"
    
    vec1 = np.array(telemetry_embeddings.embed_query(text1))
    vec2 = np.array(telemetry_embeddings.embed_query(text2))
    vec3 = np.array(telemetry_embeddings.embed_query(text3))
    
    # Cosine similarities
    sim_similar = np.dot(vec1, vec2)
    sim_unrelated = np.dot(vec1, vec3)
    
    # Assert that similar texts have higher cosine similarity than unrelated texts
    assert sim_similar > sim_unrelated
