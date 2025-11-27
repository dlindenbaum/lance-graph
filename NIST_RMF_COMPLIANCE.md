# NIST RMF Compliance Tool

**A Claude Agent-Powered Compliance Tool Built on lance-graph**

This repository now includes a comprehensive NIST 800-53 Risk Management Framework (RMF) compliance tool that leverages lance-graph's Cypher query capabilities and Claude AI agents to provide intelligent compliance assessment, evidence gathering, and visualization.

## Overview

The NIST RMF Compliance Tool transforms compliance documentation from a manual, document-heavy process into an intelligent, graph-based system that:

- **Models compliance as a knowledge graph** using lance-graph's Cypher engine
- **Automates evidence gathering** with Playwright-based screenshot capture
- **Provides AI-powered assessment** using Claude 3.5 Sonnet agents
- **Generates eMASS packages** for Authorization to Operate (ATO) processes
- **Visualizes compliance relationships** with interactive graph visualizations

## Why Graph-Based Compliance?

Traditional compliance tools treat controls, evidence, and assessments as disconnected documents. This graph-based approach:

✅ **Traces relationships** between controls, requirements, systems, and evidence
✅ **Identifies gaps** by querying the graph for missing relationships
✅ **Shows dependencies** between related controls
✅ **Enables complex queries** using Cypher for custom analysis
✅ **Scales efficiently** with lance-graph's high-performance engine

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    NIST RMF Compliance Tool                  │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
   ┌────▼────┐         ┌──────▼──────┐      ┌──────▼──────┐
   │ Claude  │         │   Evidence  │      │    Graph    │
   │ Agents  │         │  Gatherer   │      │   Storage   │
   └────┬────┘         └──────┬──────┘      └──────┬──────┘
        │                     │                     │
        │    ┌────────────────┴─────────────────┐  │
        │    │         lance-graph               │  │
        │    │    (Cypher Query Engine)          │  │
        │    └────────────────┬─────────────────┘  │
        │                     │                     │
        └─────────────────────┼─────────────────────┘
                              │
                    ┌─────────▼─────────┐
                    │   Visualizations  │
                    │   & eMASS Export  │
                    └───────────────────┘
```

## Key Components

### 1. Graph Schema (`graph_schema.py`)

Defines the RMF knowledge graph structure:

```python
# Nodes
- Control (NIST 800-53 controls)
- Requirement (testable requirements)
- Evidence (artifacts: screenshots, logs, configs)
- System (information systems)
- Assessment (evaluation results)

# Relationships
- REQUIRES: Control → Requirement
- SUPPORTS: Evidence → Requirement
- IMPLEMENTS: System → Control
- ASSESSES: Assessment → Control
- RELATES_TO: Control ↔ Control
```

### 2. Compliance Engine (`compliance_engine.py`)

Claude-powered assessment engine that:
- Analyzes evidence against requirements
- Determines compliance status
- Generates findings and recommendations
- Supports batch assessment across controls

### 3. Evidence Gatherer (`evidence_gatherer.py`)

Automated evidence collection with:
- **Screenshot capture** from web applications
- **Configuration file** collection
- **Log file** extraction
- **Metadata tracking** (timestamps, sources)

Uses Playwright (Python's Puppeteer equivalent) for reliable browser automation.

### 4. Visualization (`visualization.py`)

Generates compliance artifacts:
- **Interactive HTML graphs** using Cytoscape.js
- **Compliance matrices** by control family
- **Gap analysis reports** identifying missing evidence
- **eMASS packages** for ATO submissions

### 5. Claude Agent (`agents/compliance_agent.py`)

AI-powered capabilities:
- Control analysis and implementation guidance
- Evidence quality evaluation
- Remediation plan generation
- Control-to-codebase mapping

## Quick Start

### Installation

```bash
# Navigate to Python directory
cd python

# Install with test dependencies
uv pip install -e '.[tests]'

