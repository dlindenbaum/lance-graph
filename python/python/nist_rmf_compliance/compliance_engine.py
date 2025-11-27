"""Compliance evaluation engine powered by Claude agents."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Dict, Any
import uuid
import logging

from .models import (
    Control,
    Requirement,
    Evidence,
    AssessmentResult,
    ComplianceStatus,
)
from .graph_schema import RMFGraph

logger = logging.getLogger(__name__)


class ComplianceEngine:
    """Automated compliance evaluation using Claude agents.

    This engine analyzes evidence against requirements and provides
    intelligent compliance assessments.
    """

    def __init__(self, graph: RMFGraph, api_key: Optional[str] = None):
        """Initialize the compliance engine.

        Args:
            graph: RMF knowledge graph
            api_key: Anthropic API key for Claude (optional, uses env var if not provided)
        """
        self.graph = graph
        self.api_key = api_key
        self._initialize_claude_client()

    def _initialize_claude_client(self):
        """Initialize Claude API client."""
        try:
            import anthropic
            self.claude = anthropic.Anthropic(api_key=self.api_key)
            self.model = "claude-3-5-sonnet-20241022"
        except ImportError:
            logger.warning("Anthropic package not installed. Claude-powered features will be limited.")
            self.claude = None
            self.model = None

    def assess_control(
        self,
        control_id: str,
        system_id: str,
        evidence_list: List[Evidence],
        assessor: str = "claude-agent",
    ) -> AssessmentResult:
        """Assess compliance for a control using Claude.

        Args:
            control_id: Control identifier (e.g., "AC-2")
            system_id: System being assessed
            evidence_list: Evidence artifacts to evaluate
            assessor: Name of the assessor

        Returns:
            AssessmentResult with findings and recommendations
        """
        # Get control details from graph
        control_data = self.graph.get_control(control_id)

        if control_data.num_rows == 0:
            raise ValueError(f"Control {control_id} not found in graph")

        # Get requirements for this control
        requirements_data = self.graph.query(f"""
            MATCH (c:Control {{control_id: '{control_id}'}})-[:REQUIRES]->(r:Requirement)
            RETURN r.requirement_id, r.statement, r.testing_procedure
        """)

        # Build assessment prompt for Claude
        assessment_prompt = self._build_assessment_prompt(
            control_id,
            control_data,
            requirements_data,
            evidence_list,
        )

        # Get Claude's assessment
        if self.claude:
            findings, recommendations, status = self._evaluate_with_claude(assessment_prompt)
        else:
            findings, recommendations, status = self._evaluate_heuristic(
                control_id, evidence_list
            )

        # Create assessment result
        result = AssessmentResult(
            assessment_id=str(uuid.uuid4()),
            control_id=control_id,
            requirement_id=None,
            system_id=system_id,
            status=status,
            findings=findings,
            recommendations=recommendations,
            assessor=assessor,
            assessed_at=datetime.now(),
            evidence_ids=[e.evidence_id for e in evidence_list],
        )

        return result

    def _build_assessment_prompt(
        self,
        control_id: str,
        control_data: Any,
        requirements_data: Any,
        evidence_list: List[Evidence],
    ) -> str:
        """Build a comprehensive prompt for Claude to assess compliance."""
        prompt = f"""You are a cybersecurity compliance assessor evaluating NIST 800-53 control {control_id}.

## Control Information
Control ID: {control_id}
Title: {control_data['title'][0] if control_data.num_rows > 0 else 'N/A'}
Description: {control_data['description'][0] if control_data.num_rows > 0 else 'N/A'}

## Requirements to Assess
"""
        if requirements_data.num_rows > 0:
            for i in range(requirements_data.num_rows):
                req_id = requirements_data['requirement_id'][i]
                statement = requirements_data['statement'][i]
                procedure = requirements_data['testing_procedure'][i]
                prompt += f"""
Requirement {req_id}:
Statement: {statement}
Testing Procedure: {procedure}
"""

        prompt += "\n## Available Evidence\n"
        for evidence in evidence_list:
            prompt += f"""
