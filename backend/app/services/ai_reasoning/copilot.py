"""
AI Copilot Orchestrator — Phase 40.
Unites guardrails, retrieval-ranking, evidence extraction, memory context, and explainability.
Supports socket triggers (Eco Mode, process killing) to communicate with the host daemon.
"""
import socket
from typing import Dict, Any, List, Optional
from app.core.logging import logger
from app.services.langchain_twin import query_digital_twin
from app.services.ai_reasoning.memory import session_memory
from app.services.ai_reasoning.explainable_ai import explain_prediction
from app.services.ai_reasoning.guardrails import validate_input

def send_daemon_signal(command: str) -> bool:
    """
    Attempts to connect to the daemon command listener on port 9090
    (checking localhost, host.docker.internal, etc.) and sends the trigger.
    """
    hosts_to_try = ["host.docker.internal", "localhost", "127.0.0.1", "172.17.0.1"]
    for host in hosts_to_try:
        try:
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.settimeout(0.5)
            client.connect((host, 9090))
            client.sendall(command.encode("utf-8"))
            response = client.recv(1024).decode("utf-8").strip()
            client.close()
            if response == "ACK":
                logger.info(f"Successfully sent command '{command}' to daemon at {host}:9090")
                return True
        except Exception:
            pass
    logger.warning(f"Unable to connect to daemon on port 9090 to send command: {command}")
    return False

def run_copilot_session(
    session_id: str,
    device_id: str,
    query: str,
    personality: str,
    db_session
) -> Dict[str, Any]:
    """
    Executes the complete Copilot pipeline:
    1. Guardrail input validation.
    2. Load memory context and inject summary.
    3. Query the RAG-grounded digital twin (BM25 + Vector ranking, Evidence extraction, Chain-of-thought).
    4. Save user turn and response to session memory.
    5. Summarize history if length exceeded.
    6. Run explainability feature attributions.
    7. Detect and emit actionable daemon triggers.
    """
    # 1. Input Guardrail
    input_status = validate_input(query)
    if not input_status.is_valid:
        return {
            "query": query,
            "response": input_status.reason or "Query validation failed.",
            "source_documents": [],
            "evidence": [],
            "steps": [],
            "explainability_attributions": {},
            "action_triggered": None
        }

    # 2. Memory Context Loading
    history = session_memory.get_history(session_id)
    summary = session_memory.get_summary(session_id)
    
    # Enrich the current query with session summary context if it exists
    enriched_query = query
    if summary:
        enriched_query = f"[Session Summary Context: {summary}] {query}"

    # 3. RAG Query digital twin (retrieval, ranking, evidence, CoT)
    rag_result = query_digital_twin(
        device_id=device_id,
        query=enriched_query,
        db_session=db_session,
        personality=personality
    )

    response_text = rag_result["response"]
    
    # 4. Action Trigger Detection and Execution
    query_lower = query.lower()
    action_triggered = None
    if "eco mode" in query_lower or "optimize power" in query_lower:
        success = send_daemon_signal("ECO_MODE")
        if success:
            action_triggered = "ECO_MODE"
            response_text += "\n\n[Action Control] Socket signal emitted: engaged Eco Mode on host daemon."
    elif "kill" in query_lower and ("process" in query_lower or "cpu" in query_lower):
        success = send_daemon_signal("KILL_HIGH_CPU")
        if success:
            action_triggered = "KILL_HIGH_CPU"
            response_text += "\n\n[Action Control] Socket signal emitted: requested high-CPU process termination on host daemon."

    # Update response in rag result
    rag_result["response"] = response_text

    # 5. Save turn to memory
    session_memory.save_message(session_id, "user", query)
    session_memory.save_message(session_id, "assistant", response_text)
    session_memory.summarize_session_if_needed(session_id)

    # 6. Calculate Explainable AI Attributions
    attributions = explain_prediction(device_id, db_session)

    return {
        "query": query,
        "response": response_text,
        "source_documents": rag_result.get("source_documents", []),
        "evidence": rag_result.get("evidence", []),
        "steps": rag_result.get("steps", []),
        "explainability_attributions": attributions,
        "action_triggered": action_triggered
    }
