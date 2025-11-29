"""Generic data investigation agent with ontology-guided discovery.

This agent is completely domain-agnostic and can work with any type of data.
Entity discovery and graph construction are guided by a configurable ontology.
"""

from __future__ import annotations

import json
import logging
import os
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
from .ontology import GraphOntology, OntologyTemplates
from .tools import GraphQueryTool
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


class DataInvestigationAgent:
    """Generic agent for investigating any type of data with ontology guidance.

    Works with:
    - Any DuckDB database (CDR, taxi, financial, etc.)
    - Any knowledge graph schema
    - Configurable ontologies for different domains
    - Multi-model LLM routing
    """

    def __init__(
        self,
        service: "LanceKnowledgeGraph",
        config: Optional[AgentConfig] = None,
        duckdb_path: Optional[Union[str, Path]] = None,
        ontology: Optional[GraphOntology] = None,
        ontology_path: Optional[Union[str, Path]] = None,
    ):
        self.service = service
        self.config = config or AgentConfig.from_env()
        self.conversation_history: List[Dict[str, str]] = []
        self.iteration_count = 0

        # Set up logging
        logging.basicConfig(level=self.config.log_level)

        # Load ontology
        self.ontology = self._load_ontology(ontology, ontology_path)

        # Initialize graph tools
        self.graph_tool = GraphQueryTool(service)

        # Initialize DuckDB tools if path provided
        self.duckdb_tool: Optional[DuckDBQueryTool] = None
        self.analysis_tool: Optional[DataAnalysisTool] = None
        self.proposal_generator: Optional[NodeProposalGenerator] = None

        if duckdb_path:
            self._setup_duckdb_tools(duckdb_path)

        # Initialize LiteLLM Router
        self._setup_router()

    def _load_ontology(
        self,
        ontology: Optional[GraphOntology],
        ontology_path: Optional[Union[str, Path]],
    ) -> GraphOntology:
        """Load ontology from various sources.

        Supports:
        - Direct ontology object
        - Path to YAML file
        - ONTOLOGY_PATH environment variable
        - ONTOLOGY_DOMAIN environment variable with single or combined domains

        ONTOLOGY_DOMAIN can be:
        - Single domain: "communication", "location", "temporal", "pattern_of_life"
        - Combined: "communication,location" (comma-separated)
        - Legacy: "telecommunications", "transportation", "financial", "generic"
        """
        # 1. Use provided ontology object
        if ontology:
            logger.info(f"Using provided ontology: {ontology.name}")
            return ontology

        # 2. Load from path
        if ontology_path:
            path = Path(ontology_path)
            if path.exists():
                logger.info(f"Loading ontology from: {ontology_path}")
                return GraphOntology.from_yaml(str(ontology_path))

        # 3. Try environment variable for path
        env_path = os.getenv("ONTOLOGY_PATH")
        if env_path and Path(env_path).exists():
            logger.info(f"Loading ontology from ONTOLOGY_PATH: {env_path}")
            return GraphOntology.from_yaml(env_path)

        # 4. Try to infer from domain hint (supports multiple domains)
        domain_str = os.getenv("ONTOLOGY_DOMAIN", "generic").lower()
        domains = [d.strip() for d in domain_str.split(",")]

        # If multiple domains, combine them
        if len(domains) > 1:
            logger.info(f"Combining ontologies: {domains}")
            ontologies_to_combine = []
            for domain in domains:
                ont = self._get_ontology_by_domain(domain)
                if ont:
                    ontologies_to_combine.append(ont)

            if ontologies_to_combine:
                return GraphOntology.combine(*ontologies_to_combine)
            else:
                logger.warning(f"No valid domains found in: {domains}. Using generic.")
                return OntologyTemplates.generic()
        else:
            # Single domain
            domain = domains[0]
            logger.info(f"Using {domain} ontology template")
            ont = self._get_ontology_by_domain(domain)
            return ont if ont else OntologyTemplates.generic()

    def _get_ontology_by_domain(self, domain: str) -> Optional[GraphOntology]:
        """Get ontology template by domain name."""
        # Pattern-of-life ontologies
        if domain == "communication":
            return OntologyTemplates.communication()
        elif domain == "location":
            return OntologyTemplates.location()
        elif domain == "temporal" or domain == "time":
            return OntologyTemplates.temporal()
        elif domain == "pattern_of_life" or domain == "pol":
            return OntologyTemplates.pattern_of_life()
        # Legacy ontologies
        elif domain == "telecommunications":
            return OntologyTemplates.telecommunications()
        elif domain == "transportation":
            return OntologyTemplates.transportation()
        elif domain == "financial":
            return OntologyTemplates.financial()
        elif domain == "generic":
            return OntologyTemplates.generic()
        else:
            logger.warning(f"Unknown domain: {domain}")
            return None

    def _setup_duckdb_tools(self, duckdb_path: Union[str, Path]) -> None:
        """Set up DuckDB tools for data analysis."""
        try:
            self.duckdb_tool = DuckDBQueryTool(duckdb_path, read_only=True)
            self.analysis_tool = DataAnalysisTool(self.duckdb_tool)
            self.proposal_generator = NodeProposalGenerator(
                self.analysis_tool, ontology=self.ontology
            )
            logger.info(f"Connected to DuckDB database: {duckdb_path}")

            # Log available tables
            tables = self.duckdb_tool.get_tables()
            logger.info(f"Available tables: {tables}")

            # Log sample data for schema understanding
            for table in tables[:3]:  # First 3 tables
                sample = self.duckdb_tool.get_sample_data(table, limit=2)
                if sample:
                    logger.debug(f"Sample from {table}: {sample[0] if sample else 'empty'}")

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
        """Get the generic system prompt for any domain."""
        graph_schema = self.graph_tool.get_schema()

        # Build ontology description
        ontology_desc = f"""
=== ONTOLOGY: {self.ontology.name} ===
{self.ontology.description or 'Domain-specific ontology'}

Valid Entity Types:
{chr(10).join(f"- {et.name}: {et.description}" for et in self.ontology.entity_types)}

Valid Relationship Types:
{chr(10).join(f"- {rt.name}: {rt.source_entity_types} → {rt.target_entity_types}" for rt in self.ontology.relationship_types)}

IMPORTANT: All proposed nodes and relationships MUST conform to this ontology.
Only use entity types and relationships defined above.
"""

        duckdb_section = ""
        if self.duckdb_tool:
            tables = self.duckdb_tool.get_tables()
            tables_info = []
            for table in tables[:5]:  # Show first 5 tables
                schema = self.duckdb_tool.get_schema(table)
                cols = [f"{s['column_name']} ({s['data_type']})" for s in schema[:5]]
                tables_info.append(f"  {table}: {', '.join(cols)}")

            duckdb_section = f"""
=== EXTERNAL DATA SOURCES ===
Available Tables: {', '.join(tables)}

Schema Summary:
{chr(10).join(tables_info)}

You can query these tables with SQL to discover entities and relationships.
"""

        return f"""You are a data investigation agent that builds knowledge graphs from various data sources.

Your role is to:
1. Explore and analyze data in external databases (DuckDB)
2. Query existing graph data (Cypher)
3. Discover entities and relationships following a strict ontology
4. Propose new nodes and edges that conform to the ontology
5. Provide evidence and confidence scores

{ontology_desc}

=== KNOWLEDGE GRAPH ===
Current Graph Schema:
- Nodes: {', '.join(graph_schema.get('nodes', []))}
- Relationships: {', '.join(graph_schema.get('relationships', []))}

Graph Tools:
- query_graph(query: str): Execute Cypher queries
- search_nodes(label: str, **filters): Search for existing nodes

{duckdb_section}

=== DATA SOURCE TOOLS ===
Available Tools:
1. sql_query(query: str) - Execute SQL on external data
2. search_data(term: str, tables: list) - Search across tables
3. analyze_patterns(table: str, column: str) - Find frequent values
4. find_correlations(table: str, col1: str, col2: str) - Find correlations
5. temporal_analysis(table: str, timestamp_col: str) - Time patterns
6. detect_anomalies(table: str, column: str) - Statistical outliers
7. propose_nodes(table: str, entity_col: str, type: str, props: list) - Generate nodes
8. propose_relationships(table: str, from: str, to: str, type: str) - Generate edges

=== WORKFLOW ===
1. Start by exploring external data sources with SQL
2. Analyze patterns, correlations, and anomalies
3. Map discovered data to ontology entity types
4. Cross-reference with existing graph to avoid duplicates
5. Propose new nodes with detailed properties
6. Propose relationships based on correlations
7. ALWAYS validate against the ontology

=== RESPONSE FORMAT ===
Structure your response as JSON:
{{
    "message": "Your analysis and findings",
    "proposal": {{
        "summary": "Brief description of what you found",
        "changes": [
            {{
                "type": "add_node",
                "entity": "<EntityType from ontology>",
                "label": "<unique identifier>",
                "properties": {{"key": "value"}},
                "confidence": 85,
                "evidence": "Detailed evidence from data"
            }}
        ]
    }}
}}

Be specific, provide evidence, and ONLY use entity/relationship types from the ontology."""

    def _get_tool_descriptions(self) -> str:
        """Create descriptions of available tools."""
        desc = f"""
=== AVAILABLE TOOLS ===

Graph Tools (Cypher):
1. query_graph(query) - Execute Cypher on knowledge graph
2. search_nodes(label, **filters) - Find existing nodes
"""

        if self.duckdb_tool:
            desc += """
Data Analysis Tools (SQL):
3. sql_query(query) - Execute SQL queries
4. search_data(term, tables) - Search across all tables
5. analyze_patterns(table, column, min_freq) - Find frequent values
6. find_correlations(table, col1, col2) - Detect correlations
7. temporal_analysis(table, timestamp_col, interval) - Time-based patterns
8. detect_anomalies(table, column, threshold) - Statistical outliers

Proposal Generation:
9. propose_nodes(table, entity_col, type, props) - Generate node proposals
10. propose_relationships(table, from_col, to_col, type, source_type, target_type) - Generate edge proposals

Use these tools to discover entities in the data and propose ontology-compliant additions to the graph.
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
                return self.proposal_generator.propose_nodes_from_column(
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
                    kwargs.get("source_type"),
                    kwargs.get("target_type"),
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
        """Get router and system statistics."""
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

        stats["ontology"] = {
            "name": self.ontology.name,
            "entity_types": [et.name for et in self.ontology.entity_types],
            "relationship_types": [rt.name for rt in self.ontology.relationship_types],
        }

        return stats

    def close(self) -> None:
        """Close all connections."""
        if self.duckdb_tool:
            self.duckdb_tool.close()


# Backwards compatibility alias
IntegratedCDRAgent = DataInvestigationAgent