Evidence ID: {evidence.evidence_id}
Type: {evidence.evidence_type.value}
Title: {evidence.title}
Description: {evidence.description}
"""
            if evidence.file_path:
                prompt += f"File: {evidence.file_path}\n"
            if evidence.url:
                prompt += f"URL: {evidence.url}\n"

        prompt += """
## Assessment Task
Analyze the provided evidence against the control requirements and provide:
1. Compliance Status (Satisfied/Partially Satisfied/Not Satisfied/Not Assessed)
2. Detailed Findings (what evidence was reviewed, what was found)
3. Recommendations (gaps identified, additional evidence needed)

Format your response as:
STATUS: [status]
FINDINGS: [detailed findings]
RECOMMENDATIONS: [specific recommendations]
"""
        return prompt

    def _evaluate_with_claude(self, prompt: str) -> tuple[str, str, ComplianceStatus]:
        """Evaluate compliance using Claude."""
        try:
            message = self.claude.messages.create(
                model=self.model,
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = message.content[0].text

            # Parse response
            status_line = [line for line in response_text.split('\n') if line.startswith('STATUS:')]
            findings_start = response_text.find('FINDINGS:')
            recommendations_start = response_text.find('RECOMMENDATIONS:')

            status_str = status_line[0].replace('STATUS:', '').strip() if status_line else "Not Assessed"
            findings = response_text[findings_start:recommendations_start].replace('FINDINGS:', '').strip() if findings_start != -1 else response_text
            recommendations = response_text[recommendations_start:].replace('RECOMMENDATIONS:', '').strip() if recommendations_start != -1 else "Review required"

            # Map status string to enum
            status = self._parse_compliance_status(status_str)

            return findings, recommendations, status

        except Exception as e:
            logger.error(f"Error calling Claude API: {e}")
            return (
                f"Error during automated assessment: {e}",
                "Manual review required",
                ComplianceStatus.NOT_ASSESSED,
            )

    def _evaluate_heuristic(
        self, control_id: str, evidence_list: List[Evidence]
    ) -> tuple[str, str, ComplianceStatus]:
        """Fallback heuristic evaluation when Claude is unavailable."""
        if not evidence_list:
            return (
                f"No evidence provided for {control_id}",
                "Collect and upload evidence artifacts",
                ComplianceStatus.NOT_ASSESSED,
            )

        findings = f"Found {len(evidence_list)} evidence artifacts for {control_id}:\n"
        for evidence in evidence_list:
            findings += f"- {evidence.title} ({evidence.evidence_type.value})\n"

        recommendations = "Manual review required. Claude agent not available."
        status = ComplianceStatus.PARTIALLY_SATISFIED if len(evidence_list) >= 2 else ComplianceStatus.NOT_SATISFIED

        return findings, recommendations, status

    def _parse_compliance_status(self, status_str: str) -> ComplianceStatus:
        """Parse status string to ComplianceStatus enum."""
        status_str = status_str.lower().strip()
        if "satisfied" in status_str and "not" not in status_str and "partial" not in status_str:
            return ComplianceStatus.SATISFIED
        elif "partially" in status_str or "partial" in status_str:
            return ComplianceStatus.PARTIALLY_SATISFIED
        elif "not satisfied" in status_str or "unsatisfied" in status_str:
            return ComplianceStatus.NOT_SATISFIED
        elif "not applicable" in status_str or "n/a" in status_str:
            return ComplianceStatus.NOT_APPLICABLE
        else:
            return ComplianceStatus.NOT_ASSESSED

    def batch_assess_system(
        self,
        system_id: str,
        control_ids: List[str],
    ) -> List[AssessmentResult]:
        """Assess multiple controls for a system.

        Args:
            system_id: System identifier
            control_ids: List of control IDs to assess

        Returns:
            List of assessment results
        """
        results = []
        for control_id in control_ids:
            try:
                # Get evidence for this control
                evidence_data = self.graph.get_control_evidence(control_id)

                # For this example, create stub evidence
                # In production, this would load actual evidence from the graph
                evidence_list = []

                result = self.assess_control(control_id, system_id, evidence_list)
                results.append(result)
                logger.info(f"Assessed {control_id}: {result.status.value}")

            except Exception as e:
                logger.error(f"Error assessing {control_id}: {e}")
                continue

        return results
