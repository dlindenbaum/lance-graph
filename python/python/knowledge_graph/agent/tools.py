"""Tools for the graph review agent to interact with lance-graph."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List

if TYPE_CHECKING:
    from ..service import LanceKnowledgeGraph


class GraphQueryTool:
    """Tool for querying the graph using Cypher."""

    def __init__(self, service: "LanceKnowledgeGraph"):
        self.service = service

    def execute(self, query: str) -> List[Dict[str, Any]]:
        """Execute a Cypher query and return results."""
        try:
            result = self.service.query(query)
            return result.to_pylist()
        except Exception as e:
            return [{"error": str(e)}]

    def get_schema(self) -> Dict[str, Any]:
        """Get the current graph schema."""
        return {
            "nodes": list(self.service.config.node_labels.keys()),
            "relationships": list(self.service.config.relationships.keys()),
        }

    def search_nodes(self, label: str, **filters: Any) -> List[Dict[str, Any]]:
        """Search for nodes by label and optional property filters."""
        where_clauses = []
        for key, value in filters.items():
            if isinstance(value, str):
                where_clauses.append(f"n.{key} = '{value}'")
            else:
                where_clauses.append(f"n.{key} = {value}")

        where_clause = " AND ".join(where_clauses) if where_clauses else "true"
        query = f"MATCH (n:{label}) WHERE {where_clause} RETURN n LIMIT 100"

        return self.execute(query)

    def get_node_relationships(
        self, label: str, node_id: Any
    ) -> List[Dict[str, Any]]:
        """Get all relationships for a specific node."""
        query = f"""
            MATCH (n:{label})-[r]-(m)
            WHERE id(n) = {node_id}
            RETURN type(r) as relationship, m as connected_node
            LIMIT 100
        """
        return self.execute(query)

    def count_nodes(self, label: str) -> int:
        """Count nodes of a specific label."""
        result = self.execute(f"MATCH (n:{label}) RETURN count(n) as count")
        if result and len(result) > 0:
            return result[0].get("count", 0)
        return 0


class CDRAnalysisTool:
    """Specialized tool for analyzing Call Data Records."""

    def __init__(self, graph_tool: GraphQueryTool):
        self.graph = graph_tool

    def analyze_call_frequency(
        self, phone_number: str
    ) -> List[Dict[str, Any]]:
        """Analyze call frequency for a phone number."""
        query = f"""
            MATCH (p:Phone {{number: '{phone_number}'}})-[r:CONTACTED]-(other:Phone)
            RETURN other.number as contact, count(r) as call_count
            ORDER BY call_count DESC
            LIMIT 20
        """
        return self.graph.execute(query)

    def find_co_located_contacts(
        self, phone_number: str
    ) -> List[Dict[str, Any]]:
        """Find contacts that share locations."""
        query = f"""
            MATCH (p:Phone {{number: '{phone_number}'}})-[:LOCATED_AT]->(loc:Location)
            MATCH (other:Phone)-[:LOCATED_AT]->(loc)
            WHERE p.number <> other.number
            RETURN DISTINCT other.number as contact, loc.address as shared_location
            LIMIT 20
        """
        return self.graph.execute(query)

    def get_phone_owner(self, phone_number: str) -> Dict[str, Any] | None:
        """Look up the owner of a phone number."""
        query = f"""
            MATCH (p:Phone {{number: '{phone_number}'}})-[:OWNED_BY]->(owner:Person)
            RETURN owner
            LIMIT 1
        """
        results = self.graph.execute(query)
        return results[0] if results else None

    def find_common_contacts(
        self, phone1: str, phone2: str
    ) -> List[Dict[str, Any]]:
        """Find common contacts between two phone numbers."""
        query = f"""
            MATCH (p1:Phone {{number: '{phone1}'}})-[:CONTACTED]-(common:Phone)
            MATCH (p2:Phone {{number: '{phone2}'}})-[:CONTACTED]-(common)
            WHERE p1.number <> p2.number AND common.number <> p1.number AND common.number <> p2.number
            RETURN DISTINCT common.number as common_contact
            LIMIT 20
        """
        return self.graph.execute(query)
