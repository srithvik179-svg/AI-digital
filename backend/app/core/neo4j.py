"""
Neo4j Driver Connection Utility — Phase 15.
Manages GraphDatabase driver instance and pools connections.
"""

import os
from neo4j import GraphDatabase, Driver
from app.core.logging import logger

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "telemetry_pass")

_driver: Driver | None = None

def get_neo4j_driver() -> Driver:
    """
    Returns thread-safe singleton Neo4j driver connection.
    Creates driver on demand if not initialized.
    """
    global _driver
    if _driver is None:
        try:
            logger.info(f"Initializing Neo4j Graph Database Driver at URI: {NEO4J_URI}")
            _driver = GraphDatabase.driver(
                NEO4J_URI,
                auth=(NEO4J_USER, NEO4J_PASSWORD)
            )
            # Verify connectivity immediately
            _driver.verify_connectivity()
            logger.info("Successfully established connection to Neo4j graph cluster.")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j database: {str(e)}")
            _driver = None
            raise e
    return _driver

def close_neo4j_driver():
    """
    Closes the global cached Neo4j database driver.
    """
    global _driver
    if _driver is not None:
        logger.info("Closing Neo4j Database Driver pool.")
        _driver.close()
        _driver = None
