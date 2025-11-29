# DuckDB Integration for Graph Review UI

## Overview

The Graph Review Agent now supports **DuckDB** as an external data source, enabling:
- SQL queries across multiple databases
- Advanced data analysis and pattern detection
- Automatic node and relationship proposal generation
- Integration with existing graph data

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│  IntegratedCDRAgent                                       │
├──────────────────────────────────────────────────────────┤
│                                                            │
│  ┌─────────────────┐     ┌──────────────────────┐       │
│  │  Graph Tools    │     │   DuckDB Tools       │       │
│  ├─────────────────┤     ├──────────────────────┤       │
│  │ - Cypher Query  │     │ - SQL Query          │       │
│  │ - Graph Search  │     │ - Pattern Detection  │       │
│  │ - CDR Analysis  │     │ - Correlation Finder │       │
│  └─────────────────┘     │ - Anomaly Detection  │       │
│                           │ - Temporal Analysis  │       │
│  ┌─────────────────────────────────────────────┐        │
│  │  Node Proposal Generator                   │        │
│  │  - Extract entities from tables             │        │
│  │  - Generate relationships from correlations │        │
│  │  - Create nodes from patterns               │        │
│  └─────────────────────────────────────────────┘        │
└──────────────────────────────────────────────────────────┘
              ↓                    ↓
       lance-graph           DuckDB Database
```

## DuckDB Tools

### 1. DuckDBQueryTool

Execute SQL queries on DuckDB databases.

```python
from knowledge_graph.agent.duckdb_tools import DuckDBQueryTool

# Connect to database
db_tool = DuckDBQueryTool("./data.duckdb", read_only=True)

# Execute query
results = db_tool.execute_query("""
    SELECT phone_number, COUNT(*) as call_count
    FROM call_records
    GROUP BY phone_number
    ORDER BY call_count DESC
""")

# Get tables
tables = db_tool.get_tables()

# Get schema
schema = db_tool.get_schema("call_records")

# Search across tables
results = db_tool.search_across_tables("555-0199")
```

### 2. DataAnalysisTool

Advanced data analysis and pattern detection.

```python
from knowledge_graph.agent.duckdb_tools import DataAnalysisTool

analysis = DataAnalysisTool(db_tool)

# Find frequent patterns
patterns = analysis.find_frequent_patterns(
    table="call_records",
    column="from_number",
    min_frequency=5
)

# Find correlations
correlations = analysis.find_correlations(
    table="call_records",
    column1="from_number",
    column2="to_number"
)

# Temporal analysis
temporal = analysis.temporal_analysis(
    table="call_records",
    timestamp_column="call_timestamp",
    group_by_interval="day"  # day, hour, month
)

# Detect anomalies
anomalies = analysis.detect_anomalies(
    table="call_records",
    numeric_column="duration_seconds",
    std_threshold=3.0
)

# Find duplicates
duplicates = analysis.find_duplicates(
    table="call_records",
    columns=["from_number", "to_number"]
)
```

### 3. NodeProposalGenerator

Generate graph nodes and relationships from data analysis.

```python
from knowledge_graph.agent.duckdb_tools import NodeProposalGenerator

proposal_gen = NodeProposalGenerator(analysis)

# Propose nodes from entities
node_proposals = proposal_gen.propose_nodes_from_entities(
    table="subscribers",
    entity_column="phone_number",
    entity_type="Phone",
    property_columns=["carrier", "plan_type", "address"],
    min_confidence=70
)

# Propose relationships from correlations
rel_proposals = proposal_gen.propose_relationships_from_correlation(
    table="call_records",
    from_column="from_number",
    to_column="to_number",
    relationship_type="CONTACTED",
    min_co_occurrence=3
)

# Propose nodes from patterns
pattern_proposals = proposal_gen.propose_nodes_from_patterns(
    table="call_records",
    pattern_column="location",
    entity_type="Location",
    min_frequency=5
)

