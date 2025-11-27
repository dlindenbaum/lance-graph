## NIST RMF Compliance Tool

A comprehensive NIST 800-53 Risk Management Framework (RMF) compliance tool powered by **lance-graph** and **Claude AI agents**. This tool provides graph-based modeling of security controls, automated evidence gathering, intelligent compliance assessment, and visualization for eMASS packages.

### Features

🔐 **Graph-Based Control Modeling**
- Models NIST 800-53 controls as a knowledge graph using lance-graph
- Tracks relationships between controls, requirements, evidence, and systems
- Supports Cypher queries for complex compliance analysis

🤖 **Claude AI Agent Integration**
- Automated compliance assessment using Claude 3.5 Sonnet
- Intelligent evidence evaluation
- Remediation plan generation
- Control-to-codebase mapping

📸 **Automated Evidence Gathering**
- Screenshot capture using Playwright (Python Puppeteer equivalent)
- Configuration file collection
- Log file extraction
- Automated evidence timestamping and metadata

📊 **Visualization & Reporting**
- Interactive graph visualizations with Cytoscape.js
- Compliance status dashboards
- Control traceability matrices
- Gap analysis reports
- eMASS-compatible package export

### Architecture

```
nist_rmf_compliance/
├── models.py              # Data models (Control, Evidence, Assessment, etc.)
├── graph_schema.py        # RMF graph schema and Cypher queries
├── compliance_engine.py   # Claude-powered compliance evaluation
├── evidence_gatherer.py   # Automated evidence collection with Playwright
├── visualization.py       # Graph visualizations and reporting
├── agents/
│   └── compliance_agent.py  # Claude agent for intelligent assessment
└── cli/
    └── main.py           # Command-line interface
```

### Installation

```bash
# Install lance-graph with the compliance tool
cd python
uv pip install -e '.[tests]'

# Install optional dependencies
pip install anthropic          # For Claude AI agent
pip install playwright          # For screenshot capture
playwright install              # Install browser binaries

# Set up API key for Claude
export ANTHROPIC_API_KEY=sk-ant-...
```

### Quick Start

#### 1. Initialize a Compliance Project

```bash
python -m nist_rmf_compliance.cli.main init --project-dir ./my-compliance
```

#### 2. Run the Example

```bash
python examples/nist_rmf_example.py
```

This will:
- Create sample NIST 800-53 controls
- Build an RMF knowledge graph
- Generate compliance visualizations
- Export an eMASS package
- Demonstrate Claude agent capabilities

#### 3. Gather Evidence

```bash
# Capture screenshot evidence
python -m nist_rmf_compliance.cli.main gather \\
  --screenshot \\
  --url https://app.example.com/admin \\
  --title "Admin Dashboard" \\
  --description "User management interface showing RBAC"

# Collect configuration file
python -m nist_rmf_compliance.cli.main gather \\
  --config-file /etc/app/security.conf \\
  --title "Security Configuration" \\
  --description "Application security settings"

# Collect log file (last 1000 lines)
python -m nist_rmf_compliance.cli.main gather \\
  --log-file /var/log/app/audit.log \\
  --title "Audit Logs" \\
  --log-lines 1000
```

#### 4. Visualize Compliance

```bash
python -m nist_rmf_compliance.cli.main visualize \\
  --system-id WEB-APP-001 \\
  --output compliance_graph.html
```

#### 5. Generate Reports

```bash
# eMASS package
python -m nist_rmf_compliance.cli.main report \\
  --system-id WEB-APP-001 \\
  --format emass \\
  --output-dir ./emass_package

# Gap analysis
python -m nist_rmf_compliance.cli.main report \\
  --system-id WEB-APP-001 \\
  --format gaps

# Compliance matrix
python -m nist_rmf_compliance.cli.main report \\
  --system-id WEB-APP-001 \\
  --format matrix
```

### Python API Usage

```python
from nist_rmf_compliance import (
    Control, Requirement, Evidence, System,
    build_rmf_graph, ComplianceEngine, EvidenceGatherer,
    ComplianceVisualizer
)

# Create data models
controls = [
    Control(
        control_id="AC-2",
        family="Access Control",
        title="Account Management",
        description="Manage system accounts...",
        baseline=["MODERATE", "HIGH"],
        priority="P1",
    )
]

# Build graph
graph = build_rmf_graph(controls, requirements, evidence, systems, assessments, implementations)

# Query with Cypher
results = graph.query(\"\"\"
    MATCH (s:System)-[:IMPLEMENTS]->(c:Control)
    WHERE s.system_id = 'WEB-APP-001'
    RETURN c.control_id, c.title
\"\"\")

# Use Claude agent for assessment
engine = ComplianceEngine(graph)
assessment = engine.assess_control("AC-2", "WEB-APP-001", evidence_list)

# Gather evidence
async with EvidenceGatherer() as gatherer:
    evidence = await gatherer.capture_screenshot(
        url="https://app.example.com",
        title="Login Page",
        description="MFA login interface"
    )

# Generate visualizations
visualizer = ComplianceVisualizer(graph)
visualizer.generate_html_visualization("WEB-APP-001", "compliance.html")
emass_package = visualizer.export_emass_package("WEB-APP-001")
```

