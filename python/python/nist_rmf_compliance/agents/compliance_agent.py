"""Claude agent for automated compliance evaluation.

This agent can be used as a Claude Code skill to provide intelligent
compliance assessment capabilities within the development workflow.
"""

from __future__ import annotations

import json
import logging
from typing import Dict, List, Any, Optional
from dataclasses import asdict

logger = logging.getLogger(__name__)


class ComplianceAgent:
    """Claude-powered agent for NIST RMF compliance tasks.

    Capabilities:
    - Analyze control requirements
    - Evaluate evidence quality
    - Generate compliance reports
    - Recommend remediation steps
    - Map controls to implementation
    """

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the compliance agent.

        Args:
            api_key: Anthropic API key (optional, uses env var if not provided)
        """
        self.api_key = api_key
        self._initialize_client()

    def _initialize_client(self):
        """Initialize Claude API client."""
        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=self.api_key)
            self.model = "claude-3-5-sonnet-20241022"
        except ImportError:
            logger.error("Anthropic package not installed")
            self.client = None

    def analyze_control(
        self,
        control_id: str,
        control_description: str,
        system_context: str,
    ) -> Dict[str, Any]:
        """Analyze a control and provide implementation guidance.

        Args:
            control_id: Control identifier (e.g., "AC-2")
            control_description: Full control description
            system_context: Description of the system/application

        Returns:
            Analysis with implementation recommendations
        """
        prompt = f"""You are a cybersecurity compliance expert analyzing NIST 800-53 controls.

Control: {control_id}
Description: {control_description}

System Context: {system_context}

Please provide:
1. A clear explanation of what this control requires
2. Specific implementation steps for this system
3. Types of evidence that should be collected
4. Common pitfalls to avoid
5. Related controls that should be considered together

Format your response as JSON with keys: explanation, implementation_steps (array), evidence_types (array), pitfalls (array), related_controls (array)
"""

        if not self.client:
            return {
                "error": "Claude client not initialized",
                "explanation": "Manual analysis required",
            }

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}]
            )

            # Extract JSON from response
            content = response.content[0].text

            # Try to parse JSON
            try:
                # Look for JSON in code blocks
                if "```json" in content:
                    json_start = content.find("```json") + 7
                    json_end = content.find("```", json_start)
                    json_str = content[json_start:json_end].strip()
                elif "```" in content:
                    json_start = content.find("```") + 3
                    json_end = content.find("```", json_start)
                    json_str = content[json_start:json_end].strip()
                else:
                    json_str = content

                analysis = json.loads(json_str)
                return analysis
            except json.JSONDecodeError:
                # Return raw content if not valid JSON
                return {
                    "explanation": content,
                    "note": "Response was not in JSON format",
                }

        except Exception as e:
            logger.error(f"Error calling Claude API: {e}")
            return {"error": str(e)}

    def evaluate_evidence(
        self,
        requirement: str,
        evidence_descriptions: List[str],
    ) -> Dict[str, Any]:
        """Evaluate if evidence adequately supports a requirement.

        Args:
            requirement: The specific requirement statement
            evidence_descriptions: List of evidence descriptions

        Returns:
            Evaluation results with adequacy assessment
        """
        evidence_list = "\n".join(f"- {e}" for e in evidence_descriptions)

        prompt = f"""You are evaluating compliance evidence.

Requirement: {requirement}

Available Evidence:
{evidence_list}

Evaluate:
1. Does the evidence adequately demonstrate compliance? (Yes/Partial/No)
2. What aspects are well-supported?
3. What gaps exist?
4. What additional evidence would strengthen the case?

Format as JSON: {{"adequacy": "Yes/Partial/No", "well_supported": [], "gaps": [], "additional_evidence_needed": []}}
"""

        if not self.client:
            return {"error": "Claude client not initialized"}

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}]
            )

            content = response.content[0].text

            # Parse JSON response
            try:
                if "```json" in content:
                    json_start = content.find("```json") + 7
                    json_end = content.find("```", json_start)
                    json_str = content[json_start:json_end].strip()
                else:
                    json_str = content

                evaluation = json.loads(json_str)
                return evaluation
            except json.JSONDecodeError:
                return {"evaluation": content}

        except Exception as e:
            logger.error(f"Error evaluating evidence: {e}")
            return {"error": str(e)}

    def generate_remediation_plan(
        self,
        control_id: str,
        current_status: str,
        findings: str,
    ) -> Dict[str, Any]:
        """Generate a remediation plan for non-compliant controls.

        Args:
            control_id: Control identifier
            current_status: Current compliance status
            findings: Assessment findings

        Returns:
            Remediation plan with prioritized actions
        """
        prompt = f"""You are creating a remediation plan for a non-compliant control.

Control: {control_id}
Current Status: {current_status}
Findings: {findings}

Generate a detailed remediation plan with:
1. Priority (High/Medium/Low)
2. Remediation steps (ordered list)
3. Estimated effort (hours or days)
4. Required resources/tools
5. Success criteria

Format as JSON: {{"priority": "", "steps": [], "estimated_effort": "", "resources": [], "success_criteria": []}}
"""

        if not self.client:
            return {"error": "Claude client not initialized"}

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1536,
                messages=[{"role": "user", "content": prompt}]
            )

            content = response.content[0].text

            try:
                if "```json" in content:
                    json_start = content.find("```json") + 7
                    json_end = content.find("```", json_start)
                    json_str = content[json_start:json_end].strip()
                else:
                    json_str = content

                plan = json.loads(json_str)
                return plan
            except json.JSONDecodeError:
                return {"plan": content}

        except Exception as e:
            logger.error(f"Error generating remediation plan: {e}")
            return {"error": str(e)}

    def map_control_to_codebase(
        self,
        control_id: str,
        control_description: str,
        codebase_summary: str,
    ) -> Dict[str, Any]:
        """Map a security control to relevant code/configuration locations.

        Args:
            control_id: Control identifier
            control_description: Control description
            codebase_summary: Summary of codebase structure

        Returns:
            Mapping of control to implementation locations
        """
        prompt = f"""You are mapping a security control to a codebase.

Control: {control_id}
Description: {control_description}

Codebase Structure:
{codebase_summary}

Identify:
1. Which files/modules likely implement this control
2. Configuration files that may be relevant
3. Test files that should exist
4. Documentation that should exist

Format as JSON: {{"implementation_files": [], "config_files": [], "test_files": [], "documentation": []}}
"""

        if not self.client:
            return {"error": "Claude client not initialized"}

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}]
            )

            content = response.content[0].text

            try:
                if "```json" in content:
                    json_start = content.find("```json") + 7
                    json_end = content.find("```", json_start)
                    json_str = content[json_start:json_end].strip()
                else:
                    json_str = content

                mapping = json.loads(json_str)
                return mapping
            except json.JSONDecodeError:
                return {"mapping": content}

        except Exception as e:
            logger.error(f"Error mapping control: {e}")
            return {"error": str(e)}
