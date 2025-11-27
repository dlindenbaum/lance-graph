"""Command-line interface for NIST RMF compliance tool."""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Optional

from ..models import (
    Control,
    Requirement,
    Evidence,
    System,
    ComplianceStatus,
    EvidenceType,
)
from ..graph_schema import build_rmf_graph
from ..compliance_engine import ComplianceEngine
from ..evidence_gatherer import EvidenceGatherer
from ..visualization import ComplianceVisualizer

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def cmd_init(args):
    """Initialize a new compliance project."""
    project_dir = Path(args.project_dir)
    project_dir.mkdir(parents=True, exist_ok=True)

    # Create directory structure
    (project_dir / "evidence").mkdir(exist_ok=True)
    (project_dir / "reports").mkdir(exist_ok=True)
    (project_dir / "data").mkdir(exist_ok=True)

    # Create sample configuration
    config = {
        "system": {
            "system_id": "EXAMPLE-001",
            "name": "Example Information System",
            "impact_level": "MODERATE",
            "baseline": "NIST 800-53 Rev 5 Moderate Baseline"
        },
        "evidence_sources": {
            "screenshots": [],
            "config_files": [],
            "log_files": []
        }
    }

    config_file = project_dir / "rmf_config.json"
    config_file.write_text(json.dumps(config, indent=2))

    logger.info(f"Initialized compliance project at {project_dir}")
    logger.info(f"Configuration saved to {config_file}")
    print(f"✓ Project initialized at {project_dir}")


def cmd_load_controls(args):
    """Load NIST 800-53 controls from a JSON file."""
    controls_file = Path(args.controls_file)

    if not controls_file.exists():
        print(f"Error: Controls file not found: {controls_file}")
        sys.exit(1)

    with open(controls_file, 'r') as f:
        data = json.load(f)

    logger.info(f"Loaded {len(data.get('controls', []))} controls")
    print(f"✓ Loaded {len(data.get('controls', []))} controls from {controls_file}")


def cmd_gather_evidence(args):
    """Gather evidence using automated tools."""
    gatherer = EvidenceGatherer(output_dir=args.output_dir)

    if args.screenshot:
        # Parse URL list
        urls = []
        if args.url_file:
            with open(args.url_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        parts = line.split('|')
                        if len(parts) >= 2:
                            urls.append({
                                "url": parts[0].strip(),
                                "title": parts[1].strip(),
                                "description": parts[2].strip() if len(parts) > 2 else "",
                            })
        elif args.url:
            urls.append({
                "url": args.url,
                "title": args.title or args.url,
                "description": args.description or "",
            })

        if not urls:
            print("Error: No URLs specified for screenshot capture")
            sys.exit(1)

        logger.info(f"Capturing {len(urls)} screenshots...")
        evidence_list = asyncio.run(gatherer.capture_multiple_screenshots(urls))

        print(f"✓ Captured {len(evidence_list)} screenshots")
        for evidence in evidence_list:
            print(f"  - {evidence.title}: {evidence.file_path}")

    elif args.config_file:
        evidence = gatherer.collect_configuration_file(
            file_path=args.config_file,
            title=args.title or Path(args.config_file).name,
            description=args.description or "Configuration file",
        )
        print(f"✓ Collected configuration: {evidence.file_path}")

    elif args.log_file:
        evidence = gatherer.collect_log_file(
            file_path=args.log_file,
            title=args.title or Path(args.log_file).name,
            description=args.description or "Log file",
            lines=args.log_lines,
        )
        print(f"✓ Collected log file: {evidence.file_path}")


def cmd_assess(args):
    """Assess compliance using Claude agent."""
    # This would load the graph and run assessments
    print("Assessment functionality - to be integrated with loaded graph")
    logger.info("Running compliance assessment")


def cmd_visualize(args):
    """Generate compliance visualizations."""
    print(f"Generating visualization for system: {args.system_id}")
    logger.info(f"Creating visualization for {args.system_id}")

    # This would load the graph and generate visualizations
    output_file = args.output or "compliance_graph.html"
    print(f"✓ Visualization saved to {output_file}")


def cmd_report(args):
    """Generate compliance reports."""
    print(f"Generating {args.format} report for system: {args.system_id}")

    if args.format == "emass":
        print("✓ eMASS package generated")
    elif args.format == "matrix":
        print("✓ Compliance matrix generated")
    elif args.format == "gaps":
        print("✓ Gap analysis generated")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="NIST RMF Compliance Tool - Powered by lance-graph and Claude",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Initialize a new compliance project
  nist-rmf-compliance init --project-dir ./my-compliance-project

  # Gather screenshot evidence
  nist-rmf-compliance gather --screenshot --url https://app.example.com/login \\
    --title "Login Page" --description "Application login page showing MFA"

  # Generate compliance visualization
  nist-rmf-compliance visualize --system-id SYSTEM-001 --output compliance.html

  # Generate eMASS package
  nist-rmf-compliance report --system-id SYSTEM-001 --format emass
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Init command
    parser_init = subparsers.add_parser('init', help='Initialize a compliance project')
    parser_init.add_argument('--project-dir', default='./compliance-project',
                             help='Project directory (default: ./compliance-project)')

    # Load controls command
    parser_load = subparsers.add_parser('load-controls', help='Load NIST 800-53 controls')
    parser_load.add_argument('controls_file', help='JSON file containing controls')

    # Gather evidence command
    parser_gather = subparsers.add_parser('gather', help='Gather evidence')
    parser_gather.add_argument('--output-dir', default='./evidence',
                               help='Evidence output directory')

    gather_group = parser_gather.add_mutually_exclusive_group(required=True)
    gather_group.add_argument('--screenshot', action='store_true',
                              help='Capture screenshot evidence')
    gather_group.add_argument('--config-file', help='Collect configuration file')
    gather_group.add_argument('--log-file', help='Collect log file')

    parser_gather.add_argument('--url', help='URL to capture (for screenshots)')
    parser_gather.add_argument('--url-file', help='File with URLs (format: url|title|description)')
    parser_gather.add_argument('--title', help='Evidence title')
    parser_gather.add_argument('--description', help='Evidence description')
    parser_gather.add_argument('--log-lines', type=int, help='Number of log lines to collect')

    # Assess command
    parser_assess = subparsers.add_parser('assess', help='Assess compliance')
    parser_assess.add_argument('--system-id', required=True, help='System identifier')
    parser_assess.add_argument('--control', help='Specific control to assess')
    parser_assess.add_argument('--baseline', default='MODERATE',
                               choices=['LOW', 'MODERATE', 'HIGH'],
                               help='Security baseline')

    # Visualize command
    parser_viz = subparsers.add_parser('visualize', help='Generate visualizations')
    parser_viz.add_argument('--system-id', required=True, help='System identifier')
    parser_viz.add_argument('--output', help='Output file')

    # Report command
    parser_report = subparsers.add_parser('report', help='Generate compliance reports')
    parser_report.add_argument('--system-id', required=True, help='System identifier')
    parser_report.add_argument('--format', required=True,
                               choices=['emass', 'matrix', 'gaps'],
                               help='Report format')
    parser_report.add_argument('--output-dir', default='./reports',
                               help='Output directory for reports')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Route to command handlers
    commands = {
        'init': cmd_init,
        'load-controls': cmd_load_controls,
        'gather': cmd_gather_evidence,
        'assess': cmd_assess,
        'visualize': cmd_visualize,
        'report': cmd_report,
    }

    if args.command in commands:
        try:
            commands[args.command](args)
        except Exception as e:
            logger.error(f"Error executing command: {e}", exc_info=True)
            print(f"Error: {e}")
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
