# Graph Modification Review UI

An **Agent-driven Graph Review Interface** for investigating Call Data Records (CDR). The UI focuses on reviewing proposed changes (nodes and relationships) rather than traditional graph visualization.

## Overview

The Graph Review UI provides:
- **Agent-driven investigation**: AI agent analyzes data and proposes graph modifications
- **Pull request-style review**: Review, edit, and approve/reject changes before committing
- **Chat interface**: Natural language interaction with the agent
- **Evidence tracking**: View reasoning and confidence scores for each proposed change
- **Inline editing**: Modify proposed changes before approval

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Header: Case ID, Agent Status                                  │
├─────────────────────────┬───────────────────────────────────────┤
│                         │                                       │
│   MODIFICATION REVIEW   │      AGENT CHAT                       │
│   PANEL (Left)          │      PANEL (Right)                    │
│                         │                                       │
│   - Proposals           │   - Chat history                      │
│   - Changes             │   - Quick actions                     │
│   - Inline editing      │   - Message input                     │
│                         │                                       │
└─────────────────────────┴───────────────────────────────────────┘
```

## Technology Stack

### Frontend
- **React 18** with TypeScript
- **Vite** for build tooling
- **Tailwind CSS** for styling
- Dark theme optimized for long analysis sessions

### Backend
- **FastAPI** web service
- **LiteLLM Router** for multi-model LLM integration with automatic fallbacks
- **lance-graph** for graph query engine
- **Lance** for persistent storage

### Agent
- **LiteLLM Router** for intelligent model selection and failover:
  - Automatic fallback between models
  - Load balancing strategies (usage-based, latency-based, least-busy)
  - Retry logic and error handling
  - Cost tracking across providers
- Custom tools for CDR analysis
- Cypher query integration

## Installation

### Prerequisites
- Python 3.11+
- Node.js 18+
- Rust toolchain (for building lance-graph)
- LLM API key (OpenAI, Google, or other LiteLLM-supported provider)

### Backend Setup

```bash
cd python

# Create virtual environment
uv venv --python 3.11 .venv
source .venv/bin/activate

# Install dependencies
uv pip install 'maturin[patchelf]'
uv pip install -e '.[tests]'
maturin develop

# Set up environment variables
export OPENAI_API_KEY=sk-...  # Or other LLM provider key
# Optional: export LITELLM_MODEL=gpt-4o-mini

# Initialize knowledge graph storage
uv run knowledge_graph --init

# Start the backend server
uv run python -m knowledge_graph.webservice
```

The backend will be available at `http://localhost:8000`.

### Frontend Setup

```bash
cd web

# Install dependencies
npm install

# Start development server
npm run dev
```

The frontend will be available at `http://localhost:3000`.

## Usage

### Starting a New Investigation

1. Open the UI at `http://localhost:3000`
2. The agent is initialized and ready
3. Start by asking the agent to investigate:
   ```
   Analyze the call patterns for 555-0199
   ```

### Reviewing Proposals

1. Agent generates proposals after analysis
2. Each proposal contains discrete changes:
   - **Add Node**: New entities (Person, Phone, Location)
   - **Add Edge**: New relationships (CONTACTED, OWNED_BY)
   - **Modify Node**: Updates to existing nodes
   - **Delete Node/Edge**: Removals
3. Review each change:
   - Click `?` to view evidence
   - Click `✎` to edit values
   - Select changes to approve

### Approving Changes

1. Select individual changes or click "Select All"
2. Click "Approve" to commit to graph
3. Approved changes are persisted to Lance storage

### Iterative Investigation

1. Use quick action buttons:
   - 🔍 **Dig Deeper**: Expand investigation
   - 📋 **Show Evidence**: Review reasoning
   - 🔗 **Find Links**: Discover connections
   - 📊 **Summary**: Get case status
2. Ask follow-up questions
3. Agent generates new proposals
4. Review and approve iteratively

## API Endpoints

### Graph Review Agent

- `POST /api/agent/chat` - Send message to agent
  ```json
  {
    "message": "Analyze call patterns for 555-0199",
    "case_id": "CDR-2024-001"
  }
  ```

- `GET /api/agent/status` - Get agent status
- `POST /api/agent/reset` - Reset conversation
- `WS /api/agent/ws` - WebSocket for real-time chat

### Knowledge Graph

- `GET /graph/health` - Health check
- `GET /graph/datasets` - List datasets
- `POST /graph/query` - Execute Cypher query
- `GET /graph/schema` - Get graph schema

## Configuration

### LLM Router Configuration

The agent uses **LiteLLM Router** for intelligent multi-model support with automatic fallbacks.

#### Automatic Configuration (Environment Variables)

The router automatically detects and configures available models based on environment variables:

```bash
# Primary model (if any of these are set, they'll be added to router)
export OPENAI_API_KEY=sk-...           # Adds gpt-4o-mini
export GEMINI_API_KEY=...              # Adds gemini/gemini-1.5-flash
export ANTHROPIC_API_KEY=...           # Adds claude-3-5-sonnet
export AZURE_API_KEY=...               # Adds azure/gpt-4o-mini
export AZURE_API_BASE=https://...

# Optional: Override routing strategy
export LITELLM_ROUTING_STRATEGY=usage-based-routing  # Options: simple-shuffle, least-busy, usage-based-routing, latency-based-routing
export AGENT_TEMPERATURE=0.7
export AGENT_MAX_TOKENS=2000
export AGENT_LOG_LEVEL=INFO
```

