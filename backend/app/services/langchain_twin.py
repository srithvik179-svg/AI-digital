import datetime
from datetime import datetime as dt
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings as ChromaSettings
from langchain_classic.chains import RetrievalQA
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_core.prompts import PromptTemplate
import uuid
import re

from app.core.config import settings
from app.core.logging import logger
from app.models.telemetry import TelemetrySnapshot

# Initialize ChromaDB Client
try:
    if settings.MOCK_LLM:
        chroma_client = chromadb.Client()
        logger.info("ChromaDB Client initialized in-memory for Mock Mode.")
    else:
        chroma_client = chromadb.HttpClient(
            host=settings.CHROMA_HOST,
            port=settings.CHROMA_PORT,
            settings=ChromaSettings(allow_reset=True)
        )
        logger.info(f"ChromaDB Client connected to HTTP service at {settings.CHROMA_HOST}:{settings.CHROMA_PORT}")
except Exception as e:
    logger.error(f"Failed to connect to ChromaDB: {str(e)}. Falling back to in-memory Client.")
    chroma_client = chromadb.Client()

# Get or create the vector collection
collection_name = "laptop_telemetry_logs"
collection = chroma_client.get_or_create_collection(name=collection_name)

def index_telemetry_in_vector_db(record: Any):
    """
    Formulate a descriptive textual representation of the telemetry record and index it.
    Can accept a flat dictionary or a TelemetrySnapshot model.
    """
    if isinstance(record, dict):
        device_id = record.get("device_id", "laptop-generic")
        timestamp = record.get("timestamp", dt.utcnow())
        cpu_usage = record.get("cpu_usage", 0.0)
        memory_usage = record.get("memory_usage", 0.0)
        disk_usage = record.get("disk_usage", 0.0)
        cpu_temperature = record.get("cpu_temperature", 0.0)
        fan_speed = record.get("fan_speed", 0)
        battery_level = record.get("battery_level", 0.0)
        battery_health = record.get("battery_health", 0.0)
        power_source = record.get("power_source", "ac")
        active_process_count = record.get("active_process_count", 0)
        cpu_frequency_mhz = record.get("cpu_frequency_mhz", None)
        gpu_usage = record.get("gpu_usage", 0.0)
        gpu_temperature = record.get("gpu_temperature", 0.0)
        cycle_count = record.get("cycle_count", record.get("battery_cycle_count", 0))
        record_id = record.get("id", str(uuid.uuid4()))
    else:
        # It is a TelemetrySnapshot object
        device_id = record.device_id
        timestamp = record.timestamp
        cpu_usage = record.cpu.cpu_usage if record.cpu else 0.0
        memory_usage = record.memory.memory_usage if record.memory else 0.0
        disk_usage = record.disk.disk_usage if record.disk else 0.0
        cpu_temperature = record.thermal.cpu_temperature if record.thermal else 0.0
        fan_speed = record.thermal.fan_speed_rpm if record.thermal else 0
        battery_level = record.battery.battery_level if record.battery else 0.0
        battery_health = record.battery.battery_health if record.battery else 0.0
        power_source = record.power.power_source if record.power else "ac"
        active_process_count = record.cpu.active_process_count if record.cpu else 0
        cpu_frequency_mhz = record.cpu.cpu_frequency_mhz if record.cpu else None
        gpu_usage = record.gpu.gpu_usage if record.gpu else 0.0
        gpu_temperature = record.gpu.gpu_temperature if record.gpu else 0.0
        cycle_count = record.battery.cycle_count if record.battery else 0
        record_id = record.id

    if isinstance(timestamp, str):
        try:
            timestamp_obj = dt.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError:
            timestamp_obj = dt.utcnow()
    else:
        timestamp_obj = timestamp

    timestamp_str = timestamp_obj.strftime("%Y-%m-%d %H:%M:%S")
    
    # Structural telemetry text representation (embedding payload)
    content = (
        f"[Telemetry Record for {device_id} at {timestamp_str}] "
        f"CPU load is {cpu_usage}%. Memory usage is {memory_usage}%. "
        f"Disk usage space used is {disk_usage}%. CPU core temperature is {cpu_temperature}°C with "
        f"cooling fan active at {fan_speed} RPM. Battery charge level is {battery_level}% (health: {battery_health}%) "
        f"connected via power source {power_source.upper()}. Active running processes: {active_process_count}. "
        f"GPU usage is {gpu_usage}% with temperature {gpu_temperature}°C. "
        f"CPU frequency is {cpu_frequency_mhz or 0.0} MHz. Battery cycle count is {cycle_count}."
    )
    
    doc_id = f"telemetry_{device_id}_{record_id}"
    
    metadata = {
        "device_id": device_id,
        "timestamp": timestamp_str,
        "cpu_usage": float(cpu_usage),
        "memory_usage": float(memory_usage),
        "cpu_temperature": float(cpu_temperature),
        "battery_health": float(battery_health),
        "battery_level": float(battery_level),
        "power_source": str(power_source),
        "fan_rpm": float(fan_speed),
        "disk_usage": float(disk_usage),
        "active_processes": int(active_process_count),
        "cpu_frequency_mhz": float(cpu_frequency_mhz) if cpu_frequency_mhz is not None else 0.0,
        "gpu_usage": float(gpu_usage),
        "gpu_temperature": float(gpu_temperature) if gpu_temperature is not None else 0.0,
        "cycle_count": int(cycle_count) if cycle_count is not None else 0
    }
    
    try:
        from app.services.ai_reasoning.embeddings import telemetry_embeddings
        doc_embeddings = telemetry_embeddings.embed_documents([content])
        collection.upsert(
            documents=[content],
            embeddings=doc_embeddings,
            metadatas=[metadata],
            ids=[doc_id]
        )
        logger.debug(f"Indexed telemetry record in ChromaDB: {doc_id}")
    except Exception as e:
        logger.error(f"Failed to upsert document to ChromaDB: {str(e)}")


