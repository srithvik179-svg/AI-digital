"""
Retrieval & Re-ranking Service — Phase 33.
Implements BM25 keyword search, vector rank retrieval, and Reciprocal Rank Fusion (RRF) re-ranking.
"""
import math
import re
from typing import List, Dict, Any, Tuple
from app.core.logging import logger

def tokenize(text: str) -> List[str]:
    """Tokenize text into lowercase words, stripping punctuation."""
    return re.findall(r'\b\w+\b', text.lower())

class BM25Retriever:
    """Pure Python BM25 Retriever for document ranking."""
    def __init__(self, documents: List[str], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.documents = documents
        self.corpus_size = len(documents)
        self.avg_doc_len = 0.0
        self.doc_lengths = []
        self.doc_term_freqs = []
        self.doc_freqs = {}
        
        self._initialize()

    def _initialize(self):
        total_len = 0
        for doc in self.documents:
            tokens = tokenize(doc)
            self.doc_lengths.append(len(tokens))
            total_len += len(tokens)
            
            # Count term frequencies in this document
            tf = {}
            for token in tokens:
                tf[token] = tf.get(token, 0) + 1
            self.doc_term_freqs.append(tf)
            
            # Count document frequencies
            for token in tf.keys():
                self.doc_freqs[token] = self.doc_freqs.get(token, 0) + 1
                
        if self.corpus_size > 0:
            self.avg_doc_len = total_len / self.corpus_size

    def _idf(self, term: str) -> float:
        df = self.doc_freqs.get(term, 0)
        # Standard BM25 IDF with smoothing
        return math.log(1.0 + (self.corpus_size - df + 0.5) / (df + 0.5))

    def score(self, query: str) -> List[float]:
        query_tokens = tokenize(query)
        scores = []
        for idx in range(self.corpus_size):
            score = 0.0
            doc_len = self.doc_lengths[idx]
            tf = self.doc_term_freqs[idx]
            for token in query_tokens:
                if token in tf:
                    f = tf[token]
                    idf = self._idf(token)
                    numerator = f * (self.k1 + 1.0)
                    denominator = f + self.k1 * (1.0 - self.b + self.b * (doc_len / (self.avg_doc_len or 1.0)))
                    score += idf * (numerator / denominator)
            scores.append(score)
        return scores

def reciprocal_rank_fusion(
    vector_rankings: List[str],
    bm25_rankings: List[str],
    k: int = 60
) -> List[Tuple[str, float]]:
    """
    Fuses two ranked document list outputs using Reciprocal Rank Fusion (RRF).
    Returns list of (document, score) tuples sorted in descending order of score.
    """
    scores = {}
    
    # helper to add rank scores
    def add_ranks(rank_list: List[str]):
        for rank, doc in enumerate(rank_list, start=1):
            scores[doc] = scores.get(doc, 0.0) + (1.0 / (k + rank))

    add_ranks(vector_rankings)
    add_ranks(bm25_rankings)
    
    return sorted(scores.items(), key=lambda item: item[1], reverse=True)


def hybrid_retrieve_and_rank(
    query: str,
    device_id: str,
    db_session,
    collection,
    n_results: int = 5
) -> Tuple[List[str], List[Dict[str, Any]]]:
    """
    Fetches documents from vector store/database, performs BM25 keyword ranking
    and vector similarity ranking, and fuses them using RRF.
    """
    from app.services.ai_reasoning.embeddings import telemetry_embeddings
    
    all_docs = []
    all_metadatas = []
    
    # 1. Fetch corpus documents for the device
    try:
        # Get all records for this device from ChromaDB
        res = collection.get(where={"device_id": device_id})
        if res and res.get("documents"):
            all_docs = res["documents"]
            all_metadatas = res["metadatas"]
            logger.info(f"Loaded {len(all_docs)} corpus records from ChromaDB for hybrid search.")
    except Exception as e:
        logger.error(f"ChromaDB corpus load error: {e}")

    # Fallback to database models if ChromaDB is empty
    if not all_docs:
        from app.models.telemetry import TelemetrySnapshot
        from sqlalchemy.orm import joinedload
        
        recent_snapshots = (
            db_session.query(TelemetrySnapshot)
            .options(
                joinedload(TelemetrySnapshot.cpu),
                joinedload(TelemetrySnapshot.gpu),
                joinedload(TelemetrySnapshot.memory),
                joinedload(TelemetrySnapshot.battery),
                joinedload(TelemetrySnapshot.disk),
                joinedload(TelemetrySnapshot.wifi),
                joinedload(TelemetrySnapshot.thermal),
                joinedload(TelemetrySnapshot.power)
            )
            .filter(TelemetrySnapshot.device_id == device_id)
            .order_by(TelemetrySnapshot.timestamp.desc())
            .limit(10)
            .all()
        )
        if recent_snapshots:
            for snap in recent_snapshots:
                try:
                    from app.services.langchain_twin import index_telemetry_in_vector_db
                    index_telemetry_in_vector_db(snap)
                except Exception as index_err:
                    logger.error(f"Failed to auto-index snapshot: {str(index_err)}")
                    
        for snap in recent_snapshots:
            timestamp_str = snap.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            cpu_usage = snap.cpu.cpu_usage if snap.cpu else 0.0
            memory_usage = snap.memory.memory_usage if snap.memory else 0.0
            disk_usage = snap.disk.disk_usage if snap.disk else 0.0
            cpu_temp = snap.thermal.cpu_temperature if snap.thermal else 0.0
            fan_speed = snap.thermal.fan_speed_rpm if snap.thermal else 0
            battery_level = snap.battery.battery_level if snap.battery else 0.0
            battery_health = snap.battery.battery_health if snap.battery else 100.0
            power_source = snap.power.power_source if snap.power else "ac"
            active_processes = snap.cpu.active_process_count if snap.cpu else 0
            cpu_freq = snap.cpu.cpu_frequency_mhz if (snap.cpu and snap.cpu.cpu_frequency_mhz is not None) else 0.0
            gpu_usage = snap.gpu.gpu_usage if snap.gpu else 0.0
            gpu_temp = snap.gpu.gpu_temperature if snap.gpu else 0.0
            cycle_count = snap.battery.cycle_count if snap.battery else 0
            
            content = (
                f"[Telemetry Record for {device_id} at {timestamp_str}] "
                f"CPU load is {cpu_usage}%. Memory usage is {memory_usage}%. "
                f"Disk usage space used is {disk_usage}%. CPU core temperature is {cpu_temp}°C with "
                f"cooling fan active at {fan_speed} RPM. Battery charge level is {battery_level}% (health: {battery_health}%) "
                f"connected via power source {power_source.upper()}. Active running processes: {active_processes}. "
                f"GPU usage is {gpu_usage}% with temperature {gpu_temp}°C. "
                f"CPU frequency is {cpu_freq or 0.0} MHz. Battery cycle count is {cycle_count}."
            )
            meta = {
                "timestamp": timestamp_str,
                "cpu_usage": cpu_usage,
                "memory_usage": memory_usage,
                "cpu_temperature": cpu_temp,
                "battery_health": battery_health,
                "battery_level": battery_level,
                "power_source": power_source,
                "fan_rpm": fan_speed,
                "disk_usage": disk_usage,
                "active_processes": active_processes,
                "cpu_frequency_mhz": float(cpu_freq),
                "gpu_usage": float(gpu_usage),
                "gpu_temperature": float(gpu_temp),
                "cycle_count": int(cycle_count)
            }
            all_docs.append(content)
            all_metadatas.append(meta)

    if not all_docs:
        return [], []

    # Map doc contents to metadata for easy retrieval lookup
    doc_to_meta = {doc: meta for doc, meta in zip(all_docs, all_metadatas)}

    # ─── A. VECTOR RANKING ────────────────────────────────────────────────────
    query_vector = telemetry_embeddings.embed_query(query)
    doc_vectors = [telemetry_embeddings.embed_query(doc) for doc in all_docs]
    
    # Calculate cosine similarity manually for the corpus to rank them
    vector_scored = []
    for doc, d_vec in zip(all_docs, doc_vectors):
        numerator = sum(a * b for a, b in zip(query_vector, d_vec))
        norm_q = math.sqrt(sum(a * a for a in query_vector))
        norm_d = math.sqrt(sum(b * b for b in d_vec))
        similarity = numerator / (norm_q * norm_d) if (norm_q * norm_d) > 0 else 0.0
        vector_scored.append((doc, similarity))
        
    vector_scored.sort(key=lambda x: x[1], reverse=True)
    vector_ranked_docs = [item[0] for item in vector_scored]

    # ─── B. BM25 RANKING ─────────────────────────────────────────────────────
    bm25 = BM25Retriever(all_docs)
    bm25_scores = bm25.score(query)
    bm25_scored = sorted(zip(all_docs, bm25_scores), key=lambda x: x[1], reverse=True)
    bm25_ranked_docs = [item[0] for item in bm25_scored]

    # ─── C. RECIPROCAL RANK FUSION (RRF) ──────────────────────────────────────
    fused_results = reciprocal_rank_fusion(vector_ranked_docs, bm25_ranked_docs)
    
    # Extract top results
    top_fused = fused_results[:n_results]
    
    final_docs = [item[0] for item in top_fused]
    final_metadatas = [doc_to_meta[doc] for doc in final_docs]
    
    return final_docs, final_metadatas
