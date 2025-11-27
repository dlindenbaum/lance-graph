---
name: nist-rmf
description: Assess NIST 800-53 compliance for codebases and systems
---

# NIST RMF Compliance Assessment Skill

This skill provides intelligent NIST 800-53 Risk Management Framework (RMF) compliance assessment capabilities.

## Capabilities

- **Analyze Security Controls**: Explain NIST 800-53 control requirements and implementation guidance
- **Map Controls to Code**: Identify which parts of the codebase implement specific security controls
- **Evidence Collection**: Suggest evidence types needed for compliance assessment
- **Gap Analysis**: Identify missing controls or inadequate implementations
- **Remediation Guidance**: Provide step-by-step remediation plans

## Usage

Invoke this skill when the user asks about:
- NIST 800-53 compliance
- Security control implementation
- ATO (Authorization to Operate) requirements
- RMF process support
- eMASS package preparation
- Control assessment or evidence needs

## Commands

The tool is available via:
```bash
nist-rmf-compliance --help
```

### Common Operations

**Analyze a control:**
```python
from nist_rmf_compliance.agents import ComplianceAgent

agent = ComplianceAgent()
analysis = agent.analyze_control(
    control_id="AC-2",
    control_description="Account Management requirements",
    system_context="Description of the system/application"
)
```

**Map control to codebase:**
```python
mapping = agent.map_control_to_codebase(
    control_id="AC-2",
    control_description="Account management...",
    codebase_summary="Summary of repo structure and key files"
)
```

**Evaluate evidence:**
```python
evaluation = agent.evaluate_evidence(
    requirement="System must enforce MFA for all users",
    evidence_descriptions=["Screenshot of login page", "SSO config file"]
)
```

**Generate remediation plan:**
```python
plan = agent.generate_remediation_plan(
    control_id="AC-2",
    current_status="Partially Satisfied",
    findings="MFA not enforced for admin accounts"
)
```

## Graph-Based Analysis

The tool uses lance-graph to model compliance as a knowledge graph:

```python
from nist_rmf_compliance import build_rmf_graph, ComplianceVisualizer

# Build graph from controls, evidence, assessments
graph = build_rmf_graph(controls, requirements, evidence, systems, assessments, implementations)

# Query with Cypher
gaps = graph.find_gaps("SYSTEM-001", baseline="MODERATE")

# Generate visualizations
viz = ComplianceVisualizer(graph)
viz.generate_html_visualization("SYSTEM-001")
viz.export_emass_package("SYSTEM-001")
```

## Example Queries to Answer

When this skill is invoked, help answer questions like:

- "What does AC-2 require and how should we implement it?"
- "Which files in this codebase implement authentication controls?"
- "What evidence do we need for IA-2 (Identification and Authentication)?"
- "Are we compliant with the MODERATE baseline?"
- "Generate a remediation plan for failed controls"
- "Show me a graph of control relationships"

## Integration Points

- **Code Analysis**: Scan the codebase to identify security-relevant code
- **Evidence Gathering**: Suggest screenshot locations, config files to capture
- **Documentation**: Generate compliance documentation from code
- **Gap Identification**: Compare implemented controls vs required baseline

## Technical Details

**Models**: Uses Claude 3.5 Sonnet for intelligent assessment
**Graph Engine**: lance-graph with Cypher query support
**Evidence Tools**: Playwright for screenshot automation
**Output Formats**: HTML visualizations, JSON reports, eMASS packages

## Important Notes

- Set `ANTHROPIC_API_KEY` environment variable for AI-powered features
- Install Playwright for screenshot capture: `pip install playwright && playwright install`
- See `examples/nist_rmf_example.py` for complete usage example
- Full documentation: `python/python/nist_rmf_compliance/README.md`

## Response Pattern

When helping with compliance:
1. First understand which control(s) are relevant
2. Analyze the codebase for related implementations
3. Identify what evidence exists or is needed
4. Provide specific, actionable guidance
5. Suggest Cypher queries for deeper analysis if helpful

Always ground recommendations in the specific system context and codebase structure.