# Install optional dependencies
pip install anthropic playwright
playwright install

# Set Claude API key
export ANTHROPIC_API_KEY=sk-ant-...
```

### Run the Example

```bash
python examples/nist_rmf_example.py
```

This demonstration:
1. Creates sample NIST 800-53 controls (AC-1, AC-2, AC-3, AU-2, IA-2)
2. Builds an RMF knowledge graph with lance-graph
3. Queries compliance status using Cypher
4. Generates visualizations and gap analysis
5. Exports an eMASS-compatible package
6. Demonstrates Claude agent assessment

### CLI Usage

```bash
# Initialize a compliance project
python -m nist_rmf_compliance.cli.main init --project-dir ./compliance

# Gather screenshot evidence
python -m nist_rmf_compliance.cli.main gather \\
  --screenshot \\
  --url https://app.example.com/admin \\
  --title "Admin Dashboard" \\
  --description "RBAC user management interface"

# Generate visualization
python -m nist_rmf_compliance.cli.main visualize \\
  --system-id SYSTEM-001 \\
  --output compliance_graph.html

# Export eMASS package
python -m nist_rmf_compliance.cli.main report \\
  --system-id SYSTEM-001 \\
  --format emass \\
  --output-dir ./emass_package
```

## Example Cypher Queries

The tool enables powerful compliance queries using Cypher:

```cypher
# Find controls without evidence
MATCH (c:Control)-[:REQUIRES]->(r:Requirement)
WHERE NOT exists((r)<-[:SUPPORTS]-(:Evidence))
RETURN c.control_id, c.title

# Get compliance status by family
MATCH (s:System {system_id: 'WEB-APP-001'})-[:IMPLEMENTS]->(c:Control)
MATCH (a:Assessment)-[:ASSESSES]->(c)
RETURN c.family, a.status, count(c) as control_count
GROUP BY c.family, a.status

# Find related satisfied controls
MATCH (c1:Control {control_id: 'AC-2'})-[:RELATES_TO]->(c2:Control)
MATCH (a:Assessment)-[:ASSESSES]->(c2)
WHERE a.status = 'Satisfied'
RETURN c2.control_id, c2.title

# Identify compliance gaps for MODERATE baseline
MATCH (c:Control)
WHERE 'MODERATE' IN c.baseline
OPTIONAL MATCH (s:System {system_id: 'SYS-001'})-[:IMPLEMENTS]->(c)
OPTIONAL MATCH (a:Assessment)-[:ASSESSES]->(c)
WHERE s IS NULL OR a IS NULL OR a.status <> 'Satisfied'
RETURN c.control_id, c.title, c.family
```

## Use Cases

### 1. Continuous Compliance Monitoring

Integrate evidence gathering into CI/CD:

```yaml
# .github/workflows/compliance.yml
- name: Capture Compliance Evidence
  run: |
    python -m nist_rmf_compliance.cli.main gather \\
      --screenshot --url ${{ secrets.APP_URL }}/admin \\
      --title "Admin Panel - $(date +%Y-%m-%d)"
```

### 2. ATO Package Generation

Generate complete eMASS packages:

```python
visualizer = ComplianceVisualizer(graph)
emass_package = visualizer.export_emass_package("SYSTEM-001")
# Creates: compliance_matrix.json, gap_analysis.json, compliance_graph.html
```

### 3. AI-Assisted Control Implementation

Use Claude agent for guidance:

```python
agent = ComplianceAgent()
analysis = agent.analyze_control(
    control_id="AC-2",
    control_description="Account Management...",
    system_context="Django web application with LDAP"
)
# Returns: implementation steps, evidence types, pitfalls, related controls
```

### 4. Gap Analysis and Remediation

Identify and plan remediation:

```python
# Find gaps
gaps = graph.find_gaps("SYSTEM-001", baseline="MODERATE")

