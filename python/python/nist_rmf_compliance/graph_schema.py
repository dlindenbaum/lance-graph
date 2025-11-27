"""Graph schema definition for NIST RMF compliance data."""

from __future__ import annotations

from typing import Dict, List, Any
import pyarrow as pa
from knowledge_graph import KnowledgeGraph, KnowledgeGraphBuilder

from .models import (
    Control,
    Requirement,
    Evidence,
    System,
    AssessmentResult,
    ControlImplementation,
)


class RMFGraph:
    """Graph representation of NIST RMF compliance data.

    Nodes:
    - Control: NIST 800-53 controls
    - Requirement: Specific testable requirements
    - Evidence: Supporting documentation and artifacts
    - System: Information systems
    - Assessment: Compliance assessment results
    - Implementation: Control implementations

    Relationships:
    - REQUIRES: Control -> Requirement
    - SUPPORTS: Evidence -> Requirement
    - IMPLEMENTS: System -> Control
    - ASSESSES: Assessment -> Control
    - RELATES_TO: Control -> Control
    - ENHANCES: Control -> Control (for control enhancements)
    """

    def __init__(self, graph: KnowledgeGraph):
        """Initialize with a KnowledgeGraph instance."""
        self.graph = graph

    def query(self, cypher: str) -> pa.Table:
        """Execute a Cypher query against the RMF graph."""
        return self.graph.run(cypher)

    def get_control(self, control_id: str) -> pa.Table:
        """Retrieve a specific control by ID."""
        return self.query(
            f"MATCH (c:Control {{control_id: '{control_id}'}}) RETURN c"
        )

    def get_system_controls(self, system_id: str) -> pa.Table:
        """Get all controls implemented by a system."""
        return self.query(f"""
            MATCH (s:System {{system_id: '{system_id}'}})-[i:IMPLEMENTS]->(c:Control)
            RETURN c.control_id, c.title, c.family, i.implementation_status
        """)

    def get_control_evidence(self, control_id: str) -> pa.Table:
        """Get all evidence supporting a control."""
        return self.query(f"""
            MATCH (c:Control {{control_id: '{control_id}'}})-[:REQUIRES]->(r:Requirement)
            MATCH (e:Evidence)-[:SUPPORTS]->(r)
            RETURN e.evidence_id, e.title, e.evidence_type, e.collected_at, r.requirement_id
        """)

    def get_compliance_status(self, system_id: str) -> pa.Table:
        """Get compliance status for all controls in a system."""
        return self.query(f"""
            MATCH (s:System {{system_id: '{system_id}'}})-[:IMPLEMENTS]->(c:Control)
            MATCH (a:Assessment)-[:ASSESSES]->(c)
            WHERE a.system_id = '{system_id}'
            RETURN c.control_id, c.title, c.family, a.status, a.assessed_at
            ORDER BY c.control_id
        """)

    def get_control_relationships(self, control_id: str) -> pa.Table:
        """Get related controls."""
        return self.query(f"""
            MATCH (c1:Control {{control_id: '{control_id}'}})-[r:RELATES_TO]->(c2:Control)
            RETURN c2.control_id, c2.title, type(r) as relationship_type
        """)

    def find_gaps(self, system_id: str, baseline: str = "MODERATE") -> pa.Table:
        """Find controls without evidence or assessments."""
        return self.query(f"""
            MATCH (c:Control)
            WHERE '{baseline}' IN c.baseline
            OPTIONAL MATCH (s:System {{system_id: '{system_id}'}})-[i:IMPLEMENTS]->(c)
            OPTIONAL MATCH (a:Assessment)-[:ASSESSES]->(c)
            WHERE a.system_id = '{system_id}' AND a.status IN ['Satisfied', 'Inherited']
            WITH c, i, a
            WHERE i IS NULL OR a IS NULL
            RETURN c.control_id, c.title, c.family,
                   CASE WHEN i IS NULL THEN 'Not Implemented' ELSE 'Implemented' END as impl_status,
                   CASE WHEN a IS NULL THEN 'Not Assessed' ELSE a.status END as assessment_status
            ORDER BY c.control_id
        """)


def build_rmf_graph(
    controls: List[Control],
    requirements: List[Requirement],
    evidence: List[Evidence],
    systems: List[System],
    assessments: List[AssessmentResult],
    implementations: List[ControlImplementation],
) -> RMFGraph:
    """Build an RMF knowledge graph from data models.

    Args:
        controls: List of NIST 800-53 controls
        requirements: List of specific requirements
        evidence: List of evidence artifacts
        systems: List of information systems
        assessments: List of assessment results
        implementations: List of control implementations

    Returns:
        RMFGraph instance ready for querying
    """
    # Convert data models to Arrow tables
    controls_table = pa.table({
        "control_id": [c.control_id for c in controls],
        "family": [c.family for c in controls],
        "title": [c.title for c in controls],
        "description": [c.description for c in controls],
        "priority": [c.priority for c in controls],
    })

    requirements_table = pa.table({
        "requirement_id": [r.requirement_id for r in requirements],
        "control_id": [r.control_id for r in requirements],
        "statement": [r.statement for r in requirements],
        "testing_procedure": [r.testing_procedure for r in requirements],
    })

    evidence_table = pa.table({
        "evidence_id": [e.evidence_id for e in evidence],
        "evidence_type": [e.evidence_type.value for e in evidence],
        "title": [e.title for e in evidence],
        "description": [e.description for e in evidence],
        "file_path": [e.file_path or "" for e in evidence],
    })

    systems_table = pa.table({
        "system_id": [s.system_id for s in systems],
        "name": [s.name for s in systems],
        "impact_level": [s.impact_level for s in systems],
        "system_type": [s.system_type for s in systems],
    })

    assessments_table = pa.table({
        "assessment_id": [a.assessment_id for a in assessments],
        "control_id": [a.control_id for a in assessments],
        "system_id": [a.system_id for a in assessments],
        "status": [a.status.value for a in assessments],
        "findings": [a.findings for a in assessments],
        "assessed_at": [a.assessed_at.isoformat() for a in assessments],
    })

    # Build relationships
    # REQUIRES: Control -> Requirement
    requires_rels = pa.table({
        "control_id": [r.control_id for r in requirements],
        "requirement_id": [r.requirement_id for r in requirements],
    })

    # IMPLEMENTS: System -> Control
    implements_rels = pa.table({
        "system_id": [i.system_id for i in implementations],
        "control_id": [i.control_id for i in implementations],
        "implementation_status": [i.implementation_status for i in implementations],
    })

    # ASSESSES: Assessment -> Control
    assesses_rels = pa.table({
        "assessment_id": [a.assessment_id for a in assessments],
        "control_id": [a.control_id for a in assessments],
    })

    # Build the knowledge graph
    builder = KnowledgeGraphBuilder()
    builder.with_node("Control", "control_id", controls_table)
    builder.with_node("Requirement", "requirement_id", requirements_table)
    builder.with_node("Evidence", "evidence_id", evidence_table)
    builder.with_node("System", "system_id", systems_table)
    builder.with_node("Assessment", "assessment_id", assessments_table)

    builder.with_relationship("REQUIRES", "control_id", "requirement_id", requires_rels)
    builder.with_relationship("IMPLEMENTS", "system_id", "control_id", implements_rels)
    builder.with_relationship("ASSESSES", "assessment_id", "control_id", assesses_rels)

    kg = builder.build()
    return RMFGraph(kg)
