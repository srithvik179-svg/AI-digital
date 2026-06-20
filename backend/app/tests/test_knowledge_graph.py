"""
Unit tests for Phase 15 Neo4j Knowledge Graph Service.
Validates relationship synchronization, Cypher execution formatting,
and read-only transaction constraints.
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException

from app.services.knowledge_graph import (
    sync_relationships_to_neo4j,
    execute_cypher_query
)
from app.models.relationship import TelemetryRelationship
from app.api.v1.knowledge_graph import query_graph, CypherRequest

class TestKnowledgeGraphService:
    @patch("app.services.knowledge_graph.get_neo4j_driver")
    def test_sync_relationships_with_no_data(self, mock_get_driver):
        """Should skip sync if no relationships exist in PostgreSQL database."""
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []

        res = sync_relationships_to_neo4j("dev-123", db)
        assert res["status"] == "skipped"
        assert res["nodes_synced"] == 0
        assert res["edges_synced"] == 0
        mock_get_driver.assert_not_called()

    @patch("app.services.knowledge_graph.get_neo4j_driver")
    def test_sync_relationships_saves_to_neo4j(self, mock_get_driver):
        """Should query Postgres, parse metadata, clear old graph, and merge nodes/relationships in Neo4j."""
        db = MagicMock()
        mock_relationships = [
            TelemetryRelationship(
                id="rel-1",
                device_id="dev-123",
                source_node="cpu_usage",
                target_node="cpu_temperature",
                relationship_type="thermal_influence",
                correlation_strength=0.85,
                dependency_description="CPU workload heating core"
            )
        ]
        db.query.return_value.filter.return_value.all.return_value = mock_relationships

        # Mock Neo4j driver and session
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_get_driver.return_value = mock_driver
        mock_driver.session.return_value.__enter__.return_value = mock_session

        # Mock return count of active nodes
        mock_node_count_result = MagicMock()
        mock_node_count_result.single.return_value = {"count": 2}
        mock_session.run.side_effect = [
            None,  # Clear delete query
            None,  # MERGE relationship query
            mock_node_count_result  # count query
        ]

        res = sync_relationships_to_neo4j("dev-123", db)

        assert res["status"] == "success"
        assert res["device_id"] == "dev-123"
        assert res["nodes_synced"] == 2
        assert res["edges_synced"] == 1
        
        # Check transaction run matches expected calls
        assert mock_session.run.call_count == 3

    @patch("app.services.knowledge_graph.get_neo4j_driver")
    def test_execute_cypher_query_formatting(self, mock_get_driver):
        """Should execute query and format returned Neo4j nodes/edges into structured lists."""
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_get_driver.return_value = mock_driver
        mock_driver.session.return_value.__enter__.return_value = mock_session

        # Mock Neo4j Node and Relationship objects
        mock_source_node = MagicMock()
        mock_source_node.get.side_effect = lambda key, default=None: {
            "id": "cpu_usage",
            "label": "CPU Usage",
            "description": "CPU utilisation",
            "device_id": "dev-123"
        }.get(key, default)
        # Mock class attributes for check in execute_cypher_query
        mock_source_node.labels = ["TelemetryMetric"]
        mock_source_node.element_id = "node-1"
        mock_source_node.__iter__.return_value = [("id", "cpu_usage"), ("label", "CPU Usage")]

        mock_target_node = MagicMock()
        mock_target_node.get.side_effect = lambda key, default=None: {
            "id": "cpu_temperature",
            "label": "CPU Temp",
            "description": "Processor thermal status",
            "device_id": "dev-123"
        }.get(key, default)
        mock_target_node.labels = ["TelemetryMetric"]
        mock_target_node.element_id = "node-2"

        mock_rel = MagicMock()
        del mock_rel.labels
        del mock_rel.element_id
        mock_rel.type = "INFLUENCES"
        mock_rel.nodes = (mock_source_node, mock_target_node)
        mock_rel.start_node = mock_source_node
        mock_rel.end_node = mock_target_node
        mock_rel.get.side_effect = lambda key, default=None: {
            "source": "cpu_usage",
            "target": "cpu_temperature",
            "correlation_strength": 0.85,
            "description": "thermal connection"
        }.get(key, default)

        # Mock record mapping returned by transaction
        mock_record = MagicMock()
        mock_record.items.return_value = [
            ("n", mock_source_node),
            ("r", mock_rel),
            ("m", mock_target_node)
        ]

        mock_session.execute_read.return_value = [mock_record]

        res = execute_cypher_query("MATCH (n)-[r]->(m) RETURN n,r,m")

        assert "nodes" in res
        assert "edges" in res
        
        # Verify nodes are extracted correctly
        assert len(res["nodes"]) == 2
        assert any(n["id"] == "cpu_usage" for n in res["nodes"])
        assert any(n["id"] == "cpu_temperature" for n in res["nodes"])

        # Verify edges are parsed correctly
        assert len(res["edges"]) == 1
        assert res["edges"][0]["source"] == "cpu_usage"
        assert res["edges"][0]["target"] == "cpu_temperature"
        assert res["edges"][0]["relationship_type"] == "INFLUENCES"
        assert res["edges"][0]["correlation_strength"] == 0.85


class TestKnowledgeGraphRouterSafety:
    def test_write_queries_are_blocked(self):
        """FastAPI route should reject custom Cypher queries containing mutating commands like MERGE, CREATE, etc."""
        mutating_queries = [
            "CREATE (n:Test {id: '123'})",
            "MATCH (n) DETACH DELETE n",
            "MERGE (n:Metric {id: 'cpu'})",
            "MATCH (n) SET n.label = 'new'",
            "DROP CONSTRAINT my_constraint"
        ]

        for q in mutating_queries:
            req = CypherRequest(query=q, device_id="dev-123")
            with pytest.raises(HTTPException) as exc_info:
                query_graph(req)
            assert exc_info.value.status_code == 400
            assert "Writing or modifying operations are prohibited" in exc_info.value.detail