# Generate remediation plans
for gap in gaps:
    plan = agent.generate_remediation_plan(
        control_id=gap.control_id,
        current_status="Not Satisfied",
        findings=gap.findings
    )
```

## Claude Code Integration

Use as a Claude Code skill:

**`.claude/skills/nist-rmf.md`:**

```markdown
---
name: nist-rmf
description: NIST 800-53 compliance assessment
---

Analyze NIST 800-53 compliance for this codebase using the RMF compliance tool.

Commands:
- Analyze which controls apply to this system
- Map controls to code locations
- Identify evidence to collect
- Generate compliance documentation
```

**Usage:**

```
@nist-rmf
Review this authentication module for AC-2 compliance
```

## Graph Visualization Example

The tool generates interactive visualizations showing:

- **System nodes** (blue) - Information systems
- **Control nodes** (colored by status):
  - 🟢 Green: Satisfied
  - 🟡 Yellow: Partially Satisfied
  - 🔴 Red: Not Satisfied
  - ⚫ Gray: Not Assessed
- **Edges** showing relationships (IMPLEMENTS, REQUIRES, SUPPORTS)

Click nodes to see details: control ID, title, family, compliance status.

## Performance

Lance-graph provides high-performance graph queries:

- **100 controls**: ~680 µs query time
- **10,000 controls**: ~715 µs query time
- **1M controls**: ~743 µs query time

See [lance-graph benchmarks](README.md#benchmarks) for details.

## eMASS Integration

The tool generates eMASS-compatible artifacts:

| Artifact | Purpose |
|----------|---------|
| `compliance_matrix.json` | Control traceability matrix |
| `gap_analysis.json` | Gaps and remediation needs |
| `compliance_graph.html` | Interactive visualization |
| `package_summary.json` | Executive summary |

These support the RMF Authorization process:
1. **Prepare** - Define system and controls
2. **Categorize** - Determine impact level
3. **Select** - Choose baseline controls
4. **Implement** - Deploy controls
5. **Assess** - Evaluate compliance (← this tool)
6. **Authorize** - ATO decision
7. **Monitor** - Ongoing compliance

## Development

```bash
# Run tests
pytest python/tests/test_nist_rmf_compliance.py

# Type checking
pyright python/python/nist_rmf_compliance/

# Linting
ruff check python/python/nist_rmf_compliance/
ruff format python/python/nist_rmf_compliance/
```

## Documentation

- **Package README**: `python/python/nist_rmf_compliance/README.md`
- **Example script**: `examples/nist_rmf_example.py`
- **API documentation**: See docstrings in source files

## Roadmap

- [ ] Pre-populated NIST 800-53 Rev 5 control database
- [ ] Integration with vulnerability scanners (Nessus, Qualys)
- [ ] CIS Controls mapping
- [ ] OSCAL (Open Security Controls Assessment Language) import/export
- [ ] Real-time compliance dashboards
- [ ] Multi-system comparison views
- [ ] Automated POA&M generation

## License

Apache License 2.0 (same as lance-graph)

## Credits

Built with:
- [lance-graph](https://github.com/lancedb/lance-graph) - Cypher graph engine
- [Anthropic Claude](https://www.anthropic.com/) - AI-powered assessment
- [Playwright](https://playwright.dev/) - Browser automation
- [Cytoscape.js](https://js.cytoscape.org/) - Graph visualization

## Learn More

- 📚 [NIST 800-53 Documentation](https://csrc.nist.gov/publications/detail/sp/800-53/rev-5/final)
- 🔐 [RMF Overview](https://csrc.nist.gov/projects/risk-management)
- 🎯 [eMASS Documentation](https://www.disa.mil/~/media/Files/DISA/Services/eMASS/eMASS-User-Guide.pdf)
- 🗃️ [lance-graph Documentation](https://deepwiki.com/lancedb/lance-graph)

---

**Questions?** Open an issue or reach out to the lance-graph community.
