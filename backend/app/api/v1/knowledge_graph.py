from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Dict, Any, List

from app.core.database import get_db
from app.core.logging import logger
from app.services.knowledge_graph import sync_relationships_to_neo4j, execute_cypher_query

router = APIRouter()

class CypherRequest(BaseModel):
    query: str = Field(
        default="MATCH (n:TelemetryMetric {device_id: $device_id})-[r:INFLUENCES]->(m:TelemetryMetric {device_id: $device_id}) RETURN n, r, m",
        description="Cypher query string to execute on Neo4j. Use $device_id parameter for safety."
    )
    device_id: str = Field(..., description="Device ID context to pass as parameter.")

@router.post("/sync", response_model=Dict[str, Any])
def sync_graph(
    device_id: str,
    db: Session = Depends(get_db)
):
    """
    Manually trigger synchronization of PostgreSQL computed relationships to Neo4j.
    """
    try:
        logger.info(f"Manual trigger to sync knowledge graph for device '{device_id}'")
        res = sync_relationships_to_neo4j(device_id=device_id, db_session=db)
        if res.get("status") == "error":
            raise HTTPException(status_code=500, detail=res.get("message"))
        return res
    except Exception as e:
        logger.error(f"Failed manual graph sync: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to sync knowledge graph: {str(e)}"
        )

@router.post("/query", response_model=Dict[str, Any])
def query_graph(
    req: CypherRequest
):
    """
    Execute read-only Cypher query on Neo4j knowledge graph and return structured graph representation.
    """
    try:
        logger.info(f"Executing Cypher query: {req.query} for device '{req.device_id}'")
        # Strip structural mutations to enforce read safety
        clean_query = req.query.strip()
        forbidden_keywords = ["CREATE ", "MERGE ", "DELETE ", "REMOVE ", "SET ", "DROP "]
        if any(kw in clean_query.upper() for kw in forbidden_keywords):
            raise HTTPException(
                status_code=400,
                detail="Writing or modifying operations are prohibited on this query endpoint."
            )

        res = execute_cypher_query(
            query=req.query,
            parameters={"device_id": req.device_id}
        )
        return res
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Failed Cypher query execution: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to execute Cypher query: {str(e)}"
        )
