"""Data models for NIST RMF compliance tracking."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
import json


class ComplianceStatus(str, Enum):
    """Compliance status values aligned with eMASS."""

    NOT_ASSESSED = "Not Assessed"
    NOT_APPLICABLE = "Not Applicable"
    PLANNED = "Planned"
    IMPLEMENTED = "Implemented"
    INHERITED = "Inherited"
    NOT_SATISFIED = "Not Satisfied"
    PARTIALLY_SATISFIED = "Partially Satisfied"
    SATISFIED = "Satisfied"


class EvidenceType(str, Enum):
    """Types of evidence that can be collected."""

    SCREENSHOT = "Screenshot"
    DOCUMENT = "Document"
    LOG = "Log"
    CONFIGURATION = "Configuration"
    SCAN_RESULT = "Scan Result"
    POLICY = "Policy"
    PROCEDURE = "Procedure"
    ATTESTATION = "Attestation"


class RMFStep(str, Enum):
    """NIST RMF process steps."""

    PREPARE = "Prepare"
    CATEGORIZE = "Categorize"
    SELECT = "Select"
    IMPLEMENT = "Implement"
    ASSESS = "Assess"
    AUTHORIZE = "Authorize"
    MONITOR = "Monitor"


@dataclass
class Control:
    """NIST 800-53 security control."""

    control_id: str  # e.g., "AC-1", "AC-2"
    family: str  # e.g., "Access Control", "Audit and Accountability"
    title: str
    description: str
    baseline: List[str]  # e.g., ["LOW", "MODERATE", "HIGH"]
    priority: str  # P0, P1, P2, P3
    supplemental_guidance: Optional[str] = None
    related_controls: List[str] = field(default_factory=list)
    enhancements: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Arrow table."""
        return {
            "control_id": self.control_id,
            "family": self.family,
            "title": self.title,
            "description": self.description,
            "baseline": json.dumps(self.baseline),
            "priority": self.priority,
            "supplemental_guidance": self.supplemental_guidance or "",
            "related_controls": json.dumps(self.related_controls),
            "enhancements": json.dumps(self.enhancements),
        }


@dataclass
class Requirement:
    """Specific requirement derived from a control."""

    requirement_id: str
    control_id: str
    statement: str
    testing_procedure: str
    expected_evidence: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Arrow table."""
        return {
            "requirement_id": self.requirement_id,
            "control_id": self.control_id,
            "statement": self.statement,
            "testing_procedure": self.testing_procedure,
            "expected_evidence": json.dumps(self.expected_evidence),
        }


@dataclass
class Evidence:
    """Evidence artifact supporting compliance."""

    evidence_id: str
    evidence_type: EvidenceType
    title: str
    description: str
    file_path: Optional[str] = None
    url: Optional[str] = None
    collected_at: Optional[datetime] = None
    collected_by: str = "automated"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Arrow table."""
        return {
            "evidence_id": self.evidence_id,
            "evidence_type": self.evidence_type.value,
            "title": self.title,
            "description": self.description,
            "file_path": self.file_path or "",
            "url": self.url or "",
            "collected_at": self.collected_at.isoformat() if self.collected_at else "",
            "collected_by": self.collected_by,
            "metadata": json.dumps(self.metadata),
        }


@dataclass
class System:
    """Information system being assessed."""

    system_id: str
    name: str
    description: str
    impact_level: str  # LOW, MODERATE, HIGH
    system_type: str  # e.g., "Major Application", "General Support System"
    authorization_boundary: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Arrow table."""
        return {
            "system_id": self.system_id,
            "name": self.name,
            "description": self.description,
            "impact_level": self.impact_level,
            "system_type": self.system_type,
            "authorization_boundary": self.authorization_boundary,
        }


@dataclass
class AssessmentResult:
    """Result of assessing a control or requirement."""

    assessment_id: str
    control_id: str
    requirement_id: Optional[str]
    system_id: str
    status: ComplianceStatus
    findings: str
    recommendations: str
    assessor: str
    assessed_at: datetime
    evidence_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Arrow table."""
        return {
            "assessment_id": self.assessment_id,
            "control_id": self.control_id,
            "requirement_id": self.requirement_id or "",
            "system_id": self.system_id,
            "status": self.status.value,
            "findings": self.findings,
            "recommendations": self.recommendations,
            "assessor": self.assessor,
            "assessed_at": self.assessed_at.isoformat(),
            "evidence_ids": json.dumps(self.evidence_ids),
        }


@dataclass
class ControlImplementation:
    """How a control is implemented in a system."""

    implementation_id: str
    control_id: str
    system_id: str
    implementation_status: str
    implementation_description: str
    responsible_role: str
    implementation_date: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Arrow table."""
        return {
            "implementation_id": self.implementation_id,
            "control_id": self.control_id,
            "system_id": self.system_id,
            "implementation_status": self.implementation_status,
            "implementation_description": self.implementation_description,
            "responsible_role": self.responsible_role,
            "implementation_date": self.implementation_date.isoformat() if self.implementation_date else "",
        }
