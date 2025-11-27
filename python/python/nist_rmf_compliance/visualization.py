"""Visualization utilities for RMF compliance graphs."""

from __future__ import annotations

import json
from typing import Dict, List, Any, Optional
from pathlib import Path

from .graph_schema import RMFGraph
from .models import ComplianceStatus


class ComplianceVisualizer:
    """Generate visualizations of compliance data for reporting and eMASS packages.

    Outputs:
    - HTML interactive graphs
    - Cytoscape.js JSON for web visualization
    - Compliance status dashboards
    - Control traceability matrices
    """

    def __init__(self, graph: RMFGraph):
        """Initialize visualizer with an RMF graph."""
        self.graph = graph

    def generate_cytoscape_json(self, system_id: str) -> Dict[str, Any]:
        """Generate Cytoscape.js compatible JSON for web visualization.

        Args:
            system_id: System to visualize

        Returns:
            Dictionary with 'elements' key containing nodes and edges
        """
        # Get controls implemented by the system
        controls_data = self.graph.get_system_controls(system_id)

        # Get compliance status
        status_data = self.graph.get_compliance_status(system_id)

        # Build nodes
        nodes = []
        edges = []

        # System node
        nodes.append({
            "data": {
                "id": system_id,
                "label": system_id,
                "type": "system",
            },
            "classes": "system",
        })

        # Control nodes with status
        status_map = {}
        if status_data.num_rows > 0:
            for i in range(status_data.num_rows):
                control_id = status_data['control_id'][i]
                status_map[control_id] = status_data['status'][i]

        if controls_data.num_rows > 0:
            for i in range(controls_data.num_rows):
                control_id = controls_data['control_id'][i]
                title = controls_data['title'][i]
                family = controls_data['family'][i]
                status = status_map.get(control_id, "Not Assessed")

                nodes.append({
                    "data": {
                        "id": control_id,
                        "label": control_id,
                        "title": title,
                        "family": family,
                        "status": status,
                        "type": "control",
                    },
                    "classes": f"control {self._status_to_class(status)}",
                })

                # Edge from system to control
                edges.append({
                    "data": {
                        "id": f"{system_id}-{control_id}",
                        "source": system_id,
                        "target": control_id,
                        "label": "IMPLEMENTS",
                    },
                })

        # Get control relationships
        for node in nodes:
            if node["data"].get("type") == "control":
                control_id = node["data"]["id"]
                related_data = self.graph.get_control_relationships(control_id)

                if related_data.num_rows > 0:
                    for i in range(related_data.num_rows):
                        related_id = related_data['control_id'][i]
                        edges.append({
                            "data": {
                                "id": f"{control_id}-{related_id}",
                                "source": control_id,
                                "target": related_id,
                                "label": "RELATES_TO",
                            },
                        })

        return {
            "elements": {
                "nodes": nodes,
                "edges": edges,
            }
        }

    def _status_to_class(self, status: str) -> str:
        """Map compliance status to CSS class."""
        status_lower = status.lower()
        if "satisfied" in status_lower and "not" not in status_lower and "partial" not in status_lower:
            return "satisfied"
        elif "partially" in status_lower:
            return "partial"
        elif "not" in status_lower or "unsatisfied" in status_lower:
            return "unsatisfied"
        else:
            return "not-assessed"

    def generate_html_visualization(
        self,
        system_id: str,
        output_file: str = "compliance_graph.html",
    ) -> str:
        """Generate interactive HTML visualization using Cytoscape.js.

        Args:
            system_id: System to visualize
            output_file: Output HTML file path

        Returns:
            Path to generated HTML file
        """
        cytoscape_data = self.generate_cytoscape_json(system_id)

        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>NIST RMF Compliance Graph - {system_id}</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/cytoscape/3.26.0/cytoscape.min.js"></script>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        h1 {{
            color: #333;
            margin-bottom: 10px;
        }}
        #cy {{
            width: 100%;
            height: 800px;
            background-color: white;
            border: 1px solid #ddd;
            border-radius: 4px;
        }}
        .legend {{
            margin-top: 20px;
            padding: 15px;
            background-color: white;
            border: 1px solid #ddd;
            border-radius: 4px;
        }}
        .legend-item {{
            display: inline-block;
            margin-right: 20px;
            margin-bottom: 10px;
        }}
        .legend-color {{
            display: inline-block;
            width: 20px;
            height: 20px;
            margin-right: 5px;
            vertical-align: middle;
            border-radius: 3px;
        }}
        .satisfied {{ background-color: #4CAF50; }}
        .partial {{ background-color: #FFC107; }}
        .unsatisfied {{ background-color: #F44336; }}
        .not-assessed {{ background-color: #9E9E9E; }}
        .system-color {{ background-color: #2196F3; }}
    </style>
</head>
<body>
    <h1>NIST RMF Compliance Graph</h1>
    <p><strong>System:</strong> {system_id}</p>
    <div id="cy"></div>
    <div class="legend">
        <strong>Legend:</strong>
        <div class="legend-item">
            <span class="legend-color system-color"></span> System
        </div>
        <div class="legend-item">
            <span class="legend-color satisfied"></span> Satisfied
        </div>
        <div class="legend-item">
            <span class="legend-color partial"></span> Partially Satisfied
        </div>
        <div class="legend-item">
            <span class="legend-color unsatisfied"></span> Not Satisfied
        </div>
        <div class="legend-item">
            <span class="legend-color not-assessed"></span> Not Assessed
        </div>
    </div>
    <script>
        var cy = cytoscape({{
            container: document.getElementById('cy'),
            elements: {json.dumps(cytoscape_data['elements'])},
            style: [
                {{
                    selector: 'node',
                    style: {{
                        'label': 'data(label)',
                        'text-valign': 'center',
                        'text-halign': 'center',
                        'font-size': '12px',
                        'width': '80px',
                        'height': '80px',
                        'border-width': 2,
                        'border-color': '#333',
                    }}
                }},
                {{
                    selector: 'node.system',
                    style: {{
                        'background-color': '#2196F3',
                        'width': '100px',
                        'height': '100px',
                        'font-weight': 'bold',
                    }}
                }},
                {{
                    selector: 'node.control',
                    style: {{
                        'shape': 'roundrectangle',
                    }}
                }},
                {{
                    selector: 'node.satisfied',
                    style: {{
                        'background-color': '#4CAF50',
                    }}
                }},
                {{
                    selector: 'node.partial',
                    style: {{
                        'background-color': '#FFC107',
                    }}
                }},
                {{
                    selector: 'node.unsatisfied',
                    style: {{
                        'background-color': '#F44336',
                    }}
                }},
                {{
                    selector: 'node.not-assessed',
                    style: {{
                        'background-color': '#9E9E9E',
                    }}
                }},
                {{
                    selector: 'edge',
                    style: {{
                        'width': 2,
                        'line-color': '#ccc',
                        'target-arrow-color': '#ccc',
                        'target-arrow-shape': 'triangle',
                        'curve-style': 'bezier',
                        'label': 'data(label)',
                        'font-size': '10px',
                        'text-rotation': 'autorotate',
                    }}
                }},
            ],
            layout: {{
                name: 'cose',
                idealEdgeLength: 100,
                nodeOverlap: 20,
                refresh: 20,
                fit: true,
                padding: 30,
                randomize: false,
                componentSpacing: 100,
                nodeRepulsion: 400000,
                edgeElasticity: 100,
                nestingFactor: 5,
                gravity: 80,
                numIter: 1000,
                initialTemp: 200,
                coolingFactor: 0.95,
                minTemp: 1.0,
            }}
        }});

        // Add tooltips
        cy.on('tap', 'node', function(evt) {{
            var node = evt.target;
            var data = node.data();
            var info = 'ID: ' + data.id;
            if (data.title) info += '\\nTitle: ' + data.title;
            if (data.family) info += '\\nFamily: ' + data.family;
            if (data.status) info += '\\nStatus: ' + data.status;
            alert(info);
        }});
    </script>
</body>
</html>
"""

        output_path = Path(output_file)
        output_path.write_text(html_content)
        return str(output_path)

    def generate_compliance_matrix(self, system_id: str) -> Dict[str, Any]:
        """Generate a control traceability matrix.

        Args:
            system_id: System identifier

        Returns:
            Dictionary with control families and their compliance status
        """
        status_data = self.graph.get_compliance_status(system_id)

        matrix = {}
        if status_data.num_rows > 0:
            for i in range(status_data.num_rows):
                control_id = status_data['control_id'][i]
                title = status_data['title'][i]
                family = status_data['family'][i]
                status = status_data['status'][i]

                if family not in matrix:
                    matrix[family] = []

                matrix[family].append({
                    "control_id": control_id,
                    "title": title,
                    "status": status,
                })

        return matrix

    def generate_gap_analysis(self, system_id: str, baseline: str = "MODERATE") -> Dict[str, Any]:
        """Generate gap analysis report.

        Args:
            system_id: System identifier
            baseline: Security baseline (LOW/MODERATE/HIGH)

        Returns:
            Dictionary with gap analysis results
        """
        gaps_data = self.graph.find_gaps(system_id, baseline)

        gaps = {
            "total_gaps": gaps_data.num_rows,
            "not_implemented": [],
            "not_assessed": [],
        }

        if gaps_data.num_rows > 0:
            for i in range(gaps_data.num_rows):
                control_id = gaps_data['control_id'][i]
                title = gaps_data['title'][i]
                impl_status = gaps_data['impl_status'][i]
                assessment_status = gaps_data['assessment_status'][i]

                gap_item = {
                    "control_id": control_id,
                    "title": title,
                    "implementation_status": impl_status,
                    "assessment_status": assessment_status,
                }

                if impl_status == "Not Implemented":
                    gaps["not_implemented"].append(gap_item)
                if assessment_status == "Not Assessed":
                    gaps["not_assessed"].append(gap_item)

        return gaps

    def export_emass_package(
        self,
        system_id: str,
        output_dir: str = "./emass_package",
    ) -> str:
        """Export compliance data in eMASS-compatible format.

        Args:
            system_id: System identifier
            output_dir: Output directory for package

        Returns:
            Path to package directory
        """
        package_dir = Path(output_dir)
        package_dir.mkdir(parents=True, exist_ok=True)

        # Generate compliance matrix
        matrix = self.generate_compliance_matrix(system_id)
        matrix_file = package_dir / "compliance_matrix.json"
        matrix_file.write_text(json.dumps(matrix, indent=2))

        # Generate gap analysis
        gaps = self.generate_gap_analysis(system_id)
        gaps_file = package_dir / "gap_analysis.json"
        gaps_file.write_text(json.dumps(gaps, indent=2))

        # Generate visualization
        viz_file = package_dir / "compliance_graph.html"
        self.generate_html_visualization(system_id, str(viz_file))

        # Generate summary report
        summary = {
            "system_id": system_id,
            "generated_at": str(datetime.now()),
            "total_controls": sum(len(controls) for controls in matrix.values()),
            "families": list(matrix.keys()),
            "total_gaps": gaps["total_gaps"],
        }
        summary_file = package_dir / "package_summary.json"
        summary_file.write_text(json.dumps(summary, indent=2))

        return str(package_dir)


from datetime import datetime
