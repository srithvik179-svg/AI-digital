import datetime
from datetime import datetime as dt
from typing import List, Dict, Any
import chromadb
from chromadb.config import Settings as ChromaSettings
from langchain_classic.chains import RetrievalQA
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_core.prompts import PromptTemplate
import uuid

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
        record_id = record.id

    if isinstance(timestamp, str):
        try:
            timestamp_obj = dt.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError:
            timestamp_obj = dt.utcnow()
    else:
        timestamp_obj = timestamp

    timestamp_str = timestamp_obj.strftime("%Y-%m-%d %H:%M:%S")
    content = (
        f"At {timestamp_str}, device '{device_id}' reported: "
        f"CPU usage is {cpu_usage}%, Memory usage is {memory_usage}%, "
        f"Disk usage is {disk_usage}%. CPU Temperature is {cpu_temperature}°C with "
        f"fan speed at {fan_speed} RPM. Battery level is {battery_level}% (health: {battery_health}%) "
        f"and power source is {power_source}. Active processes: {active_process_count}."
    )
    
    doc_id = f"telemetry_{device_id}_{record_id}"
    
    metadata = {
        "device_id": device_id,
        "timestamp": timestamp_str,
        "cpu_usage": cpu_usage,
        "memory_usage": memory_usage,
        "cpu_temperature": cpu_temperature,
        "battery_health": battery_health
    }
    
    try:
        collection.add(
            documents=[content],
            metadatas=[metadata],
            ids=[doc_id]
        )
        logger.debug(f"Indexed telemetry record in ChromaDB: {doc_id}")
    except Exception as e:
        logger.error(f"Failed to add document to ChromaDB: {str(e)}")

def get_mock_response(query: str, recent_snapshots: List[TelemetrySnapshot]) -> Dict[str, Any]:
    """
    Generate an intelligent mock response analyzing the device's status and telemetry records.
    """
    query_lower = query.lower()
    
    if not recent_snapshots:
        return {
            "response": "Hello! I am your AI Laptop Twin. Currently, I don't have any telemetry data loaded for this device. Please send some telemetry logs to start analyzing the twin.",
            "source_documents": []
        }
    
    latest = recent_snapshots[0]
    
    # Safe getters
    battery_health = latest.battery.battery_health if latest.battery else 94.0
    battery_level = latest.battery.battery_level if latest.battery else 100.0
    power_source = latest.power.power_source if latest.power else "ac"
    cpu_temp = latest.thermal.cpu_temperature if latest.thermal else 45.0
    fan_speed = latest.thermal.fan_speed_rpm if latest.thermal else 1200
    cpu_usage = latest.cpu.cpu_usage if latest.cpu else 15.0
    active_process_count = latest.cpu.active_process_count if latest.cpu else 95
    memory_usage = latest.memory.memory_usage if latest.memory else 50.0
    disk_usage = latest.disk.disk_usage if latest.disk else 40.0
    
    # Build context from recent records
    context_docs = []
    for r in recent_snapshots[:5]:
        r_cpu = r.cpu.cpu_usage if r.cpu else 0.0
        r_temp = r.thermal.cpu_temperature if r.thermal else 0.0
        r_bat = r.battery.battery_level if r.battery else 0.0
        context_docs.append(f"At {r.timestamp}, CPU was {r_cpu}%, Temp was {r_temp}°C, Battery was {r_bat}%.")
    
    # Rule-based diagnostics matching queries
    if "battery" in query_lower:
        if battery_health < 80:
            health_status = "degraded (<80%) and you might notice reduced battery life. Consider scheduling a service replacement."
        else:
            health_status = f"healthy at {battery_health}%. The current charge is {battery_level}% with power source connected via {power_source.upper()}."
        
        response = (
            f"Based on recent telemetry, your battery health is currently {health_status}. "
            f"The device is currently running on {power_source}. "
            "To maximize battery lifespan, try to keep the charge cycle between 20% and 80%."
        )
    elif "fan" in query_lower or "hot" in query_lower or "temperature" in query_lower or "temp" in query_lower:
        if cpu_temp > 75:
            temp_status = (
                f"running high ({cpu_temp}°C) with the fan active at {fan_speed} RPM. "
                "This might be due to intensive computational tasks or background processes."
            )
        else:
            temp_status = f"stable at {cpu_temp}°C with fans running quietly at {fan_speed} RPM."
            
        response = (
            f"The thermal status of your laptop is {temp_status}. "
            "If you notice persistent high temperatures, make sure the vents are clear and inspect background CPU consumption."
        )
    elif "cpu" in query_lower or "performance" in query_lower or "slow" in query_lower:
        if cpu_usage > 80:
            cpu_status = (
                f"very high ({cpu_usage}%) with {active_process_count} active processes. "
                "This could cause interface lag or thermal throttle."
            )
        else:
            cpu_status = f"optimal ({cpu_usage}%) with {active_process_count} active processes."
            
        response = (
            f"CPU utilization is currently {cpu_status}. "
            f"Memory usage is also stable at {memory_usage}%. Your system has sufficient overhead for standard operations."
        )
    else:
        response = (
            f"Hello! I am your Laptop's Digital Twin. Here is my current system snapshot:\n"
            f"- CPU Usage: {cpu_usage}%\n"
            f"- Temperature: {cpu_temp}°C\n"
            f"- Memory Usage: {memory_usage}%\n"
            f"- Power Source: {power_source.upper()} (Battery: {battery_level}%)\n"
            f"- Active Processes: {active_process_count}\n\n"
            "I'm ready to answer any specific questions you have about battery state, performance bottlenecks, or heating."
        )

    return {
        "response": response,
        "source_documents": context_docs
    }

