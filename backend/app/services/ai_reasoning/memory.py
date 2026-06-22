"""
Session Memory Service — Phase 39.
Utilizes Redis connection caching with in-memory fallback to track chat history,
compress context with turn summarization, and limit context windows.
"""
import json
import redis
from typing import List, Dict, Optional, Any
from app.core.config import settings
from app.core.logging import logger

class SessionMemoryManager:
    def __init__(self, redis_url: str = settings.REDIS_URL, max_messages: int = 10):
        self.max_messages = max_messages
        self.use_redis = False
        self.redis_client = None
        self.local_memory: Dict[str, List[Dict[str, str]]] = {}
        self.local_summaries: Dict[str, str] = {}
        
        try:
            # Initialize Redis connection with a timeout
            self.redis_client = redis.Redis.from_url(redis_url, socket_timeout=1.0, decode_responses=True)
            self.redis_client.ping()
            self.use_redis = True
            logger.info("SessionMemoryManager successfully connected to Redis.")
        except Exception as e:
            logger.warning(f"SessionMemoryManager failed to connect to Redis: {e}. Falling back to in-memory caching.")
            self.use_redis = False

    def save_message(self, session_id: str, role: str, content: str) -> None:
        """Saves a message in the session history, maintaining a sliding window."""
        msg = {"role": role, "content": content}
        if self.use_redis:
            try:
                key = f"chat_history:{session_id}"
                raw = self.redis_client.get(key)
                history = json.loads(raw) if raw else []
                history.append(msg)
                # Apply sliding window
                if len(history) > self.max_messages:
                    history = history[-self.max_messages:]
                self.redis_client.set(key, json.dumps(history))
                return
            except Exception as e:
                logger.error(f"Redis save_message failed: {e}. Falling back to local memory.")
                
        # Local memory fallback
        if session_id not in self.local_memory:
            self.local_memory[session_id] = []
        history = self.local_memory[session_id]
        history.append(msg)
        if len(history) > self.max_messages:
            history = history[-self.max_messages:]
        self.local_memory[session_id] = history

    def get_history(self, session_id: str) -> List[Dict[str, str]]:
        """Retrieves session history messages."""
        if self.use_redis:
            try:
                key = f"chat_history:{session_id}"
                raw = self.redis_client.get(key)
                return json.loads(raw) if raw else []
            except Exception as e:
                logger.error(f"Redis get_history failed: {e}. Falling back to local memory.")
                
        return self.local_memory.get(session_id, [])

    def clear_session(self, session_id: str) -> None:
        """Clears session messages and summary."""
        if self.use_redis:
            try:
                self.redis_client.delete(f"chat_history:{session_id}")
                self.redis_client.delete(f"chat_summary:{session_id}")
                return
            except Exception as e:
                logger.error(f"Redis clear_session failed: {e}. Falling back to local memory.")
                
        self.local_memory.pop(session_id, None)
        self.local_summaries.pop(session_id, None)

    def get_summary(self, session_id: str) -> Optional[str]:
        """Retrieves session summary if it exists."""
        if self.use_redis:
            try:
                return self.redis_client.get(f"chat_summary:{session_id}")
            except Exception as e:
                logger.error(f"Redis get_summary failed: {e}. Falling back to local memory.")
                
        return self.local_summaries.get(session_id)

    def set_summary(self, session_id: str, summary: str) -> None:
        """Manually sets the session summary."""
        if self.use_redis:
            try:
                self.redis_client.set(f"chat_summary:{session_id}", summary)
                return
            except Exception as e:
                logger.error(f"Redis set_summary failed: {e}. Falling back to local memory.")
                
        self.local_summaries[session_id] = summary

    def summarize_session_if_needed(self, session_id: str, force: bool = False) -> Optional[str]:
        """
        Compresses conversation history if message count exceeds max_messages.
        Updates the session's summary and trims the message log.
        """
        history = self.get_history(session_id)
        if not force and len(history) < self.max_messages:
            return self.get_summary(session_id)
            
        # Compile text to summarize
        chat_text = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in history])
        
        summary = ""
        # Check if we are running in real LLM mode or mock mode
        if not settings.MOCK_LLM and settings.OPENAI_API_KEY != "mock_key":
            try:
                from langchain_openai import ChatOpenAI
                llm = ChatOpenAI(
                    model_name="gpt-4-turbo",
                    temperature=0.0,
                    openai_api_key=settings.OPENAI_API_KEY
                )
                prompt = (
                    f"Summarize the following chat history between a laptop user and an AI Digital Twin diagnostics copilot. "
                    f"Focus on the problems, queries, diagnostics, and action items discussed. Keep the summary under 3 sentences:\n\n"
                    f"{chat_text}\n\nSummary:"
                )
                summary = llm.predict(prompt).strip()
            except Exception as e:
                logger.error(f"Error in LLM summary generation: {e}. Falling back to local summarizer.")
                
        if not summary:
            # Deterministic local summary based on keywords
            problems = []
            if "cpu" in chat_text.lower():
                problems.append("CPU performance")
            if "temp" in chat_text.lower() or "heat" in chat_text.lower():
                problems.append("thermals")
            if "bat" in chat_text.lower():
                problems.append("battery state")
            if "disk" in chat_text.lower():
                problems.append("disk storage")
                
            problems_str = " and ".join(problems) if problems else "system metrics"
            summary = f"The conversation focused on diagnosing the laptop's {problems_str}."

        # Save summary
        self.set_summary(session_id, summary)
        
        # Trim history: keep only the last 2 messages (1 turn) to maintain immediate context
        trimmed_history = history[-2:] if len(history) >= 2 else history
        if self.use_redis:
            try:
                self.redis_client.set(f"chat_history:{session_id}", json.dumps(trimmed_history))
            except Exception as e:
                logger.error(f"Redis trim history failed: {e}")
        else:
            self.local_memory[session_id] = trimmed_history
            
        return summary

# Singleton memory manager
session_memory = SessionMemoryManager()
