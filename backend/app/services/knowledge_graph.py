"""
Knowledge Graph Service — Phase 15.
Synchronizes hardware telemetry relationships to Neo4j and provides graph query capability.
"""

from typing import Dict, List, Any
from sqlalchemy.orm import Session
from app.models.relationship import TelemetryRelationship
from app.core.neo4j import get_neo4j_driver
from app.core.logging import logger

# Metdata dictionary to enrich graph nodes
NODE_METADATA = {
    "cpu_usage": {
        "label": "CPU Usage",
        "description": "Processor computation utilization rate (%)"
    },
    "cpu_temperature": {
        "label": "CPU Temp",
        "description": "Processor core thermal status (°C)"
    },
    "fan_speed_rpm": {
        "label": "Fan Speed",
        "description": "Active cooling fan speed (RPM)"
    },
    "power_source": {
        "label": "Power Source",
        "description": "Charger state (AC vs Battery DC)"
    },
    "battery_level_delta": {
        "label": "Battery Delta",
        "description": "Battery charge and drain rate (%/s)"
    },
    "memory_usage": {
        "label": "Memory Usage",
        "description": "System RAM utilization (%)"
    },
    "disk_usage": {
        "label": "Disk Usage",
        "description": "Local SSD utilization (%)"
    },
    "battery_level": {
        "label": "Battery Level",
        "description": "Battery remaining capacity (%)"
    },
    "battery_temperature": {
        "label": "Battery Temp",
        "description": "Battery chemical thermal status (°C)"
    },
    "gpu_usage": {
        "label": "GPU Usage",
        "description": "Graphics processor utilization (%)"
    }
}

def sync_relationships_to_neo4j(device_id: str, db_session: Session) -> Dict[str, Any]:
    """
    Retrieves telemetry relationships from Postgres and synchronizes them to Neo4j.
    Returns status and sync stats.
    """
    logger.info(f"Syncing telemetry relationships to Neo4j for device '{device_id}'")
    try:
        # Fetch relationships from SQL DB
        relationships = (
            db_session.query(TelemetryRelationship)
            .filter(TelemetryRelationship.device_id == device_id)
            .all()
        )
        
        if not relationships:
            logger.warning(f"No Postgres relationships found to sync for device '{device_id}'")
            return {"status": "skipped", "message": "No relationships found in SQL DB.", "nodes_synced": 0, "edges_synced": 0}

        driver = get_neo4j_driver()
        if not driver:
            raise Exception("Neo4j driver is not initialized.")

        nodes_synced = 0
        edges_synced = 0

        with driver.session() as session:
            # Idempotent write query to insert nodes and relationships
            # Clear existing relationships for this device first to maintain graph cleanliness
            session.run(
                """
                MATCH (s:TelemetryMetric {device_id: $device_id})-[r:INFLUENCES]->(t:TelemetryMetric {device_id: $device_id})
                DELETE r
                """,
                device_id=device_id
            )

            for rel in relationships:
                source_meta = NODE_METADATA.get(rel.source_node, {"label": rel.source_node, "description": "Telemetry metric channel"})
                target_meta = NODE_METADATA.get(rel.target_node, {"label": rel.target_node, "description": "Telemetry metric channel"})

                # MERGE nodes and relationship
                session.run(
                    """
                    MERGE (s:TelemetryMetric {id: $source_id, device_id: $device_id})
                    ON CREATE SET s.label = $source_label, s.description = $source_desc
                    ON MATCH SET s.label = $source_label, s.description = $source_desc

                    MERGE (t:TelemetryMetric {id: $target_id, device_id: $device_id})
                    ON CREATE SET t.label = $target_label, t.description = $target_desc
                    ON MATCH SET t.label = $target_label, t.description = $target_desc

                    MERGE (s)-[r:INFLUENCES {relationship_type: $rel_type}]->(t)
                    SET r.correlation_strength = $strength,
                        r.description = $desc,
                        r.source = $source_id,
                        r.target = $target_id
                    """,
                    device_id=device_id,
                    source_id=rel.source_node,
                    source_label=source_meta["label"],
                    source_desc=source_meta["description"],
                    target_id=rel.target_node,
                    target_label=target_meta["label"],
                    target_desc=target_meta["description"],
                    rel_type=rel.relationship_type,
                    strength=rel.correlation_strength,
                    desc=rel.dependency_description
                )
                edges_synced += 1
            
            # Count active nodes for this device
            node_result = session.run(
                "MATCH (n:TelemetryMetric {device_id: $device_id}) RETURN count(n) as count",
                device_id=device_id
            )
            nodes_synced = node_result.single()["count"]

        logger.info(f"Neo4j sync completed: {nodes_synced} nodes and {edges_synced} edges processed.")
        return {
            "status": "success",
            "device_id": device_id,
            "nodes_synced": nodes_synced,
            "edges_synced": edges_synced
        }

    except Exception as e:
        logger.error(f"Failed to sync knowledge graph to Neo4j: {str(e)}")
        # Return error mapping, do not crash backend to avoid disrupting core telemetry write loops
        return {
            "status": "error",
            "message": str(e),
            "nodes_synced": 0,
            "edges_synced": 0
        }

def execute_cypher_query(query: str, parameters: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Executes a custom read-only Cypher query and formats the returned nodes/edges.
    """
    driver = get_neo4j_driver()
    if not driver:
        raise Exception("Neo4j driver is not initialized.")

    nodes_dict: Dict[str, Dict[str, Any]] = {}
    edges_list: List[Dict[str, Any]] = []
    raw_rows: List[Dict[str, Any]] = []

    with driver.session() as session:
        # Run inside a read-only transaction for safety
        result = session.execute_read(
            lambda tx: tx.run(query, parameters or {})
        )

        for record in result:
            row_dict = {}
            for key, val in record.items():
                # If val is a Node object
                # Check properties or class attributes
                if hasattr(val, 'labels') and hasattr(val, 'element_id'):
                    node_id = val.get("id")
                    device_id = val.get("device_id")
                    # Unique key to aggregate nodes returned by queries
                    node_key = f"{node_id}:{device_id}" if device_id else node_id
                    
                    nodes_dict[node_key] = {
                        "id": node_id,
                        "label": val.get("label", node_id),
                        "description": val.get("description", ""),
                        "device_id": device_id
                    }
                    row_dict[key] = dict(val)
                # If val is a Relationship object
                elif hasattr(val, 'start_node') and hasattr(val, 'end_node'):
                    # Retrieve nodes if attached
                    start_node = val.nodes[0] if (hasattr(val, 'nodes') and len(val.nodes) >= 2) else None
                    end_node = val.nodes[1] if (hasattr(val, 'nodes') and len(val.nodes) >= 2) else None
                    
                    source_id = val.get("source") or (start_node.get("id") if start_node else None)
                    target_id = val.get("target") or (end_node.get("id") if end_node else None)

                    edge_dict = {
                        "source": source_id,
                        "target": target_id,
                        "relationship_type": val.type,
                        "correlation_strength": val.get("correlation_strength", 0.0),
                        "description": val.get("description", "")
                    }
                    edges_list.append(edge_dict)
                    row_dict[key] = dict(val)
                else:
                    # Basic value (number, string, dict, list)
                    row_dict[key] = val
            raw_rows.append(row_dict)

    # Format output
    return {
        "nodes": list(nodes_dict.values()),
        "edges": edges_list,
        "raw_rows": raw_rows
    }
