import datetime
from typing import List, Dict, Any
import chromadb
from chromadb.config import Settings as ChromaSettings
from langchain_classic.chains import RetrievalQA
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_core.prompts import PromptTemplate
from app.core.config import settings
from app.core.logging import logger
from app.models.telemetry import TelemetryRecord

# Initialize ChromaDB Client
try:
    if settings.MOCK_LLM:
        # In mock mode, we can use an in-memory client or a local directory
        chroma_client = chromadb.Client()
        logger.info("ChromaDB Client initialized in-memory for Mock Mode.")
    else:
        # Connect to the standalone Chroma service
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

def index_telemetry_in_vector_db(record: TelemetryRecord):
    """
    Formulate a descriptive textual representation of the telemetry record and index it.
    This description is stored in ChromaDB for semantic search queries.
    """
    timestamp_str = record.timestamp.strftime("%Y-%m-%d %H:%M:%S")
    content = (
        f"At {timestamp_str}, device '{record.device_id}' reported: "
        f"CPU usage is {record.cpu_usage}%, Memory usage is {record.memory_usage}%, "
        f"Disk usage is {record.disk_usage}%. CPU Temperature is {record.cpu_temperature}°C with "
        f"fan speed at {record.fan_speed} RPM. Battery level is {record.battery_level}% (health: {record.battery_health}%) "
        f"and power source is {record.power_source}. Active processes: {record.active_process_count}."
    )
    
    doc_id = f"telemetry_{record.device_id}_{record.id}"
    
    metadata = {
        "device_id": record.device_id,
        "timestamp": timestamp_str,
        "cpu_usage": record.cpu_usage,
        "memory_usage": record.memory_usage,
        "cpu_temperature": record.cpu_temperature,
        "battery_health": record.battery_health
    }
    
    # In Mock mode, we just add documents using ChromaDB's default embedding function
    # In real mode, we could also define custom embeddings, but Chroma's default or simple embeddings work
    try:
        collection.add(
            documents=[content],
            metadatas=[metadata],
            ids=[doc_id]
        )
        logger.debug(f"Indexed telemetry record in ChromaDB: {doc_id}")
    except Exception as e:
        logger.error(f"Failed to add document to ChromaDB: {str(e)}")

def get_mock_response(query: str, recent_records: List[TelemetryRecord]) -> Dict[str, Any]:
    """
    Generate an intelligent mock response analyzing the device's status and telemetry records.
    """
    query_lower = query.lower()
    
    if not recent_records:
        return {
            "response": "Hello! I am your AI Laptop Twin. Currently, I don't have any telemetry data loaded for this device. Please send some telemetry logs to start analyzing the twin.",
            "source_documents": []
        }
    
    latest = recent_records[0]
    
    # Build context from recent records
    context_docs = [
        f"At {r.timestamp}, CPU was {r.cpu_usage}%, Temp was {r.cpu_temperature}°C, Battery was {r.battery_level}%."
        for r in recent_records[:5]
    ]
    
    # Rule-based diagnostics matching queries
    if "battery" in query_lower:
        if latest.battery_health < 80:
            health_status = "degraded (<80%) and you might notice reduced battery life. Consider scheduling a service replacement."
        else:
            health_status = f"healthy at {latest.battery_health}%. The current charge is {latest.battery_level}% with power source connected via {latest.power_source.upper()}."
        
        response = (
            f"Based on recent telemetry, your battery health is currently {health_status}. "
            f"The device is currently running on {latest.power_source}. "
            "To maximize battery lifespan, try to keep the charge cycle between 20% and 80%."
        )
    elif "fan" in query_lower or "hot" in query_lower or "temperature" in query_lower or "temp" in query_lower:
        if latest.cpu_temperature > 75:
            temp_status = (
                f"running high ({latest.cpu_temperature}°C) with the fan active at {latest.fan_speed} RPM. "
                "This might be due to intensive computational tasks or background processes."
            )
        else:
            temp_status = f"stable at {latest.cpu_temperature}°C with fans running quietly at {latest.fan_speed} RPM."
            
        response = (
            f"The thermal status of your laptop is {temp_status}. "
            "If you notice persistent high temperatures, make sure the vents are clear and inspect background CPU consumption."
        )
    elif "cpu" in query_lower or "performance" in query_lower or "slow" in query_lower:
        if latest.cpu_usage > 80:
            cpu_status = (
                f"very high ({latest.cpu_usage}%) with {latest.active_process_count} active processes. "
                "This could cause interface lag or thermal throttle."
            )
        else:
            cpu_status = f"optimal ({latest.cpu_usage}%) with {latest.active_process_count} active processes."
            
        response = (
            f"CPU utilization is currently {cpu_status}. "
            f"Memory usage is also stable at {latest.memory_usage}%. Your system has sufficient overhead for standard operations."
        )
    else:
        response = (
            f"Hello! I am your Laptop's Digital Twin. Here is my current system snapshot:\n"
            f"- CPU Usage: {latest.cpu_usage}%\n"
            f"- Temperature: {latest.cpu_temperature}°C\n"
            f"- Memory Usage: {latest.memory_usage}%\n"
            f"- Power Source: {latest.power_source.upper()} (Battery: {latest.battery_level}%)\n"
            f"- Active Processes: {latest.active_process_count}\n\n"
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
    # Fetch recent telemetry logs from DB for structured context
    # Note: importing here to avoid circular imports
    from app.models.telemetry import TelemetryRecord
    
    recent_records = (
        db_session.query(TelemetryRecord)
        .filter(TelemetryRecord.device_id == device_id)
        .order_by(TelemetryRecord.timestamp.desc())
        .limit(10)
        .all()
    )
    
    if settings.MOCK_LLM or settings.OPENAI_API_KEY == "mock_key":
        logger.info(f"Generating mock answer for twin query: '{query}'")
        return get_mock_response(query, recent_records)
        
    try:
        # Real RAG Implementation using LangChain + ChromaDB
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
        
        # Filter retrieved docs to only this device_id
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
        return get_mock_response(query, recent_records)