# Propose from custom SQL
custom_proposals = proposal_gen.propose_from_sql_query(
    query="""
        SELECT DISTINCT carrier, COUNT(*) as subscriber_count
        FROM subscribers
        GROUP BY carrier
    """,
    entity_type="Carrier",
    label_column="carrier",
    property_columns=["subscriber_count"],
    confidence=85
)
```

## Agent Integration

### Setup

```bash
# 1. Install DuckDB
pip install duckdb>=0.10.0

# 2. Set DuckDB path (optional, can be set at runtime)
export DUCKDB_PATH=./my_data.duckdb

# 3. Start backend
cd python
uv run python -m knowledge_graph.webservice
```

### Available Agent Tools

When DuckDB is configured, the agent has access to these tools:

| Tool | Description | Example |
|------|-------------|---------|
| `sql_query(query)` | Execute SQL on DuckDB | `sql_query("SELECT * FROM calls LIMIT 10")` |
| `search_data(term, tables)` | Search across tables | `search_data("555-0199", ["call_records"])` |
| `analyze_patterns(table, column, min_freq)` | Find patterns | `analyze_patterns("calls", "from_number", 5)` |
| `find_correlations(table, col1, col2)` | Find correlations | `find_correlations("calls", "from", "to")` |
| `temporal_analysis(table, timestamp_col)` | Time patterns | `temporal_analysis("calls", "timestamp")` |
| `detect_anomalies(table, column)` | Find outliers | `detect_anomalies("calls", "duration")` |
| `propose_nodes(table, entity_col, type, props)` | Generate nodes | `propose_nodes("subscribers", "phone", "Phone", ["carrier"])` |
| `propose_relationships(table, from, to, type)` | Generate edges | `propose_relationships("calls", "from", "to", "CONTACTED")` |

### Example Agent Queries

```
User: Analyze the call_records table and find frequent callers

Agent: I'll query the DuckDB database to analyze call patterns.
→ sql_query("SELECT from_number, COUNT(*) as calls FROM call_records GROUP BY from_number ORDER BY calls DESC LIMIT 10")
→ Found 555-0199 with 4 calls (highest frequency)
→ Proposing Phone node for 555-0199...

User: Find correlations between phone numbers and propose relationships

Agent: Analyzing correlations in the data...
→ find_correlations("call_records", "from_number", "to_number")
→ Found strong correlation: 555-0199 ↔ 555-1024 (3 co-occurrences)
→ propose_relationships("call_records", "from_number", "to_number", "CONTACTED")
→ Proposing CONTACTED relationship with evidence...

User: Detect any anomalies in call durations

Agent: Checking for statistical outliers...
→ detect_anomalies("call_records", "duration_seconds", 3.0)
→ Found 2 anomalous calls exceeding 3 standard deviations
→ Proposing investigation of calls: [call_id: 123, 456]
```

## Configuration

### Environment Variables

```bash
# DuckDB database path
export DUCKDB_PATH=./cdr_data.duckdb

# Agent configuration
export OPENAI_API_KEY=sk-...
export LITELLM_ROUTING_STRATEGY=usage-based-routing
export AGENT_LOG_LEVEL=INFO
```

### Programmatic Configuration

```python
from knowledge_graph.agent import IntegratedCDRAgent, AgentConfig
from knowledge_graph import LanceKnowledgeGraph

# Configure agent with DuckDB
service = LanceKnowledgeGraph(...)
config = AgentConfig.from_env()

agent = IntegratedCDRAgent(
    service=service,
    config=config,
    duckdb_path="./cdr_data.duckdb"
)

# Agent now has access to both graph and DuckDB tools
response = await agent.process_message(
    "Analyze call patterns and propose new nodes"
)
```

## Use Cases

### 1. CDR Investigation

```sql
-- DuckDB stores raw CDR data
CREATE TABLE call_records (
    call_id INTEGER,
    from_number VARCHAR,
    to_number VARCHAR,
    timestamp TIMESTAMP,
    duration INTEGER,
    tower_id VARCHAR
);

