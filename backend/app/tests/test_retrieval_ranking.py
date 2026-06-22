"""
Unit tests for Phase 33 Retrieval Ranking Service.
"""
import pytest
from app.services.ai_reasoning.retrieval_ranking import (
    tokenize,
    BM25Retriever,
    reciprocal_rank_fusion,
    hybrid_retrieve_and_rank
)

def test_tokenize():
    """Ensure tokenize removes punctuation and returns lowercase words."""
    text = "Battery level is low! (At 12:00)."
    tokens = tokenize(text)
    assert tokens == ["battery", "level", "is", "low", "at", "12", "00"]

def test_bm25_retriever_ranking():
    """Ensure BM25 scores exact matches higher than unrelated docs."""
    docs = [
        "CPU load is very high and cores are overheating",
        "Battery charging level is normal and stable",
        "WiFi speed is fast and latency is low"
    ]
    retriever = BM25Retriever(docs)
    
    # Query matching CPU doc
    cpu_scores = retriever.score("overheating CPU cores")
    assert cpu_scores[0] > cpu_scores[1]
    assert cpu_scores[0] > cpu_scores[2]
    
    # Query matching battery doc
    bat_scores = retriever.score("charging battery level")
    assert bat_scores[1] > bat_scores[0]
    assert bat_scores[1] > bat_scores[2]

def test_reciprocal_rank_fusion():
    """Ensure RRF scores rank items according to consensus rank."""
    vector_ranks = ["docA", "docB", "docC"]
    bm25_ranks = ["docB", "docA", "docD"]
    
    fused = reciprocal_rank_fusion(vector_ranks, bm25_ranks)
    # docA is rank 1 (vector) and rank 2 (bm25) -> RRF: 1/(60+1) + 1/(60+2)
    # docB is rank 2 (vector) and rank 1 (bm25) -> RRF: 1/(60+2) + 1/(60+1)
    # docA and docB should have the highest scores (tied)
    fused_docs = [item[0] for item in fused]
    assert "docA" in fused_docs[:2]
    assert "docB" in fused_docs[:2]
    assert fused_docs[3] == "docD" or fused_docs[2] == "docC"
