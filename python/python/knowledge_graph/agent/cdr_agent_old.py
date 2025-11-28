"""CDR Investigation Agent using LiteLLM for LLM integration."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import litellm

from .tools import CDRAnalysisTool, GraphQueryTool
from .types import (
    AddEdgeChange,
    AddNodeChange,
    ChatResponse,
    Message,
    Proposal,
    ProposalStatus,
)

if TYPE_CHECKING:
    from ..service import LanceKnowledgeGraph


class CDRInvestigationAgent:
    """Agent for investigating Call Data Records using LiteLLM."""

    def __init__(
        self,
        service: "LanceKnowledgeGraph",
        model: str = "gpt-4o-mini",
        temperature: float = 0.7,
    ):
        self.service = service
        self.model = model
        self.temperature = temperature
        self.graph_tool = GraphQueryTool(service)
        self.cdr_tool = CDRAnalysisTool(self.graph_tool)
        self.conversation_history: List[Dict[str, str]] = []
        self.iteration_count = 0

        # Configure LiteLLM
        litellm.set_verbose = False

    def _get_system_prompt(self) -> str:
        """Get the system prompt for the agent."""
        return """You are a CDR (Call Data Record) investigation agent. Your role is to analyze phone call patterns,
identify relationships, and propose changes to a knowledge graph.

When the user asks you to investigate, you should:
1. Query the existing graph data using available tools
2. Analyze patterns and relationships
3. Propose new nodes (phones, people, locations) or edges (relationships) to add to the graph
4. Always provide evidence and confidence scores for your proposals

Available tools:
- query_graph(query: str): Execute Cypher queries
- search_nodes(label: str, **filters): Search for nodes
- analyze_call_frequency(phone_number: str): Get call frequency analysis
- find_co_located_contacts(phone_number: str): Find contacts at same locations
- get_phone_owner(phone_number: str): Look up phone owner

When proposing changes, structure your response as:
{
    "message": "Your analysis and findings",
    "proposal": {
        "summary": "Brief description of what you found",
        "changes": [
            {
                "type": "add_node",
                "entity": "Phone",
                "label": "555-1234",
                "properties": {"calls": 47, "pattern": "Daily morning"},
                "confidence": 85,
                "evidence": "Found in CDR frequency analysis with 47 calls over 90 days"
            }
        ]
    }
}

Always be specific, provide evidence, and assign confidence scores based on data quality."""

    def _create_tool_descriptions(self) -> str:
        """Create descriptions of available tools."""
        return """
Available Analysis Tools:
1. query_graph(query) - Execute Cypher queries on the graph
2. search_nodes(label, **filters) - Search for nodes by label and properties
3. analyze_call_frequency(phone) - Analyze call patterns for a phone number
4. find_co_located_contacts(phone) - Find contacts sharing locations
5. get_phone_owner(phone) - Look up the owner of a phone number

Current Graph Schema:
- Nodes: Person, Phone, Location, Account
- Relationships: CONTACTED, OWNED_BY, LOCATED_AT
"""

    def _execute_tool(self, tool_name: str, **kwargs: Any) -> Any:
        """Execute a tool and return results."""
        try:
            if tool_name == "query_graph":
                return self.graph_tool.execute(kwargs.get("query", ""))
            elif tool_name == "search_nodes":
                label = kwargs.pop("label", "")
                return self.graph_tool.search_nodes(label, **kwargs)
            elif tool_name == "analyze_call_frequency":
                return self.cdr_tool.analyze_call_frequency(
                    kwargs.get("phone_number", "")
                )
            elif tool_name == "find_co_located_contacts":
                return self.cdr_tool.find_co_located_contacts(
                    kwargs.get("phone_number", "")
                )
            elif tool_name == "get_phone_owner":
                return self.cdr_tool.get_phone_owner(kwargs.get("phone_number", ""))
            else:
                return {"error": f"Unknown tool: {tool_name}"}
        except Exception as e:
            return {"error": str(e)}

    async def process_message(
        self, user_message: str, case_id: Optional[str] = None
    ) -> ChatResponse:
        """Process a user message and generate a response with optional proposal."""
        # Add user message to history
        self.conversation_history.append({"role": "user", "content": user_message})

        # Prepare messages for LLM
        messages = [
            {"role": "system", "content": self._get_system_prompt()},
            {"role": "system", "content": self._create_tool_descriptions()},
        ] + self.conversation_history

        try:
            # Call LLM using LiteLLM
            response = await litellm.acompletion(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=2000,
            )

            assistant_message = response.choices[0].message.content

            # Add to conversation history
            self.conversation_history.append(
                {"role": "assistant", "content": assistant_message}
            )

            # Try to parse if the response contains a structured proposal
            proposal = self._try_parse_proposal(assistant_message)

            # Create response message
            message = Message(
                id=f"msg-{uuid.uuid4()}",
                role="agent",
                content=self._extract_message_content(assistant_message),
                timestamp="Just now",
            )

            return ChatResponse(message=message, proposal=proposal)

        except Exception as e:
            # Return error message
            error_message = Message(
                id=f"msg-{uuid.uuid4()}",
                role="system",
                content=f"Error communicating with agent: {str(e)}",
                timestamp="Just now",
            )
            return ChatResponse(message=error_message)

    def _extract_message_content(self, response: str) -> str:
        """Extract the message content from the response."""
        # If response contains JSON, extract the message field
        try:
            data = json.loads(response)
            if isinstance(data, dict) and "message" in data:
                return data["message"]
        except json.JSONDecodeError:
            pass
        return response

    def _try_parse_proposal(self, response: str) -> Optional[Proposal]:
        """Try to parse a proposal from the agent response."""
        try:
            # Try to parse JSON from the response
            data = json.loads(response)

            if not isinstance(data, dict) or "proposal" not in data:
                return None

            proposal_data = data["proposal"]
            if not isinstance(proposal_data, dict):
                return None

            self.iteration_count += 1

            # Create proposal
            proposal = Proposal(
                id=f"p-{uuid.uuid4()}",
                iteration=self.iteration_count,
                status=ProposalStatus.PENDING,
                summary=proposal_data.get("summary", "Agent proposal"),
                timestamp="Just now",
                changes=[],
            )

            # Parse changes
            for change_data in proposal_data.get("changes", []):
                change_id = f"c-{uuid.uuid4()}"
                change_type = change_data.get("type")

                if change_type == "add_node":
                    proposal.changes.append(
                        AddNodeChange(
                            id=change_id,
                            entity=change_data.get("entity", "Unknown"),
                            label=change_data.get("label", ""),
                            properties=change_data.get("properties", {}),
                            confidence=change_data.get("confidence", 50),
                            evidence=change_data.get("evidence"),
                        )
                    )
                elif change_type == "add_edge":
                    proposal.changes.append(
                        AddEdgeChange(
                            id=change_id,
                            from_node=change_data.get("from", ""),
                            to_node=change_data.get("to", ""),
                            relationship=change_data.get("relationship", "RELATED"),
                            properties=change_data.get("properties"),
                            evidence=change_data.get("evidence"),
                        )
                    )

            return proposal if proposal.changes else None

        except json.JSONDecodeError:
            return None
        except Exception:
            return None

    def reset_conversation(self) -> None:
        """Reset the conversation history."""
        self.conversation_history = []
        self.iteration_count = 0
