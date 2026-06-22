"""
Unified Telemetry Embeddings Service — Phase 32.
Provides OpenAIEmbeddings and a local, offline deterministic embedding fallback.
"""
from typing import List
import numpy as np
import hashlib
from langchain_openai import OpenAIEmbeddings
from app.core.config import settings
from app.core.logging import logger

class TelemetryEmbeddings:
    """
    A unified embedding class for telemetry RAG context.
    Uses OpenAI in production and a local character-hash vectorizer in offline/mock mode.
    """
    def __init__(self):
        self.mock_mode = settings.MOCK_LLM or settings.OPENAI_API_KEY == "mock_key"
        self._openai_embeddings = None
        if not self.mock_mode:
            try:
                self._openai_embeddings = OpenAIEmbeddings(
                    openai_api_key=settings.OPENAI_API_KEY
                )
                logger.info("OpenAIEmbeddings initialized successfully.")
            except Exception as e:
                logger.warning(f"Failed to init OpenAIEmbeddings: {e}. Falling back to Local Mock Embeddings.")
                self.mock_mode = True

    def _get_local_embedding(self, text: str) -> List[float]:
        """
        Generate a deterministic 1536-dimensional embedding based on string contents.
        Uses MD5 hashing to distribute frequencies evenly for mock vector similarity.
        """
        vector = np.zeros(1536)
        words = text.lower().split()
        for idx, word in enumerate(words):
            # Compute a hash of the word to determine vector coordinates
            h = hashlib.md5(word.encode("utf-8")).digest()
            for b_idx, byte in enumerate(h):
                coord = (idx * len(h) + b_idx) % 1536
                # Add positive/negative components based on byte parity
                val = float(byte) / 255.0
                if byte % 2 == 0:
                    vector[coord] += val
                else:
                    vector[coord] -= val
        
        # Add L2 normalization
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm
        else:
            # Prevent zero vector
            vector[0] = 1.0
        return vector.tolist()

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of telemetry document strings."""
        if not self.mock_mode and self._openai_embeddings:
            try:
                return self._openai_embeddings.embed_documents(texts)
            except Exception as e:
                logger.error(f"OpenAI embed_documents error: {e}. Falling back to local.")
        return [self._get_local_embedding(t) for t in texts]

    def embed_query(self, text: str) -> List[float]:
        """Embed a user query string."""
        if not self.mock_mode and self._openai_embeddings:
            try:
                return self._openai_embeddings.embed_query(text)
            except Exception as e:
                logger.error(f"OpenAI embed_query error: {e}. Falling back to local.")
        return self._get_local_embedding(text)

# Singleton Instance
telemetry_embeddings = TelemetryEmbeddings()
