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
    MergeNodesChange,
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
                self.analysis_tool,
                ontology=self.ontology,
                graph_tool=self.graph_tool,
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

        return f"""You are an intelligence analysis agent that builds knowledge graphs by discovering entities and relationships in data.

{ontology_desc}

=== CURRENT GRAPH ===
Node Types: {', '.join(graph_schema.get('nodes', [])) or 'Empty graph'}
Relationships: {', '.join(graph_schema.get('relationships', [])) or 'None yet'}

{duckdb_section}

=== WORKFLOW ===
1. Use tools to explore and analyze data sources
2. Search the graph for existing entities before proposing new ones
3. Propose merge_nodes when similar entities exist (the propose_nodes tool does this automatically)
4. Ensure all proposals conform to the ontology
5. Provide clear evidence and confidence scores

=== RESPONSE FORMAT ===
When you're done with your investigation, respond with JSON:
{{
    "message": "Clear explanation of what you discovered",
    "proposal": {{
        "summary": "Brief summary of proposed changes",
        "changes": [
            {{
                "type": "add_node",
                "entity": "Person",
                "label": "John Smith",
                "properties": {{"phone": "555-1234"}},
                "confidence": 85,
                "evidence": "Found in call records"
            }},
            {{
                "type": "merge_nodes",
                "entity": "Person",
                "primaryLabel": "John Smith",
                "secondaryLabel": "J. Smith",
                "primaryProperties": {{"name": "John Smith", "phone": "555-1234"}},
                "secondaryProperties": {{"name": "J. Smith", "email": "john@example.com"}},
                "mergedProperties": {{"name": ["John Smith", "J. Smith"], "phone": "555-1234", "email": "john@example.com"}},
                "matchConfidence": 0.92,
                "matchedRules": ["name+address (normalized)"],
                "evidence": "Matched with 92% confidence",
                "requiresReview": true
            }},
            {{
                "type": "add_edge",
                "from": "John Smith",
                "to": "555-1234",
                "relationship": "USES_PHONE",
                "properties": {{"first_seen": "2023-01-01"}},
                "evidence": "15 calls in January 2023"
            }}
        ]
    }}
}}

IMPORTANT:
- Only use entity/relationship types from the ontology
- When propose_nodes finds matches, include the merge suggestions it returns
- Provide clear evidence for all proposed changes"""

    def _get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Get tool definitions in OpenAI function calling format."""
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "query_graph",
                    "description": "Execute a Cypher query on the knowledge graph to find existing nodes and relationships",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Cypher query to execute (e.g., 'MATCH (p:Person) RETURN p LIMIT 10')",
                            }
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "search_nodes",
                    "description": "Search for existing nodes in the graph by label and property filters",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "label": {
                                "type": "string",
                                "description": "Node label/type to search for (e.g., 'Person', 'Phone')",
                            },
                            "filters": {
                                "type": "object",
                                "description": "Property filters as key-value pairs (e.g., {'name': 'John'})",
                                "additionalProperties": True,
                            },
                        },
                        "required": ["label"],
                    },
                },
            },
        ]

        if self.duckdb_tool:
            tools.extend([
                {
                    "type": "function",
                    "function": {
                        "name": "sql_query",
                        "description": "Execute a SQL query on the external DuckDB database to analyze data",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "SQL query to execute (e.g., 'SELECT * FROM calls LIMIT 10')",
                                }
                            },
                            "required": ["query"],
                        },
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "search_data",
                        "description": "Search for a term across multiple tables in the database",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "term": {
                                    "type": "string",
                                    "description": "Search term (phone number, name, etc.)",
                                },
                                "tables": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "List of table names to search, or null for all tables",
                                },
                            },
                            "required": ["term"],
                        },
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "analyze_patterns",
                        "description": "Find frequent values/patterns in a column for entity discovery",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "table": {"type": "string", "description": "Table name"},
                                "column": {"type": "string", "description": "Column to analyze"},
                                "min_freq": {
                                    "type": "integer",
                                    "description": "Minimum frequency threshold (default: 5)",
                                    "default": 5,
                                },
                            },
                            "required": ["table", "column"],
                        },
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "propose_nodes",
                        "description": "Generate node proposals from a database column. Automatically checks for duplicates and suggests merges.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "table": {"type": "string", "description": "Table name"},
                                "entity_col": {
                                    "type": "string",
                                    "description": "Column containing entity identifiers (labels)",
                                },
                                "type": {
                                    "type": "string",
                                    "description": "Entity type from ontology (e.g., 'Person', 'Phone')",
                                },
                                "props": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Additional columns to include as properties",
                                },
                            },
                            "required": ["table", "entity_col", "type"],
                        },
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "propose_relationships",
                        "description": "Generate relationship proposals from database correlations",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "table": {"type": "string", "description": "Table name"},
                                "from_col": {
                                    "type": "string",
                                    "description": "Column containing source node labels",
                                },
                                "to_col": {
                                    "type": "string",
                                    "description": "Column containing target node labels",
                                },
                                "rel_type": {
                                    "type": "string",
                                    "description": "Relationship type from ontology (e.g., 'CALLED', 'LIVES_AT')",
                                },
                                "source_type": {
                                    "type": "string",
                                    "description": "Source entity type (e.g., 'Person')",
                                },
                                "target_type": {
                                    "type": "string",
                                    "description": "Target entity type (e.g., 'Phone')",
                                },
                            },
                            "required": ["table", "from_col", "to_col", "rel_type"],
                        },
                    },
                },
            ])

        return tools

    def _execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a tool and return results.

        Args:
            tool_name: Name of the tool to execute
            arguments: Dictionary of arguments from the LLM's tool call

        Returns:
            Tool execution result (will be serialized to JSON for LLM)
        """
        try:
            logger.info(f"Executing tool: {tool_name} with args: {arguments}")

            # Graph tools
            if tool_name == "query_graph":
                result = self.graph_tool.execute(arguments.get("query", ""))
                return {"success": True, "result": result}

            elif tool_name == "search_nodes":
                label = arguments.get("label", "")
                filters = arguments.get("filters", {})
                result = self.graph_tool.search_nodes(label, **filters)
                return {"success": True, "result": result}

            # DuckDB tools
            elif tool_name == "sql_query" and self.duckdb_tool:
                result = self.duckdb_tool.execute_query(arguments.get("query", ""))
                return {"success": True, "result": result}

            elif tool_name == "search_data" and self.duckdb_tool:
                result = self.duckdb_tool.search_across_tables(
                    arguments.get("term", ""),
                    arguments.get("tables")
                )
                return {"success": True, "result": result}

            elif tool_name == "analyze_patterns" and self.analysis_tool:
                result = self.analysis_tool.find_frequent_patterns(
                    arguments.get("table", ""),
                    arguments.get("column", ""),
                    arguments.get("min_freq", 5),
                )
                return {"success": True, "result": result}

            elif tool_name == "propose_nodes" and self.proposal_generator:
                result = self.proposal_generator.propose_nodes_from_column(
                    arguments.get("table", ""),
                    arguments.get("entity_col", ""),
                    arguments.get("type", "Entity"),
                    arguments.get("props"),
                )
                return {"success": True, "proposals": result}

            elif tool_name == "propose_relationships" and self.proposal_generator:
                result = self.proposal_generator.propose_relationships_from_correlation(
                    arguments.get("table", ""),
                    arguments.get("from_col", ""),
                    arguments.get("to_col", ""),
                    arguments.get("rel_type", "RELATED"),
                    arguments.get("source_type"),
                    arguments.get("target_type"),
                )
                return {"success": True, "proposals": result}

            else:
                return {"success": False, "error": f"Unknown tool: {tool_name}"}

        except Exception as e:
            logger.error(f"Tool execution error in {tool_name}: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def _get_response_schema(self) -> Dict[str, Any]:
        """Get JSON schema for structured output."""
        return {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "Your analysis and findings to show the user"
                },
                "proposal": {
                    "type": "object",
                    "description": "Optional proposal with graph changes",
                    "properties": {
                        "summary": {
                            "type": "string",
                            "description": "Brief summary of proposed changes"
                        },
                        "changes": {
                            "type": "array",
                            "description": "List of proposed changes to the graph",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "type": {
                                        "type": "string",
                                        "enum": ["add_node", "add_edge", "merge_nodes"]
                                    }
                                },
                                "required": ["type"]
                            }
                        }
                    },
                    "required": ["summary", "changes"]
                }
            },
            "required": ["message"]
        }

    async def process_message(
        self,
        user_message: str,
        case_id: Optional[str] = None,
        model_override: Optional[str] = None,
    ) -> ChatResponse:
        """Process a user message with native tool calling and structured output."""
        # Add user message to history
        self.conversation_history.append({"role": "user", "content": user_message})

        # Prepare messages for LLM (simplified prompt for tool calling)
        messages = [
            {"role": "system", "content": self._get_system_prompt()},
        ] + self.conversation_history

        tools = self._get_tool_schemas()
        max_iterations = 10  # Prevent infinite loops
        iteration = 0

        try:
            import litellm

            model = (
                model_override or
                (self.config.router.models[0].model_name if self.router else "gpt-4o-mini")
            )
            logger.info(f"Using model: {model} with native tool calling")

            # Tool calling loop
            while iteration < max_iterations:
                iteration += 1
                logger.info(f"Tool calling iteration {iteration}")

                # Make LLM call with tools
                if self.router and not model_override:
                    response = await self.router.acompletion(
                        model=model,
                        messages=messages,
                        tools=tools,
                        temperature=self.config.temperature,
                        max_tokens=self.config.max_tokens,
                    )
                else:
                    response = await litellm.acompletion(
                        model=model,
                        messages=messages,
                        tools=tools,
                        temperature=self.config.temperature,
                        max_tokens=self.config.max_tokens,
                    )

                assistant_message = response.choices[0].message

                # Log usage
                if hasattr(response, "usage"):
                    logger.info(f"Token usage: {response.usage}")

                # Check if LLM wants to call tools
                if assistant_message.tool_calls:
                    logger.info(f"LLM requested {len(assistant_message.tool_calls)} tool calls")

                    # Add assistant message with tool calls to history
                    messages.append({
                        "role": "assistant",
                        "content": assistant_message.content,
                        "tool_calls": assistant_message.tool_calls,
                    })

                    # Execute each tool call
                    for tool_call in assistant_message.tool_calls:
                        tool_name = tool_call.function.name

                        # Parse arguments (comes as JSON string)
                        try:
                            arguments = json.loads(tool_call.function.arguments)
                        except json.JSONDecodeError:
                            arguments = {}
                            logger.error(f"Failed to parse tool arguments: {tool_call.function.arguments}")

                        # Execute tool
                        result = self._execute_tool(tool_name, arguments)

                        # Add tool result to messages
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": tool_name,
                            "content": json.dumps(result),
                        })

                    # Continue loop to get next LLM response
                    continue

                else:
                    # No more tool calls - this is the final response
                    logger.info("LLM provided final response without tool calls")

                    # Get final response with structured output
                    final_content = assistant_message.content or ""

                    # Try to get structured response if model supports it
                    try:
                        # Request structured JSON output for final response
                        final_response = await litellm.acompletion(
                            model=model,
                            messages=messages + [{
                                "role": "assistant",
                                "content": final_content
                            }, {
                                "role": "user",
                                "content": "Please format your response as JSON with 'message' and optional 'proposal' fields. The proposal should contain 'summary' and 'changes' array."
                            }],
                            response_format={"type": "json_object"},
                            temperature=0.3,  # Lower temperature for structured output
                            max_tokens=self.config.max_tokens,
                        )

                        structured_content = final_response.choices[0].message.content
                        logger.info("Got structured JSON response")

                    except Exception as e:
                        logger.warning(f"Failed to get structured response, using original: {e}")
                        structured_content = final_content

                    # Add to conversation history
                    self.conversation_history.append({
                        "role": "assistant",
                        "content": structured_content
                    })

                    # Parse proposal
                    proposal = self._try_parse_proposal(structured_content)

                    # Create response message
                    message = Message(
                        id=f"msg-{uuid.uuid4()}",
                        role="agent",
                        content=self._extract_message_content(structured_content),
                        timestamp="Just now",
                    )

                    return ChatResponse(message=message, proposal=proposal)

            # Max iterations reached
            logger.warning(f"Max iterations ({max_iterations}) reached in tool calling loop")
            error_message = Message(
                id=f"msg-{uuid.uuid4()}",
                role="system",
                content="Agent reached maximum tool calling iterations. Please try a simpler query.",
                timestamp="Just now",
            )
            return ChatResponse(message=error_message)

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
                elif change_type == "merge_nodes":
                    proposal.changes.append(
                        MergeNodesChange(
                            id=change_id,
                            entity=change_data.get("entity", "Unknown"),
                            primary_label=change_data.get("primaryLabel", ""),
                            secondary_label=change_data.get("secondaryLabel", ""),
                            primary_properties=change_data.get("primaryProperties", {}),
                            secondary_properties=change_data.get("secondaryProperties", {}),
                            merged_properties=change_data.get("mergedProperties", {}),
                            match_confidence=change_data.get("matchConfidence", 0.5),
                            matched_rules=change_data.get("matchedRules", []),
                            evidence=change_data.get("evidence"),
                            requires_review=change_data.get("requiresReview", True),
                            artifact_id=change_data.get("artifactId"),
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