-- Agent proposes nodes and relationships
Agent → propose_nodes("call_records", "from_number", "Phone", ["tower_id"])
Agent → propose_relationships("call_records", "from_number", "to_number", "CONTACTED")
```

### 2. Pattern Detection

```sql
-- Find suspicious patterns
SELECT from_number, COUNT(DISTINCT to_number) as unique_contacts
FROM call_records
GROUP BY from_number
HAVING COUNT(DISTINCT to_number) > 10;

-- Agent detects and proposes
Agent → "Found 555-0199 with 15 unique contacts (potential hub)"
Agent → Proposes "Person" node with "hub_score" property
```

### 3. Temporal Analysis

```sql
-- Analyze call timing patterns
SELECT DATE_TRUNC('hour', timestamp) as hour,
       COUNT(*) as call_count
FROM call_records
GROUP BY hour
ORDER BY call_count DESC;

-- Agent identifies patterns
Agent → "Peak activity: 9-10 AM (47 calls)"
Agent → Proposes "TimePattern" node with properties
```

### 4. Cross-Source Integration

```python
# Query both graph and DuckDB
# 1. Check existing graph
existing = query_graph("MATCH (p:Phone {number: '555-0199'}) RETURN p")

# 2. Query DuckDB for new data
new_data = sql_query("SELECT * FROM call_records WHERE from_number = '555-0199'")

# 3. Propose updates
if existing and new_data:
    agent → "Found 10 new calls for existing node 555-0199"
    agent → Proposes property update: call_count += 10
```

## Example: Complete Workflow

```python
# 1. Create DuckDB database
import duckdb
con = duckdb.connect("cdr_data.duckdb")
con.execute("""
    CREATE TABLE call_records AS
    SELECT * FROM read_csv('cdr_export.csv')
""")

# 2. Start agent with DuckDB
from knowledge_graph.agent import IntegratedCDRAgent

agent = IntegratedCDRAgent(
    service=graph_service,
    config=agent_config,
    duckdb_path="cdr_data.duckdb"
)

# 3. Agent explores data
response = await agent.process_message(
    "Analyze the call_records table and propose phone numbers as nodes"
)

# 4. Agent response includes:
# - SQL query executed
# - Patterns found
# - Proposed nodes with properties
# - Confidence scores
# - Evidence from data

# 5. Review and approve in UI
# User reviews proposal → Approves → Nodes added to graph
```

## Best Practices

1. **Read-Only Access**: Always connect to DuckDB in read-only mode for safety
2. **Index Your Data**: Create indexes on frequently queried columns
3. **Batch Processing**: Use SQL aggregations instead of row-by-row processing
4. **Evidence Tracking**: Always include source table and query in proposals
5. **Confidence Scores**: Base confidence on data quality and frequency
6. **Cross-Reference**: Check existing graph before proposing duplicates

## Performance Tips

```sql
-- Good: Aggregation in SQL
SELECT phone_number, COUNT(*) as calls
FROM call_records
GROUP BY phone_number
HAVING COUNT(*) > 10

-- Bad: Fetching all rows then filtering in Python
SELECT * FROM call_records  -- Don't do this!
```

## Monitoring

Check DuckDB status via API:

```bash
curl http://localhost:8000/api/agent/status
```

Response includes:
```json
{
  "duckdb": {
    "connected": true,
    "tables": ["call_records", "subscribers", "tower_locations"]
  }
}
```

## Example Database Setup

See `examples/duckdb_integration_example.py` for complete example including:
- Creating DuckDB database
- Populating with sample data
- Running all tools
- Generating proposals

```bash
cd examples
python duckdb_integration_example.py
```

## Troubleshooting

**Issue**: `ImportError: No module named 'duckdb'`
```bash
pip install duckdb>=0.10.0
```

**Issue**: Database locked
- Ensure read-only mode: `DuckDBQueryTool(path, read_only=True)`
- Close other connections to the database

**Issue**: Agent not detecting DuckDB
- Check `DUCKDB_PATH` environment variable
- Verify database file exists and is readable
- Check logs for initialization errors

## License

Apache 2.0