### Graph Schema

The RMF graph uses the following schema:

**Nodes:**
- `Control`: NIST 800-53 security controls
- `Requirement`: Specific testable requirements
- `Evidence`: Supporting artifacts (screenshots, documents, logs)
- `System`: Information systems being assessed
- `Assessment`: Compliance assessment results
- `Implementation`: Control implementation records

**Relationships:**
- `REQUIRES`: Control → Requirement
- `SUPPORTS`: Evidence → Requirement
- `IMPLEMENTS`: System → Control
- `ASSESSES`: Assessment → Control
- `RELATES_TO`: Control → Control

### Example Cypher Queries

```cypher
# Find all controls without evidence
MATCH (c:Control)-[:REQUIRES]->(r:Requirement)
WHERE NOT exists((r)<-[:SUPPORTS]-(:Evidence))
RETURN c.control_id, c.title, r.requirement_id

# Get compliance status summary
MATCH (s:System {system_id: 'WEB-APP-001'})-[:IMPLEMENTS]->(c:Control)
MATCH (a:Assessment)-[:ASSESSES]->(c)
WHERE a.system_id = 'WEB-APP-001'
RETURN a.status, count(c) as control_count

# Find related controls that are satisfied
MATCH (c1:Control {control_id: 'AC-2'})-[:RELATES_TO]->(c2:Control)
MATCH (a:Assessment)-[:ASSESSES]->(c2)
WHERE a.status = 'Satisfied'
RETURN c2.control_id, c2.title
```

### Claude Agent Capabilities

The Claude AI agent provides:

1. **Control Analysis** - Explains requirements and implementation guidance
2. **Evidence Evaluation** - Assesses if evidence adequately demonstrates compliance
3. **Remediation Planning** - Generates prioritized action plans for gaps
4. **Control Mapping** - Maps controls to codebase locations

```python
from nist_rmf_compliance.agents import ComplianceAgent

agent = ComplianceAgent()

# Analyze a control
analysis = agent.analyze_control(
    control_id="AC-2",
    control_description="Account Management requirements...",
    system_context="Web application with SSO"
)

# Evaluate evidence
evaluation = agent.evaluate_evidence(
    requirement="Users must authenticate with MFA",
    evidence_descriptions=["Screenshot of login page", "MFA config file"]
)

# Generate remediation plan
plan = agent.generate_remediation_plan(
    control_id="AC-2",
    current_status="Partially Satisfied",
    findings="MFA not enforced for all user types"
)
```

### Integration with Claude Code

This tool can be integrated as a Claude Code skill for use during development:

1. Create `.claude/skills/nist-rmf.md`:

```markdown
---
name: nist-rmf
description: Assess NIST 800-53 compliance for the current codebase
---

Use the NIST RMF compliance tool to:
- Analyze security controls relevant to this codebase
- Identify which NIST 800-53 controls apply
- Map controls to code locations
- Suggest evidence that should be collected
- Generate compliance documentation

The tool is available at: python -m nist_rmf_compliance.cli.main
```

2. Use in Claude Code:

```
@nist-rmf
Analyze this authentication module for AC-2 (Account Management) compliance
```

### eMASS Package Generation

The tool generates eMASS-compatible packages containing:

- **compliance_matrix.json** - Control traceability matrix
- **gap_analysis.json** - Gaps and remediation needs
- **compliance_graph.html** - Interactive visualization
- **package_summary.json** - Executive summary

These artifacts support the Authorization to Operate (ATO) process.

### Best Practices

1. **Regular Evidence Collection**
   - Automate screenshot capture in CI/CD pipelines
   - Schedule periodic configuration snapshots
   - Collect audit logs continuously

2. **Graph-Based Analysis**
   - Leverage Cypher queries for custom compliance reports
   - Track control dependencies and relationships
   - Identify cascading gaps

3. **Claude Agent Usage**
   - Use AI assessment as a first pass, followed by expert review
   - Maintain evidence quality to improve AI accuracy
   - Review and refine remediation plans

4. **Continuous Monitoring**
   - Integrate with monitoring tools for real-time compliance status
   - Automate gap detection
   - Track compliance trends over time

### Contributing

This tool is part of the lance-graph project. Contributions welcome!

### License

Apache License 2.0 (same as lance-graph)

### Related Projects

- [lance-graph](https://github.com/lancedb/lance-graph) - Cypher-capable graph engine
- [LanceDB](https://lancedb.com) - Serverless vector database
- [NIST 800-53](https://csrc.nist.gov/publications/detail/sp/800-53/rev-5/final) - Security controls
