# MCP Skills and Context Guide

This guide shows you how to add **custom skills** and **persistent context** to your Lance Graph agent, similar to Claude Code's custom skills feature.

## Overview

The MCP (Model Context Protocol) integration provides:

1. **Custom Skills** - Reusable prompt templates that extend agent capabilities
2. **Persistent Context** - User preferences, domain knowledge, and constraints
3. **Dynamic Context Injection** - Automatic context injection into conversations

## Quick Start

### 1. Enable MCP in Your Agent

```python
from knowledge_graph.agent.integrated_agent import DataInvestigationAgent
from knowledge_graph.service import create_default_service

service = create_default_service()

agent = DataInvestigationAgent(
    service=service,
    duckdb_path="path/to/database.duckdb",
    enable_mcp=True,  # Enable MCP features
)
```

### 2. Add Custom Context

```bash
# Add a user preference
python -m knowledge_graph.cli.mcp_manager context add \
    "Always prioritize privacy when analyzing call data" \
    --category user_preference

# Add domain knowledge
python -m knowledge_graph.cli.mcp_manager context add \
    "This dataset uses E.164 phone number format" \
    --category domain_knowledge

# Add a constraint
python -m knowledge_graph.cli.mcp_manager context add \
    "Merge confidence threshold is 0.85" \
    --category constraint
```

### 3. Use Custom Skills

```bash
# List available skills
python -m knowledge_graph.cli.mcp_manager skills list

# Test a skill
python -m knowledge_graph.cli.mcp_manager skills test analyze_timeline \
    entity_type=Person \
    target="John Smith" \
    table_name=calls
```

## Custom Skills

Skills are reusable prompt templates stored in `.lance-graph/skills.yaml`.

### Built-in Skills

#### analyze_timeline
Analyzes temporal patterns in communications or events.
```yaml
analyze_timeline:
  description: "Analyze temporal patterns in communications or events"
  parameters:
    - entity_type  # e.g., "Person", "Phone"
    - target       # e.g., "John Smith", "555-1234"
    - table_name   # e.g., "calls", "locations"
```

**Usage in conversation:**
> "Use the analyze_timeline skill for Person 'John Smith' in the calls table"

The agent will automatically call the skill tool and apply the formatted prompt.

#### identify_network
Maps network connections around an entity.
```yaml
identify_network:
  parameters:
    - central_entity   # Starting entity
    - degree           # How many hops (1, 2, 3)
    - relationship_type # Type to focus on
```

#### detect_anomalies
Finds statistical anomalies in entity behavior.
```yaml
detect_anomalies:
  parameters:
    - entity_type
    - metric       # What to analyze (e.g., "call_count", "duration")
    - table_name
    - threshold    # Std deviations (e.g., "3.0")
```

#### compare_entities
Compares two entities and suggests merges if similar.
```yaml
compare_entities:
  parameters:
    - entity1
    - entity2
```

#### enrich_entity
Enriches an entity with additional properties from external data.
```yaml
enrich_entity:
  parameters:
    - entity_type
    - entity_label
    - data_sources  # Comma-separated list
```

### Adding Custom Skills

#### Via CLI:
```bash
python -m knowledge_graph.cli.mcp_manager skills add \
    find_clusters \
    "Identify clusters using graph algorithms" \
    --template "Apply community detection algorithms to find clusters in the graph. Focus on {metric} and use {algorithm}." \
    --params metric algorithm
```

#### Via YAML:
Edit `.lance-graph/skills.yaml`:
```yaml
custom_analysis:
  description: "Your custom analysis skill"
  prompt_template: |
    Perform custom analysis on {target} focusing on:
    1. {aspect1}
    2. {aspect2}

    Use {method} method and provide confidence scores.
  parameters:
    - target
    - aspect1
    - aspect2
    - method
```

### Using Skills Programmatically

```python
# The agent automatically exposes skills as tools
# Just reference them in conversation:

response = await agent.process_message(
    "Use the analyze_timeline skill to analyze Person 'Alice Johnson' "
    "in the call_records table"
)

# The agent will:
# 1. Recognize the skill reference
# 2. Call the skill_analyze_timeline tool
# 3. Get the formatted prompt
# 4. Apply it to continue the investigation
```

## Persistent Context

Context is stored in `.lance-graph/context.jsonl` and automatically injected into conversations.

### Context Categories

1. **user_preference** - How the user wants things done
2. **domain_knowledge** - Facts about the domain/data
3. **constraint** - Rules and limitations
4. **general** - Uncategorized context

### Managing Context

