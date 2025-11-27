"""Example: NIST RMF Compliance Tool with lance-graph.

This example demonstrates how to use the NIST RMF compliance tool to:
1. Model security controls as a graph
2. Track evidence and assessments
3. Generate compliance visualizations
4. Use Claude agents for automated assessment
"""

import asyncio
from datetime import datetime
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "python" / "python"))

from nist_rmf_compliance.models import (
    Control,
    Requirement,
    Evidence,
    System,
    AssessmentResult,
    ControlImplementation,
    ComplianceStatus,
    EvidenceType,
)
from nist_rmf_compliance.graph_schema import build_rmf_graph
from nist_rmf_compliance.compliance_engine import ComplianceEngine
from nist_rmf_compliance.evidence_gatherer import EvidenceGatherer
from nist_rmf_compliance.visualization import ComplianceVisualizer


def create_sample_data():
    """Create sample NIST 800-53 controls and system data."""

    # Sample controls from NIST 800-53
    controls = [
        Control(
            control_id="AC-1",
            family="Access Control",
            title="Policy and Procedures",
            description="Develop, document, and disseminate access control policy and procedures.",
            baseline=["LOW", "MODERATE", "HIGH"],
            priority="P1",
            related_controls=["AC-2", "AC-3"],
        ),
        Control(
            control_id="AC-2",
            family="Access Control",
            title="Account Management",
            description="Manage information system accounts including establishing, activating, modifying, reviewing, disabling, and removing accounts.",
            baseline=["LOW", "MODERATE", "HIGH"],
            priority="P1",
            related_controls=["AC-1", "AC-3", "IA-4"],
        ),
        Control(
            control_id="AC-3",
            family="Access Control",
            title="Access Enforcement",
            description="Enforce approved authorizations for logical access to information and system resources.",
            baseline=["LOW", "MODERATE", "HIGH"],
            priority="P1",
            related_controls=["AC-2", "AC-4"],
        ),
        Control(
            control_id="AU-2",
            family="Audit and Accountability",
            title="Event Logging",
            description="Identify the types of events that the system is capable of logging.",
            baseline=["LOW", "MODERATE", "HIGH"],
            priority="P1",
            related_controls=["AU-3", "AU-6"],
        ),
        Control(
            control_id="IA-2",
            family="Identification and Authentication",
            title="Identification and Authentication",
            description="Uniquely identify and authenticate organizational users.",
            baseline=["LOW", "MODERATE", "HIGH"],
            priority="P1",
            related_controls=["IA-4", "IA-5"],
        ),
    ]

    # Sample requirements
    requirements = [
        Requirement(
            requirement_id="AC-1.a",
            control_id="AC-1",
            statement="Develop and document an access control policy.",
            testing_procedure="Examine access control policy documentation.",
            expected_evidence=["Policy Document", "Approval Records"],
        ),
        Requirement(
            requirement_id="AC-2.a",
            control_id="AC-2",
            statement="Identify account types and establish conditions for group membership.",
            testing_procedure="Review account management procedures and examine account records.",
            expected_evidence=["Account Management Procedures", "Account Inventory"],
        ),
        Requirement(
            requirement_id="AC-2.b",
            control_id="AC-2",
            statement="Assign account managers and specify authorized account users.",
            testing_procedure="Examine account management documentation and user records.",
            expected_evidence=["Role Assignments", "User Access Reviews"],
        ),
        Requirement(
            requirement_id="AC-3.a",
            control_id="AC-3",
            statement="Enforce approved authorizations for logical access.",
            testing_procedure="Test access control mechanisms and review authorization records.",
            expected_evidence=["Access Control Configuration", "Authorization Matrix"],
        ),
    ]

    # Sample system
    systems = [
        System(
            system_id="WEB-APP-001",
            name="Customer Portal Web Application",
            description="Public-facing web application for customer account management",
            impact_level="MODERATE",
            system_type="Major Application",
            authorization_boundary="Web application and database",
        )
    ]

    # Sample evidence (would be collected automatically)
    evidence = [
        Evidence(
            evidence_id="EV-001",
            evidence_type=EvidenceType.DOCUMENT,
            title="Access Control Policy v2.1",
            description="Organization-wide access control policy approved by CISO",
            file_path="./evidence/access_control_policy_v2.1.pdf",
            collected_at=datetime(2024, 1, 15),
        ),
        Evidence(
            evidence_id="EV-002",
            evidence_type=EvidenceType.SCREENSHOT,
            title="User Management Interface",
            description="Screenshot of admin panel showing user account management",
            file_path="./evidence/user_mgmt_screenshot.png",
            url="https://portal.example.com/admin/users",
            collected_at=datetime(2024, 11, 20),
        ),
        Evidence(
            evidence_id="EV-003",
            evidence_type=EvidenceType.CONFIGURATION,
            title="RBAC Configuration",
            description="Role-based access control configuration file",
            file_path="./evidence/rbac_config.yaml",
            collected_at=datetime(2024, 11, 15),
        ),
    ]

    # Sample implementations
    implementations = [
        ControlImplementation(
            implementation_id="IMPL-001",
            control_id="AC-1",
            system_id="WEB-APP-001",
            implementation_status="Implemented",
            implementation_description="Access control policy documented and implemented via RBAC",
            responsible_role="Security Team",
            implementation_date=datetime(2024, 1, 15),
        ),
        ControlImplementation(
            implementation_id="IMPL-002",
            control_id="AC-2",
            system_id="WEB-APP-001",
            implementation_status="Implemented",
            implementation_description="Account management via centralized identity provider",
            responsible_role="Security Team",
            implementation_date=datetime(2024, 2, 1),
        ),
        ControlImplementation(
            implementation_id="IMPL-003",
            control_id="AC-3",
            system_id="WEB-APP-001",
            implementation_status="Implemented",
            implementation_description="RBAC enforced at application and database layers",
            responsible_role="Development Team",
            implementation_date=datetime(2024, 2, 15),
        ),
        ControlImplementation(
            implementation_id="IMPL-004",
            control_id="AU-2",
            system_id="WEB-APP-001",
            implementation_status="Planned",
            implementation_description="Comprehensive audit logging implementation in progress",
            responsible_role="Development Team",
        ),
    ]

    # Sample assessments
    assessments = [
        AssessmentResult(
            assessment_id="ASSESS-001",
            control_id="AC-1",
            requirement_id="AC-1.a",
            system_id="WEB-APP-001",
            status=ComplianceStatus.SATISFIED,
            findings="Access control policy is well-documented and approved. Policy covers all required elements.",
            recommendations="Continue annual policy reviews as scheduled.",
            assessor="Security Assessor",
            assessed_at=datetime(2024, 11, 1),
            evidence_ids=["EV-001"],
        ),
        AssessmentResult(
            assessment_id="ASSESS-002",
            control_id="AC-2",
            requirement_id="AC-2.a",
            system_id="WEB-APP-001",
            status=ComplianceStatus.SATISFIED,
            findings="Account management procedures in place. Identity provider integration working correctly.",
            recommendations="Add automated quarterly access reviews.",
            assessor="Security Assessor",
            assessed_at=datetime(2024, 11, 10),
            evidence_ids=["EV-002"],
        ),
        AssessmentResult(
            assessment_id="ASSESS-003",
            control_id="AC-3",
            requirement_id="AC-3.a",
            system_id="WEB-APP-001",
            status=ComplianceStatus.PARTIALLY_SATISFIED,
            findings="RBAC implemented but some legacy endpoints lack proper authorization checks.",
            recommendations="Audit all API endpoints and add authorization middleware to legacy routes.",
            assessor="Security Assessor",
            assessed_at=datetime(2024, 11, 15),
            evidence_ids=["EV-003"],
        ),
    ]

    return controls, requirements, evidence, systems, assessments, implementations