#### Routing Strategies

1. **usage-based-routing** (default): Routes to model with lowest usage
   - Best for cost optimization
   - Evenly distributes load across models

2. **simple-shuffle**: Random distribution
   - Simple load balancing
   - Good for general purpose

3. **least-busy**: Routes to model with fewest active requests
   - Best for high-load scenarios
   - Optimizes throughput

4. **latency-based-routing**: Routes to fastest responding model
   - Best for performance-critical applications
   - Minimizes response time

#### Example Configurations

**Cost-Optimized (Free/Cheap Models):**
```bash
export GEMINI_API_KEY=your-key
export OPENAI_API_KEY=sk-your-key
export LITELLM_ROUTING_STRATEGY=usage-based-routing
# Primary: Gemini Flash (free tier), Fallback: GPT-4o-mini
```

**High Availability (Multiple Providers):**
```bash
export OPENAI_API_KEY=sk-...
export GEMINI_API_KEY=...
export ANTHROPIC_API_KEY=...
export LITELLM_ROUTING_STRATEGY=simple-shuffle
# Distributes across all 3 providers with automatic fallbacks
```

**Performance Critical:**
```bash
export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=...
export LITELLM_ROUTING_STRATEGY=latency-based-routing
# Uses fastest responding model
```

#### Fallback Chain

When you set multiple API keys, the router automatically creates a fallback chain:

```
Request → GPT-4o-mini (primary)
    ↓ (if fails)
   Gemini Flash (fallback 1)
    ↓ (if fails)
   Claude Sonnet (fallback 2)
    ↓ (if all fail)
   Error response
```

#### Monitoring

Check router status:
```bash
curl http://localhost:8000/api/agent/status
```

Returns configuration and stats:
```json
{
  "router": {
    "models": ["gpt-4o-mini", "gemini/gemini-1.5-flash"],
    "routing_strategy": "usage-based-routing",
    "fallbacks_configured": true
  }
}
```

See [IMPLEMENTATION_REVIEW.md](./IMPLEMENTATION_REVIEW.md) for detailed router documentation.

### Graph Configuration

Create `schema.yaml` in your data directory:

```yaml
nodes:
  Person:
    primary_key: person_id
    properties:
      - name
      - phone
      - email
      - location

  Phone:
    primary_key: number
    properties:
      - carrier
      - type
      - owner

  Location:
    primary_key: location_id
    properties:
      - address
      - coordinates

relationships:
  CONTACTED:
    source: Phone
    target: Phone
    properties:
      - timestamp
      - duration
      - direction

  OWNED_BY:
    source: Phone
    target: Person

  LOCATED_AT:
    source: Phone
    target: Location
    properties:
      - timestamp
```

## Development

### Running Tests

```bash
# Backend tests
cd python
pytest python/tests/ -v

# Frontend tests (if added)
cd web
npm test
```

### Building for Production

```bash
# Frontend
cd web
npm run build

# Backend (already production-ready)
cd python
uv pip install -e .
```

### Extending the Agent

Add new tools in `python/python/knowledge_graph/agent/tools.py`:

```python
class YourCustomTool:
    def __init__(self, graph_tool: GraphQueryTool):
        self.graph = graph_tool

    def analyze_something(self, param: str) -> List[Dict[str, Any]]:
        query = f"MATCH ... WHERE ... RETURN ..."
        return self.graph.execute(query)
```

Update the agent prompt in `cdr_agent.py` to include your new tool.

## Example Workflows

### CDR Investigation

1. **Initial Analysis**
   ```
   User: Analyze the call patterns for 555-0199
   Agent: [Proposes Person node, relationship patterns]
   User: [Reviews and approves]
   ```

2. **Deep Dive**
   ```
   User: Dig deeper on high-frequency contacts
   Agent: [Proposes new Phone nodes, CONTACTED edges]
   User: [Edits properties, approves selected changes]
   ```

3. **Connection Discovery**
   ```
   User: Find common contacts between 555-0199 and 555-1024
   Agent: [Proposes new connections with evidence]
   User: [Reviews evidence, approves]
   ```

## Troubleshooting

### Agent Not Responding

- Check backend logs for errors
- Verify LLM API key is set correctly
- Check API rate limits

### Frontend Not Connecting

- Ensure backend is running on port 8000
- Check CORS configuration in `webservice.py`
- Verify Vite proxy configuration

### Graph Queries Failing

- Check schema.yaml is properly configured
- Verify Lance datasets are initialized
- Check Cypher query syntax

## Performance Tips

1. **Use appropriate LLM model**:
   - Fast: `gpt-4o-mini`, `gemini-1.5-flash`
   - Accurate: `gpt-4o`, `claude-3-5-sonnet`

2. **Limit proposal size**:
   - Agent generates manageable proposals (~5-10 changes)
   - Request focused investigations

3. **Batch approvals**:
   - Select and approve multiple changes at once
   - Reduces commit overhead

## License

Apache 2.0 - See LICENSE file

## Contributing

Contributions welcome! Please see CONTRIBUTING.md for guidelines.

## Support

- GitHub Issues: https://github.com/lancedb/lance-graph/issues
- Documentation: https://deepwiki.com/lancedb/lance-graph