def query_digital_twin(device_id: str, query: str, db_session) -> Dict[str, Any]:
    """
    Main RAG query coordinator. Queries ChromaDB + DB telemetry logs and builds the response.
    Supports either real LangChain QA chain or local mock diagnosis.
    """
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
    
    if settings.MOCK_LLM or settings.OPENAI_API_KEY == "mock_key":
        logger.info(f"Generating mock answer for twin query: '{query}'")
        return get_mock_response(query, recent_snapshots)
        
    try:
        embeddings = OpenAIEmbeddings(openai_api_key=settings.OPENAI_API_KEY)
        
        # Connect to Chroma as a LangChain VectorStore
        vectordb = Chroma(
            client=chroma_client,
            collection_name=collection_name,
            embedding_function=embeddings
        )
        
        # Set up a prompt with context
        prompt_template = """You are the AI Digital Twin of a laptop.
You have access to historical and real-time telemetry logs containing cpu_usage, memory_usage, cpu_temperature, fan_speed, battery_level, battery_health, and power_source.
Answer the user's question about the laptop state objectively and provide diagnostics if needed.

Context from vector telemetry logs:
{context}

Question: {question}
Answer in a friendly, helpful, and highly descriptive style:"""
        
        PROMPT = PromptTemplate(
            template=prompt_template, input_variables=["context", "question"]
        )
        
        llm = ChatOpenAI(
            model_name="gpt-4-turbo",
            temperature=0.2,
            openai_api_key=settings.OPENAI_API_KEY
        )
        
        retriever = vectordb.as_retriever(
            search_kwargs={"filter": {"device_id": device_id}, "k": 5}
        )
        
        qa_chain = RetrievalQA.from_chain_type(
            llm=llm,
            chain_type="stuff",
            retriever=retriever,
            chain_type_kwargs={"prompt": PROMPT},
            return_source_documents=True
        )
        
        result = qa_chain({"query": query})
        
        sources = [doc.page_content for doc in result.get("source_documents", [])]
        
        return {
            "response": result["result"],
            "source_documents": sources
        }
    except Exception as e:
        logger.error(f"Error in LangChain RAG pipeline: {str(e)}. Falling back to mock diagnostics.")
        return get_mock_response(query, recent_snapshots)
