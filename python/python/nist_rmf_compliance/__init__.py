"""NIST RMF Compliance Tool powered by lance-graph and Claude agents.

This package provides a comprehensive solution for evaluating and documenting
compliance with NIST 800-53 Risk Management Framework (RMF) requirements.

Key features:
- Graph-based modeling of controls, requirements, and evidence
- Automated compliance evaluation using Claude agents
- Evidence gathering with screenshot capture
- Visualization of compliance relationships
- eMASS package generation
"""

from __future__ import annotations

from .models import (
    Control,
    Requirement,
    Evidence,
    System,
    ComplianceStatus,
    AssessmentResult,
)
from .graph_schema import RMFGraph, build_rmf_graph
from .compliance_engine import ComplianceEngine
from .evidence_gatherer import EvidenceGatherer
from .visualization import ComplianceVisualizer

__version__ = "0.1.0"

__all__ = [
    "Control",
    "Requirement",
    "Evidence",
    "System",
    "ComplianceStatus",
    "AssessmentResult",
    "RMFGraph",
    "build_rmf_graph",
    "ComplianceEngine",
    "EvidenceGatherer",
    "ComplianceVisualizer",
]
