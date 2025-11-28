"""Integrated CDR Investigation Agent with DuckDB data source support."""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from litellm import Router

from .config import AgentConfig
from .duckdb_tools import (
    DataAnalysisTool,
    DuckDBQueryTool,
    NodeProposalGenerator,
)
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

logger = logging.getLogger(__name__)


class IntegratedCDRAgent:
    """Integrated agent with both graph and DuckDB data source capabilities.

    Combines:
    - Graph query tools (lance-graph via Cypher)
    - DuckDB SQL query tools for external data sources
    - Data analysis and pattern detection
    - Automatic node proposal generation
    """

    def __init__(
        self,
        service: "LanceKnowledgeGraph",
        config: Optional[AgentConfig] = None,
        duckdb_path: Optional[Union[str, Path]] = None,
    ):
        self.service = service
        self.config = config or AgentConfig.from_env()
        self.conversation_history: List[Dict[str, str]] = []
        self.iteration_count = 0

        # Set up logging
        logging.basicConfig(level=self.config.log_level)

        # Initialize graph tools
        self.graph_tool = GraphQueryTool(service)
        self.cdr_tool = CDRAnalysisTool(self.graph_tool)

        # Initialize DuckDB tools if path provided
        self.duckdb_tool: Optional[DuckDBQueryTool] = None
        self.analysis_tool: Optional[DataAnalysisTool] = None
        self.proposal_generator: Optional[NodeProposalGenerator] = None

        if duckdb_path:
            self._setup_duckdb_tools(duckdb_path)

        # Initialize LiteLLM Router
        self._setup_router()

    def _setup_duckdb_tools(self, duckdb_path: Union[str, Path]) -> None:
        """Set up DuckDB tools for data analysis."""
        try:
            self.duckdb_tool = DuckDBQueryTool(duckdb_path, read_only=True)
            self.analysis_tool = DataAnalysisTool(self.duckdb_tool)
            self.proposal_generator = NodeProposalGenerator(self.analysis_tool)
            logger.info(f"Connected to DuckDB database: {duckdb_path}")

            # Log available tables
            tables = self.duckdb_tool.get_tables()
            logger.info(f"Available tables: {tables}")
        except Exception as e:
            logger.error(f"Failed to initialize DuckDB tools: {e}")
            self.duckdb_tool = None

    def _setup_router(self) -> None:
        """Set up the LiteLLM router with configured models."""
        if not self.config.router.models:
            logger.warning("No models configured, using default GPT-4o-mini")
            self.router = None
            self.fallback_model = "gpt-4o-mini"
            return

        try:
            model_list = []
            for model_config in self.config.router.models:
                model_list.append(
                    {
                        "model_name": model_config.model_name,
                        "litellm_params": {
                            "model": model_config.model_name,
                            **model_config.litellm_params,
                        },
                        "model_info": model_config.model_info,
                    }
                )

            self.router = Router(
                model_list=model_list,
                routing_strategy=self.config.router.routing_strategy,
                num_retries=self.config.router.retry_policy.get("num_retries", 2),
                timeout=self.config.router.retry_policy.get("timeout", 30),
                fallbacks=self.config.router.fallbacks,
                set_verbose=self.config.log_level == "DEBUG",
            )

            logger.info(
                f"Initialized LiteLLM Router with {len(model_list)} models: "
                f"{[m['model_name'] for m in model_list]}"
            )
        except Exception as e:
            logger.error(f"Failed to initialize router: {e}")
            self.router = None
            self.fallback_model = "gpt-4o-mini"

    def _get_system_prompt(self) -> str:
        """Get the comprehensive system prompt for the agent."""
        duckdb_section = ""
        if self.duckdb_tool:
            tables = self.duckdb_tool.get_tables()
            duckdb_section = f"""
DuckDB Data Sources:
You have access to external data in DuckDB tables: {', '.join(tables)}

DuckDB Tools Available:
- sql_query(query): Execute SQL queries on DuckDB tables
- search_data(term, tables): Search for a term across tables
- analyze_patterns(table, column): Find frequent patterns in data
- find_correlations(table, col1, col2): Find correlations between columns
- temporal_analysis(table, timestamp_col): Analyze time-based patterns
- detect_anomalies(table, column): Find statistical anomalies
- propose_nodes_from_table(table, entity_col, entity_type, properties): Generate node proposals
- propose_relationships(table, from_col, to_col, rel_type): Generate relationship proposals

Use these tools to discover new entities and relationships from external data sources.
"""

        return f"""You are a CDR (Call Data Record) investigation agent with access to both a knowledge graph and external data sources.

Your role is to:
1. Query and analyze existing graph data using Cypher
2. Search and analyze external data sources using SQL (DuckDB)
3. Find patterns, correlations, and anomalies in the data
4. Propose new nodes and relationships to add to the knowledge graph
5. Provide evidence and confidence scores for all proposals

Graph Tools Available:
- query_graph(query): Execute Cypher queries on the knowledge graph
- search_nodes(label, **filters): Search for nodes
- analyze_call_frequency(phone): Analyze CDR call patterns
- find_co_located_contacts(phone): Find contacts at same locations
- get_phone_owner(phone): Look up phone owner

{duckdb_section}

When analyzing data and proposing changes:
1. Start by querying external data sources to discover new entities
2. Analyze patterns and correlations in the data
3. Cross-reference with existing graph data to avoid duplicates
4. Propose nodes with detailed properties extracted from the data
5. Propose relationships based on co-occurrence and correlation analysis
6. Always provide evidence and confidence scores (0-100)

Structure your response as JSON:
{{
    "message": "Your analysis and findings",
    "proposal": {{
        "summary": "Brief description of what you found",
        "changes": [
            {{
                "type": "add_node",
                "entity": "Phone",
                "label": "555-1234",
                "properties": {{"carrier": "Verizon", "calls": 47}},
                "confidence": 85,
                "evidence": "Found 47 call records in cdr_data table"
            }}
        ]
    }}
}}

Be specific, provide detailed evidence from the data, and assign confidence scores based on data quality and frequency."""

    def _get_tool_descriptions(self) -> str:
        """Create descriptions of available tools."""
        graph_schema = self.graph_tool.get_schema()

        desc = f"""
=== KNOWLEDGE GRAPH TOOLS ===
Current Graph Schema:
- Nodes: {', '.join(graph_schema.get('nodes', []))}
- Relationships: {', '.join(graph_schema.get('relationships', []))}

Available Graph Tools:
1. query_graph(query: str) - Execute Cypher queries
2. search_nodes(label: str, **filters) - Search for nodes
3. analyze_call_frequency(phone: str) - Analyze call patterns
4. find_co_located_contacts(phone: str) - Find contacts at same location
5. get_phone_owner(phone: str) - Look up phone owner
"""

        if self.duckdb_tool:
            tables = self.duckdb_tool.get_tables()
            desc += f"""
=== DUCKDB DATA SOURCE TOOLS ===
Available Tables: {', '.join(tables)}

Table Schemas:
"""
            for table in tables[:5]:  # Show first 5 tables
                schema = self.duckdb_tool.get_schema(table)
                cols = [f"{s['column_name']} ({s['data_type']})" for s in schema[:5]]
                desc += f"\n{table}: {', '.join(cols)}"

            desc += """

Available DuckDB Tools:
1. sql_query(query: str) - Execute SQL on DuckDB tables
2. search_data(term: str, tables: list) - Search across tables
3. analyze_patterns(table: str, column: str, min_freq: int) - Find frequent values
4. find_correlations(table: str, col1: str, col2: str) - Find correlations
5. temporal_analysis(table: str, timestamp_col: str) - Time-based patterns
6. detect_anomalies(table: str, column: str) - Find outliers
7. propose_nodes(table: str, entity_col: str, type: str, props: list) - Generate nodes
8. propose_relationships(table: str, from: str, to: str, type: str) - Generate edges

Use SQL tools to discover new entities, then propose them as graph nodes.
"""

        return desc

    def _execute_tool(self, tool_name: str, **kwargs: Any) -> Any:
        """Execute a tool and return results."""
        try:
            # Graph tools
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

            # DuckDB tools
            elif tool_name == "sql_query" and self.duckdb_tool:
                return self.duckdb_tool.execute_query(kwargs.get("query", ""))
            elif tool_name == "search_data" and self.duckdb_tool:
                return self.duckdb_tool.search_across_tables(
                    kwargs.get("term", ""), kwargs.get("tables")
                )
            elif tool_name == "analyze_patterns" and self.analysis_tool:
                return self.analysis_tool.find_frequent_patterns(
                    kwargs.get("table", ""),
                    kwargs.get("column", ""),
                    kwargs.get("min_freq", 5),
                )
            elif tool_name == "find_correlations" and self.analysis_tool:
                return self.analysis_tool.find_correlations(
                    kwargs.get("table", ""),
                    kwargs.get("col1", ""),
                    kwargs.get("col2", ""),
                )
            elif tool_name == "temporal_analysis" and self.analysis_tool:
                return self.analysis_tool.temporal_analysis(
                    kwargs.get("table", ""),
                    kwargs.get("timestamp_col", ""),
                    kwargs.get("interval", "day"),
                )
            elif tool_name == "detect_anomalies" and self.analysis_tool:
                return self.analysis_tool.detect_anomalies(
                    kwargs.get("table", ""),
                    kwargs.get("column", ""),
                    kwargs.get("threshold", 3.0),
                )
            elif tool_name == "propose_nodes" and self.proposal_generator:
                return self.proposal_generator.propose_nodes_from_entities(
                    kwargs.get("table", ""),
                    kwargs.get("entity_col", ""),
                    kwargs.get("type", "Entity"),
                    kwargs.get("props"),
                )
            elif tool_name == "propose_relationships" and self.proposal_generator:
                return self.proposal_generator.propose_relationships_from_correlation(
                    kwargs.get("table", ""),
                    kwargs.get("from_col", ""),
                    kwargs.get("to_col", ""),
                    kwargs.get("rel_type", "RELATED"),
                )
            else:
                return {"error": f"Unknown tool: {tool_name}"}

        except Exception as e:
            logger.error(f"Tool execution error in {tool_name}: {e}")
            return {"error": str(e)}

    async def process_message(
        self,
        user_message: str,
        case_id: Optional[str] = None,
        model_override: Optional[str] = None,
    ) -> ChatResponse:
        """Process a user message and generate a response with optional proposal."""
        # Add user message to history
        self.conversation_history.append({"role": "user", "content": user_message})

        # Prepare messages for LLM
        messages = [
            {"role": "system", "content": self._get_system_prompt()},
            {"role": "system", "content": self._get_tool_descriptions()},
        ] + self.conversation_history

        try:
            # Use router if available
            if self.router and not model_override:
                logger.info(
                    f"Using router with strategy: {self.config.router.routing_strategy}"
                )
                response = await self.router.acompletion(
                    model=self.config.router.models[0].model_name,
                    messages=messages,
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                )
            else:
                import litellm

                model = model_override or getattr(self, "fallback_model", "gpt-4o-mini")
                logger.info(f"Using fallback model: {model}")
                response = await litellm.acompletion(
                    model=model,
                    messages=messages,
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                )

            assistant_message = response.choices[0].message.content

            # Log usage stats
            if hasattr(response, "usage"):
                logger.info(f"Token usage: {response.usage}")

            # Add to conversation history
            self.conversation_history.append(
                {"role": "assistant", "content": assistant_message}
            )

            # Try to parse proposal
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
            logger.error(f"Error processing message: {e}", exc_info=True)
            error_message = Message(
                id=f"msg-{uuid.uuid4()}",
                role="system",
                content=f"Error communicating with agent: {str(e)}",
                timestamp="Just now",
            )
            return ChatResponse(message=error_message)

    def _extract_message_content(self, response: str) -> str:
        """Extract the message content from the response."""
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
            data = json.loads(response)

            if not isinstance(data, dict) or "proposal" not in data:
                return None

            proposal_data = data["proposal"]
            if not isinstance(proposal_data, dict):
                return None

            self.iteration_count += 1

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
        except Exception as e:
            logger.error(f"Error parsing proposal: {e}")
            return None

    def reset_conversation(self) -> None:
        """Reset the conversation history."""
        self.conversation_history = []
        self.iteration_count = 0

    def get_router_stats(self) -> Dict[str, Any]:
        """Get router statistics if available."""
        stats = {}

        if self.router:
            stats["router"] = {
                "models": [m.model_name for m in self.config.router.models],
                "routing_strategy": self.config.router.routing_strategy,
                "fallbacks_configured": len(self.config.router.fallbacks) > 0,
            }
        else:
            stats["router"] = {"error": "Router not initialized"}

        if self.duckdb_tool:
            stats["duckdb"] = {
                "connected": True,
                "tables": self.duckdb_tool.get_tables(),
            }
        else:
            stats["duckdb"] = {"connected": False}

        return stats

    def close(self) -> None:
        """Close all connections."""
        if self.duckdb_tool:
            self.duckdb_tool.close()
