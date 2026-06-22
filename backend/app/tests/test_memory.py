"""
Unit tests for Phase 39 Session Memory Service.
"""
import pytest
from app.services.ai_reasoning.memory import SessionMemoryManager

def test_local_memory_fallback():
    """Ensure saving and loading messages works using in-memory local caching when Redis is unavailable."""
    # We pass a bogus Redis URL to trigger the fallback
    manager = SessionMemoryManager(redis_url="redis://localhost:9999/0")
    assert manager.use_redis is False
    
    session_id = "test-session-123"
    
    # Save messages
    manager.save_message(session_id, "user", "Hello Digital Twin")
    manager.save_message(session_id, "assistant", "Hello! How can I help you?")
    
    # Retrieve messages
    history = manager.get_history(session_id)
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "Hello Digital Twin"
    assert history[1]["role"] == "assistant"

def test_sliding_window_limit():
    """Ensure message log is capped at max_messages length."""
    manager = SessionMemoryManager(redis_url="redis://localhost:9999/0", max_messages=4)
    session_id = "test-session-456"
    
    for i in range(6):
        manager.save_message(session_id, "user", f"Msg {i}")
        
    history = manager.get_history(session_id)
    assert len(history) == 4
    # The oldest messages (0, 1) should have been discarded
    assert history[0]["content"] == "Msg 2"
    assert history[3]["content"] == "Msg 5"

def test_clear_session():
    """Ensure clear_session removes history and summaries."""
    manager = SessionMemoryManager(redis_url="redis://localhost:9999/0")
    session_id = "test-session-789"
    
    manager.save_message(session_id, "user", "Message to delete")
    manager.set_summary(session_id, "Summary to delete")
    
    assert len(manager.get_history(session_id)) == 1
    assert manager.get_summary(session_id) == "Summary to delete"
    
    manager.clear_session(session_id)
    assert len(manager.get_history(session_id)) == 0
    assert manager.get_summary(session_id) is None

def test_summarization_trigger():
    """Ensure summarize_session_if_needed compresses history and trims it to 2 messages."""
    manager = SessionMemoryManager(redis_url="redis://localhost:9999/0", max_messages=4)
    session_id = "test-session-summarize"
    
    manager.save_message(session_id, "user", "How is the CPU temperature?")
    manager.save_message(session_id, "assistant", "It is 85C.")
    manager.save_message(session_id, "user", "Is my battery low?")
    manager.save_message(session_id, "assistant", "Battery level is 15%.")
    
    # 4 messages in history
    assert len(manager.get_history(session_id)) == 4
    
    # Summarize should trigger because message length == max_messages
    summary = manager.summarize_session_if_needed(session_id)
    assert summary is not None
    assert "thermals" in summary.lower() or "battery" in summary.lower() or "diagnosing" in summary.lower()
    
    # Summary should be saved
    assert manager.get_summary(session_id) == summary
    
    # Chat history should be trimmed to the last 2 messages (1 turn)
    history = manager.get_history(session_id)
    assert len(history) == 2
    assert history[0]["content"] == "Is my battery low?"
    assert history[1]["content"] == "Battery level is 15%."