async def demonstrate_evidence_gathering():
    """Demonstrate automated evidence gathering."""
    print("\n=== Evidence Gathering Demo ===\n")

    gatherer = EvidenceGatherer(output_dir="./example_evidence")

    # Example: Capture screenshots (would use real URLs in production)
    screenshot_targets = [
        {
            "url": "https://example.com",
            "title": "Example.com Homepage",
            "description": "Public homepage showing security features",
        },
    ]

    print("Capturing screenshots...")
    try:
        evidence_list = await gatherer.capture_multiple_screenshots(screenshot_targets)
        print(f"✓ Captured {len(evidence_list)} screenshots")
        for ev in evidence_list:
            print(f"  - {ev.title}: {ev.file_path}")
    except Exception as e:
        print(f"Note: Screenshot capture requires Playwright: {e}")

    await gatherer.close()


def main():
    """Main demonstration function."""
    print("=" * 70)
    print("NIST RMF Compliance Tool - Powered by lance-graph and Claude")
    print("=" * 70)

    # Create sample data
    print("\n=== Creating Sample Data ===\n")
    controls, requirements, evidence, systems, assessments, implementations = create_sample_data()

    print(f"✓ Created {len(controls)} controls")
    print(f"✓ Created {len(requirements)} requirements")
    print(f"✓ Created {len(evidence)} evidence artifacts")
    print(f"✓ Created {len(systems)} systems")
    print(f"✓ Created {len(assessments)} assessments")
    print(f"✓ Created {len(implementations)} implementations")

    # Build the RMF graph
    print("\n=== Building RMF Knowledge Graph ===\n")
    rmf_graph = build_rmf_graph(
        controls=controls,
        requirements=requirements,
        evidence=evidence,
        systems=systems,
        assessments=assessments,
        implementations=implementations,
    )
    print("✓ RMF graph built successfully")

    # Query the graph
    print("\n=== Querying the Graph ===\n")

    print("Controls implemented by WEB-APP-001:")
    system_controls = rmf_graph.get_system_controls("WEB-APP-001")
    print(system_controls.to_pandas())

    print("\nCompliance status for WEB-APP-001:")
    compliance_status = rmf_graph.get_compliance_status("WEB-APP-001")
    print(compliance_status.to_pandas())

    print("\nGap analysis for WEB-APP-001 (MODERATE baseline):")
    gaps = rmf_graph.find_gaps("WEB-APP-001", "MODERATE")
    print(gaps.to_pandas())

    # Generate visualizations
    print("\n=== Generating Visualizations ===\n")
    visualizer = ComplianceVisualizer(rmf_graph)

    # Generate HTML visualization
    html_file = visualizer.generate_html_visualization("WEB-APP-001", "compliance_graph.html")
    print(f"✓ HTML visualization: {html_file}")

    # Generate compliance matrix
    matrix = visualizer.generate_compliance_matrix("WEB-APP-001")
    print(f"✓ Compliance matrix generated: {len(matrix)} families")

    # Generate gap analysis
    gap_analysis = visualizer.generate_gap_analysis("WEB-APP-001", "MODERATE")
    print(f"✓ Gap analysis: {gap_analysis['total_gaps']} gaps found")

    # Export eMASS package
    emass_dir = visualizer.export_emass_package("WEB-APP-001", "./emass_package")
    print(f"✓ eMASS package exported to: {emass_dir}")

    # Demonstrate Claude agent (if API key available)
    print("\n=== Claude Agent Demo ===\n")
    try:
        from nist_rmf_compliance.agents import ComplianceAgent

        agent = ComplianceAgent()
        print("✓ Claude agent initialized")
        print("  (Set ANTHROPIC_API_KEY to enable AI-powered assessment)")

        # Example analysis (would use actual API if key is set)
        print("\nExample: Analyzing AC-2 control...")
        analysis = agent.analyze_control(
            control_id="AC-2",
            control_description="Manage information system accounts",
            system_context="Web application with user authentication",
        )

        if "error" not in analysis:
            print("✓ Control analysis complete")
        else:
            print(f"Note: {analysis.get('explanation', 'API key needed')}")

    except Exception as e:
        print(f"Note: Claude agent demo skipped: {e}")

    # Demonstrate evidence gathering
    print("\n")
    asyncio.run(demonstrate_evidence_gathering())

    print("\n=== Demo Complete ===\n")
    print("Next steps:")
    print("1. Review generated files:")
    print("   - compliance_graph.html (interactive visualization)")
    print("   - emass_package/ (eMASS-compatible package)")
    print("2. Set ANTHROPIC_API_KEY to enable AI-powered assessment")
    print("3. Install Playwright for screenshot capture: pip install playwright && playwright install")
    print("4. Explore the CLI: python -m nist_rmf_compliance.cli.main --help")


if __name__ == "__main__":
    main()
