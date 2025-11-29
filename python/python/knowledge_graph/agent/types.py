"""Type definitions for graph review agent."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field


class ChangeType(str, Enum):
    """Types of changes that can be proposed."""

    ADD_NODE = "add_node"
    ADD_EDGE = "add_edge"
    MODIFY_NODE = "modify_node"
    DELETE_NODE = "delete_node"
    DELETE_EDGE = "delete_edge"
    MERGE_NODES = "merge_nodes"


class AddNodeChange(BaseModel):
    """Represents adding a new node to the graph."""

    id: str
    type: Literal["add_node"] = "add_node"
    entity: str = Field(..., description="Node type (e.g., Person, Phone, Account)")
    label: str = Field(..., description="Display name for the node")
    properties: Dict[str, Any] = Field(default_factory=dict)
    confidence: int = Field(..., ge=0, le=100, description="Confidence score 0-100")
    evidence: Optional[str] = Field(None, description="Reasoning for this change")
    user_modified: bool = False


class AddEdgeChange(BaseModel):
    """Represents adding a new relationship between nodes."""

    id: str
    type: Literal["add_edge"] = "add_edge"
    from_node: str = Field(..., alias="from", description="Source node label")
    to_node: str = Field(..., alias="to", description="Target node label")
    relationship: str = Field(..., description="Relationship type (e.g., CONTACTED)")
    properties: Optional[Dict[str, Any]] = None
    evidence: Optional[str] = None
    user_modified: bool = False

    class Config:
        populate_by_name = True


class ModifyNodeChange(BaseModel):
    """Represents modifying an existing node."""

    id: str
    type: Literal["modify_node"] = "modify_node"
    entity: str
    label: str
    before: Dict[str, Any] = Field(..., description="Previous property values")
    after: Dict[str, Any] = Field(..., description="New property values")
    confidence: int = Field(..., ge=0, le=100)
    evidence: Optional[str] = None
    user_modified: bool = False


class DeleteNodeChange(BaseModel):
    """Represents deleting a node from the graph."""

    id: str
    type: Literal["delete_node"] = "delete_node"
    entity: str
    label: str
    reason: Optional[str] = None
    user_modified: bool = False


class DeleteEdgeChange(BaseModel):
    """Represents deleting a relationship."""

    id: str
    type: Literal["delete_edge"] = "delete_edge"
    from_node: str = Field(..., alias="from")
    to_node: str = Field(..., alias="to")
    relationship: str
    reason: Optional[str] = None
    user_modified: bool = False

    class Config:
        populate_by_name = True


class MergeNodesChange(BaseModel):
    """Represents merging two nodes into one enriched node."""

    id: str
    type: Literal["merge_nodes"] = "merge_nodes"
    entity: str = Field(..., description="Node type being merged")
    primary_label: str = Field(
        ..., description="Label of the primary node (will be kept)"
    )
    secondary_label: str = Field(
        ..., description="Label of the secondary node (will be merged in)"
    )
    primary_properties: Dict[str, Any] = Field(
        ..., description="Properties from primary node"
    )
    secondary_properties: Dict[str, Any] = Field(
        ..., description="Properties from secondary node"
    )
    merged_properties: Dict[str, Any] = Field(
        ..., description="Combined properties after merge"
    )
    match_confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence that these are the same entity (0-1)"
    )
    matched_rules: List[str] = Field(
        default_factory=list, description="Matching rules that triggered this merge"
    )
    evidence: Optional[str] = Field(None, description="Evidence for this merge")
    requires_review: bool = Field(
        default=True, description="Whether this merge requires manual review"
    )
    user_modified: bool = False


Change = Union[
    AddNodeChange,
    AddEdgeChange,
    ModifyNodeChange,
    DeleteNodeChange,
    DeleteEdgeChange,
    MergeNodesChange,
]


class ProposalStatus(str, Enum):
    """Status of a proposal."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class Proposal(BaseModel):
    """A collection of proposed changes from the agent."""

    id: str
    iteration: int
    status: ProposalStatus = ProposalStatus.PENDING
    summary: str = Field(..., description="Human-readable summary of changes")
    timestamp: str
    changes: List[Change] = Field(default_factory=list)


class Message(BaseModel):
    """A chat message between user and agent."""

    id: str
    role: Literal["user", "agent", "system"]
    content: str
    timestamp: Optional[str] = None


class ChatRequest(BaseModel):
    """Request to send a message to the agent."""

    message: str
    case_id: Optional[str] = None


class ChatResponse(BaseModel):
    """Response from the agent."""

    message: Message
    proposal: Optional[Proposal] = None