```bash
# Add context
python -m knowledge_graph.cli.mcp_manager context add \
    "When analyzing timeline, focus on weekday patterns" \
    --category user_preference

# List all context
python -m knowledge_graph.cli.mcp_manager context list

# List specific category
python -m knowledge_graph.cli.mcp_manager context list --category domain_knowledge

# Clear specific category
python -m knowledge_graph.cli.mcp_manager context clear --category constraint

# Clear all
python -m knowledge_graph.cli.mcp_manager context clear
```

### Context Example

```jsonl
{"content": "Prioritize privacy - only expose aggregated patterns", "category": "user_preference", "metadata": {"priority": "high"}}
{"content": "This is a counterterrorism investigation", "category": "domain_knowledge", "metadata": {"domain": "intelligence"}}
{"content": "Merge threshold is 0.85", "category": "constraint", "metadata": {"type": "data_quality"}}
```

When you start a conversation, this context is automatically injected:

```
=== USER CONTEXT ===
The user has provided the following persistent context:

[USER_PREFERENCE] Prioritize privacy - only expose aggregated patterns
[DOMAIN_KNOWLEDGE] This is a counterterrorism investigation
[CONSTRAINT] Merge threshold is 0.85

Use this context to inform your responses.
```

## Advanced Usage

### Custom Context Files

```python
from pathlib import Path

agent = DataInvestigationAgent(
    service=service,
    enable_mcp=True,
    context_file=Path("/custom/path/context.jsonl"),
    skills_file=Path("/custom/path/skills.yaml"),
)
```

### Programmatic Context Management

```python
# Add context programmatically
agent.mcp_context.add_context(
    content="Focus on Q4 2024 timeframe",
    category="constraint",
    metadata={"temporal": True}
)

# Get context
context = agent.mcp_context.get_context(category="user_preference", limit=5)

# Clear context
agent.mcp_context.clear_context(category="constraint")
```

### Programmatic Skill Management

```python
# Add a skill
agent.mcp_context.add_skill(
    name="custom_skill",
    description="My custom skill",
    prompt_template="Analyze {target} using {method}",
    parameters=["target", "method"]
)

# List skills
skills = agent.mcp_context.list_skills()

# Get skill details
skill = agent.mcp_context.get_skill("analyze_timeline")
```

### Selective Context Injection

```python
# Only inject specific categories
messages = agent.mcp_context.inject_context_into_messages(
    messages,
    categories=["user_preference", "domain_knowledge"]
)
```

## Integration with Agent Workflow

The MCP system integrates seamlessly:

1. **Skills as Tools**: Custom skills appear as callable tools in the agent's tool list
2. **Automatic Context**: Context is injected into every conversation automatically
3. **Native Tool Calling**: Skills work with the native function calling system

### Example Flow

```python
# User message
response = await agent.process_message(
    "Analyze the communication patterns for person '555-1234' "
    "and identify any anomalies"
)

# Agent workflow:
# 1. Context injected automatically (user preferences, constraints)
# 2. Agent sees custom skills in its tool list
# 3. Agent can call skill_analyze_timeline or skill_detect_anomalies
# 4. Skill returns formatted prompt
# 5. Agent applies prompt and continues investigation
# 6. Final response incorporates context and skill outputs
```

## Tips and Best Practices

### Context Tips
- Keep context entries concise (< 200 chars)
- Use categories consistently
- Add metadata for filtering/organization
- Review and clean up context periodically

### Skill Tips
- Use clear, descriptive parameter names
- Include numbered steps in templates
- Specify expected outputs
- Test skills before deploying

### Performance
- Context injection adds ~500-1000 tokens per conversation
- Skills add minimal overhead (only when called)
- Limit context to last 10-20 entries for efficiency

## MCP Server Integration (Future)

The current implementation uses file-based storage. For production use, you can integrate with external MCP servers:

- **[@modelcontextprotocol/server-memory](https://www.npmjs.com/package/@modelcontextprotocol/server-memory)** - Official memory server
- **[mcp-memory-keeper](https://github.com/mkreyman/mcp-memory-keeper)** - Persistent context management
- **[mcp-prompts](https://github.com/sparesparrow/mcp-prompts)** - Advanced prompt management

To add MCP SDK support:
```bash
pip install mcp
```

Then integrate with [Python MCP Client](https://github.com/modelcontextprotocol/python-sdk) for remote MCP servers.

## References

- [Model Context Protocol Documentation](https://modelcontextprotocol.io/specification/2025-06-18)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [Official MCP Servers](https://github.com/modelcontextprotocol/servers)
- [MCP Memory Server](https://github.com/modelcontextprotocol/servers/tree/main/src/memory)