def query_digital_twin(device_id: str, query: str, db_session, personality: str = "diagnostic_engineer") -> Dict[str, Any]:
    """
    Retrieval-Augmented Generation (RAG) query engine.
    1. Retrieves context from ChromaDB (falls back & syncs from PostgreSQL if Chroma is empty).
    2. Assembles structured, cited contexts.
    3. Executes a grounded generator (GPT-4 or Grounded Cognitive Solver) to prevent hallucinations.
    """
    from app.services.ai_reasoning.guardrails import validate_input, validate_output
    from app.services.ai_reasoning.chain_of_thought import parse_cot_response, generate_local_cot
    input_status = validate_input(query)
    if not input_status.is_valid:
        return {
            "query": query,
            "response": input_status.reason or "Query validation failed.",
            "source_documents": [],
            "evidence": [],
            "steps": []
        }
        
    query_lower = query.lower().strip()
    
    # ─── 1. RETRIEVAL LAYER ──────────────────────────────────────────────────
    from app.services.ai_reasoning.retrieval_ranking import hybrid_retrieve_and_rank
    try:
        retrieved_docs, retrieved_metadatas = hybrid_retrieve_and_rank(
            query=query,
            device_id=device_id,
            db_session=db_session,
            collection=collection,
            n_results=5
        )
    except Exception as e:
        logger.error(f"Hybrid retrieval and ranking failed: {e}")
        retrieved_docs, retrieved_metadatas = [], []

    from app.services.ai_reasoning.evidence_extractor import extract_evidence
    evidence_items = extract_evidence(retrieved_docs)
    evidence_serialized = [item.model_dump() for item in evidence_items]

    # ─── 2. CONTEXT ASSEMBLY ─────────────────────────────────────────────────
    context_lines = []
    for doc, meta in zip(retrieved_docs, retrieved_metadatas):
        timestamp = meta.get("timestamp", "unknown")
        context_lines.append(f"- [Source: Telemetry at {timestamp}] {doc}")
        
    context = "\n".join(context_lines)

    # ─── 3. GROUNDED ANSWER GENERATION ───────────────────────────────────────
    
    # Check if query is completely out-of-scope (preventing generic chat hallucinations)
    scope_keywords = ["cpu", "gpu", "battery", "disk", "temp", "fan", "heat", "hot", "power", "charge", "performance", "usage", "process", "processes", "signal", "wifi"]
    is_in_scope = any(kw in query_lower for kw in scope_keywords)
    
    # If there is no context available, we cannot answer
    if not retrieved_docs or not is_in_scope:
        return {
            "query": query,
            "response": "I cannot find evidence in the telemetry logs to answer this question.",
            "source_documents": retrieved_docs,
            "evidence": evidence_serialized,
            "steps": []
        }

    # REAL LLM RAG Mode (if OpenAI API Key is valid and MOCK_LLM is disabled)
    if not settings.MOCK_LLM and settings.OPENAI_API_KEY != "mock_key":
        try:
            from app.models.alert import TelemetryAlert
            
            # Query DB for live prompt variables
            alerts_count = db_session.query(TelemetryAlert).filter(
                TelemetryAlert.device_id == device_id,
                TelemetryAlert.acknowledged == False
            ).count()
            
            latest_snap = db_session.query(TelemetrySnapshot).filter(
                TelemetrySnapshot.device_id == device_id
            ).order_by(TelemetrySnapshot.timestamp.desc()).first()
            
            health_score = latest_snap.health_score if (latest_snap and latest_snap.health_score is not None) else 100.0
            health_category = latest_snap.health_category if (latest_snap and latest_snap.health_category is not None) else "Healthy"
            
            from app.services.ai_reasoning.prompts import prompt_registry
            compiled_prompt = prompt_registry.get_prompt(
                personality=personality,
                device_id=device_id,
                alerts_count=alerts_count,
                health_score=health_score,
                health_category=health_category,
                context=context,
                question=query
            )
            
            llm = ChatOpenAI(
                model_name="gpt-4-turbo",
                temperature=0.0, # Zero temperature to enforce deterministic grounding
                openai_api_key=settings.OPENAI_API_KEY
            )
            
            result = llm.predict(compiled_prompt)
            
            final_response, steps = parse_cot_response(result.strip())
            _, final_response = validate_output(final_response, evidence_items)
            return {
                "query": query,
                "response": final_response,
                "source_documents": retrieved_docs,
                "evidence": evidence_serialized,
                "steps": [s.model_dump() for s in steps]
            }
        except Exception as e:
            logger.error(f"Error in OpenAI LLM execution: {str(e)}. Falling back to Grounded Cognitive Solver.")

    # LOCAL / MOCK GROUNDED COGNITIVE SOLVER
    # Fully grounded resolver that answers strictly from context and cites sources
    responses = []
    
    # Resolve CPU stats from context
    if any(k in query_lower for k in ["cpu", "process", "processes", "frequency"]):
        # Find the latest document containing CPU info
        cpu_record = None
        for meta in retrieved_metadatas:
            if "cpu_usage" in meta:
                cpu_record = meta
                break
        if cpu_record:
            freq_str = f" running at {cpu_record['cpu_frequency_mhz']:.0f} MHz" if cpu_record.get("cpu_frequency_mhz") else ""
            cpu_usage = cpu_record["cpu_usage"]
            active_processes = cpu_record.get("active_processes", 0)
            
            # Formulate grounded response with exact citations
            resp = f"CPU Status: Utilization is {cpu_usage:.1f}% with {active_processes} active processes{freq_str}."
            if cpu_usage > 85.0:
                resp += " The CPU load is critically high."
            elif cpu_usage > 50.0:
                resp += " The CPU is under moderate workload."
            else:
                resp += " The CPU is running cool and idle."
                
            resp += f" [Source: Telemetry at {cpu_record['timestamp']}]"
            responses.append(resp)

    # Resolve GPU stats
    if any(k in query_lower for k in ["gpu", "graphics", "vram", "card"]):
        gpu_record = None
        for meta in retrieved_metadatas:
            if "gpu_usage" in meta:
                gpu_record = meta
                break
        if gpu_record:
            gpu_usage = gpu_record["gpu_usage"]
            gpu_temp = gpu_record.get("gpu_temperature")
            temp_str = f", temperature is {gpu_temp:.1f}°C" if gpu_temp is not None else ""
            
            resp = f"GPU Status: Utilization is {gpu_usage:.1f}%{temp_str}."
            if gpu_usage > 80.0:
                resp += " The GPU is heavily loaded."
            else:
                resp += " The GPU load is nominal."
                
            resp += f" [Source: Telemetry at {gpu_record['timestamp']}]"
            responses.append(resp)

    # Resolve Battery stats
    if any(k in query_lower for k in ["battery", "charge", "power", "cycle", "cycles", "health", "drain"]):
        bat_record = None
        for meta in retrieved_metadatas:
            if "battery_level" in meta:
                bat_record = meta
                break
        if bat_record:
            level = bat_record["battery_level"]
            health = bat_record["battery_health"]
            power_src = bat_record.get("power_source", "ac").upper()
            cycles = int(bat_record.get("battery_cycle_count", bat_record.get("cycle_count", 0)))
            
            resp = f"Battery Status: Charge level is {level:.1f}% (health: {health:.1f}%) with {cycles} cycles. Power source: {power_src}."
            if power_src == "BATTERY" and level < 20.0:
                resp += " Battery is low."
            elif health < 80.0:
                resp += " Battery health has degraded below 80%."
            else:
                resp += " Battery is in healthy condition."
                
            resp += f" [Source: Telemetry at {bat_record['timestamp']}]"
            responses.append(resp)

    # Resolve Disk stats
    if any(k in query_lower for k in ["disk", "storage", "drive", "space", "ssd"]):
        disk_record = None
        for meta in retrieved_metadatas:
            if "disk_usage" in meta:
                disk_record = meta
                break
        if disk_record:
            usage = disk_record["disk_usage"]
            resp = f"Disk Status: Space used is {usage:.1f}%."
            if usage > 90.0:
                resp += " Disk storage is critically low (<10% free)."
            else:
                resp += " Disk space is sufficient."
                
            resp += f" [Source: Telemetry at {disk_record['timestamp']}]"
            responses.append(resp)

    # Resolve Temperature and thermal stats
    if any(k in query_lower for k in ["temp", "temperature", "hot", "heat", "fan", "rpm"]):
        temp_record = None
        for meta in retrieved_metadatas:
            if "cpu_temperature" in meta:
                temp_record = meta
                break
        if temp_record:
            cpu_temp = temp_record["cpu_temperature"]
            fan_rpm = temp_record.get("fan_rpm", 0.0)
            
            resp = f"Thermal Status: CPU temperature is {cpu_temp:.1f}°C with cooling fan active at {fan_rpm:.0f} RPM."
            if cpu_temp > 75.0:
                resp += " The system thermals are elevated."
            else:
                resp += " The thermals are stable and normal."
                
            resp += f" [Source: Telemetry at {temp_record['timestamp']}]"
            responses.append(resp)

    # If queries matched keywords but no data records are found, or solver compiled nothing:
    if not responses:
        # Default back to compiling all active metrics from the latest record as a cited baseline
        latest_meta = retrieved_metadatas[0]
        resp = (
            f"Active system status baseline:\n"
            f"- CPU Usage: {latest_meta.get('cpu_usage', 0.0):.1f}%\n"
            f"- Temperature: {latest_meta.get('cpu_temperature', 0.0):.1f}°C\n"
            f"- Memory Usage: {latest_meta.get('memory_usage', 0.0):.1f}%\n"
            f"- Power Source: {str(latest_meta.get('power_source', 'AC')).upper()} (Battery Level: {latest_meta.get('battery_level', 100.0):.1f}%)\n"
            f" [Source: Telemetry at {latest_meta['timestamp']}]"
        )
        responses.append(resp)

    response_text = "\n".join(responses)
    _, final_response = validate_output(response_text, evidence_items)
    steps = generate_local_cot(query, evidence_serialized)
    return {
        "query": query,
        "response": final_response,
        "source_documents": retrieved_docs,
        "evidence": evidence_serialized,
        "steps": [s.model_dump() for s in steps]
    }
