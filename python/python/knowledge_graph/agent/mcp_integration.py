"""MCP (Model Context Protocol) integration for custom skills and context injection.

This module provides:
1. Custom skills/prompts (user-defined capabilities)
2. Persistent context/memory storage
3. Dynamic context injection into agent conversations
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MCPContextManager:
    """Manages custom context and skills via MCP servers.

    Supports:
    - Custom skills (reusable prompt templates)
    - User context (persistent memory/preferences)
    - Dynamic context injection
    """

    def __init__(
        self,
        context_file: Optional[Path] = None,
        skills_file: Optional[Path] = None,
    ):
        """Initialize MCP context manager.

        Args:
            context_file: Path to persistent context storage (JSONL format)
            skills_file: Path to custom skills definitions (YAML/JSON)
        """
        self.context_file = context_file or Path.cwd() / ".lance-graph" / "context.jsonl"
        self.skills_file = skills_file or Path.cwd() / ".lance-graph" / "skills.yaml"

        self.context_entries: List[Dict[str, Any]] = []
        self.skills: Dict[str, Dict[str, Any]] = {}

        self._load_context()
        self._load_skills()

    def _load_context(self) -> None:
        """Load persistent context from storage."""
        if not self.context_file.exists():
            logger.info(f"No context file found at {self.context_file}")
            return

        try:
            with self.context_file.open("r") as f:
                for line in f:
                    if line.strip():
                        entry = json.loads(line)
                        self.context_entries.append(entry)
            logger.info(f"Loaded {len(self.context_entries)} context entries")
        except Exception as e:
            logger.error(f"Failed to load context: {e}")

    def _load_skills(self) -> None:
        """Load custom skills from configuration."""
        if not self.skills_file.exists():
            logger.info(f"No skills file found at {self.skills_file}")
            return

        try:
            import yaml
            with self.skills_file.open("r") as f:
                self.skills = yaml.safe_load(f) or {}
            logger.info(f"Loaded {len(self.skills)} custom skills")
        except ImportError:
            logger.warning("PyYAML not available, skills not loaded")
        except Exception as e:
            logger.error(f"Failed to load skills: {e}")

    def add_context(
        self,
        content: str,
        category: str = "user_preference",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add a context entry to persistent storage.

        Args:
            content: The context content
            category: Category (e.g., "user_preference", "domain_knowledge", "constraint")
            metadata: Optional metadata (tags, timestamps, etc.)
        """
        entry = {
            "content": content,
            "category": category,
            "metadata": metadata or {},
        }

        self.context_entries.append(entry)

        # Persist to file
        try:
            self.context_file.parent.mkdir(parents=True, exist_ok=True)
            with self.context_file.open("a") as f:
                f.write(json.dumps(entry) + "\n")
            logger.info(f"Added context: {category} - {content[:50]}...")
        except Exception as e:
            logger.error(f"Failed to persist context: {e}")

    def get_context(
        self,
        category: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Retrieve context entries.

        Args:
            category: Filter by category (None = all)
            limit: Maximum entries to return

        Returns:
            List of context entries
        """
        entries = self.context_entries

        if category:
            entries = [e for e in entries if e.get("category") == category]

        return entries[-limit:]  # Most recent

    def clear_context(self, category: Optional[str] = None) -> None:
        """Clear context entries.

        Args:
            category: Clear only this category (None = all)
        """
        if category:
            self.context_entries = [
                e for e in self.context_entries
                if e.get("category") != category
            ]
        else:
            self.context_entries = []

        # Rewrite file
        try:
            with self.context_file.open("w") as f:
                for entry in self.context_entries:
                    f.write(json.dumps(entry) + "\n")
            logger.info(f"Cleared context: {category or 'all'}")
        except Exception as e:
            logger.error(f"Failed to clear context: {e}")

    def add_skill(
        self,
        name: str,
        description: str,
        prompt_template: str,
        parameters: Optional[List[str]] = None,
    ) -> None:
        """Add a custom skill (reusable prompt template).

        Args:
            name: Skill name (e.g., "analyze_timeline")
            description: What this skill does
            prompt_template: Template with {param} placeholders
            parameters: List of required parameters
        """
        self.skills[name] = {
            "description": description,
            "prompt_template": prompt_template,
            "parameters": parameters or [],
        }

        # Persist to file
        try:
            import yaml
            self.skills_file.parent.mkdir(parents=True, exist_ok=True)
            with self.skills_file.open("w") as f:
                yaml.dump(self.skills, f, default_flow_style=False)
            logger.info(f"Added skill: {name}")
        except Exception as e:
            logger.error(f"Failed to persist skill: {e}")

    def get_skill(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a skill definition by name."""
        return self.skills.get(name)

    def list_skills(self) -> List[str]:
        """List all available skill names."""
        return list(self.skills.keys())

    def apply_skill(self, name: str, **params: Any) -> str:
        """Apply a skill with parameters to generate a prompt.

        Args:
            name: Skill name
            **params: Parameter values

        Returns:
            Formatted prompt
        """
        skill = self.get_skill(name)
        if not skill:
            raise ValueError(f"Unknown skill: {name}")

        template = skill["prompt_template"]
        required_params = skill.get("parameters", [])

        # Validate parameters
        missing = set(required_params) - set(params.keys())
        if missing:
            raise ValueError(f"Missing parameters: {missing}")

        # Format template
        try:
            return template.format(**params)
        except KeyError as e:
            raise ValueError(f"Template error: {e}")

    def inject_context_into_messages(
        self,
        messages: List[Dict[str, str]],
        categories: Optional[List[str]] = None,
    ) -> List[Dict[str, str]]:
        """Inject context into conversation messages.

        Args:
            messages: Existing conversation messages
            categories: Which context categories to inject (None = all)

        Returns:
            Messages with context injected as a system message
        """
        if not self.context_entries:
            return messages

        # Get relevant context
        if categories:
            context = [
                e for e in self.context_entries
                if e.get("category") in categories
            ]
        else:
            context = self.context_entries[-10:]  # Last 10 entries

        if not context:
            return messages

        # Build context message
        context_parts = [
            "=== USER CONTEXT ===",
            "The user has provided the following persistent context:",
            "",
        ]

        for entry in context:
            category = entry.get("category", "general")
            content = entry.get("content", "")
            context_parts.append(f"[{category.upper()}] {content}")

        context_parts.append("\nUse this context to inform your responses.")

        context_message = {
            "role": "system",
            "content": "\n".join(context_parts)
        }

        # Insert after system prompt (position 1)
        modified = messages.copy()
        if len(modified) > 0 and modified[0].get("role") == "system":
            modified.insert(1, context_message)
        else:
            modified.insert(0, context_message)

        return modified


class MCPSkillsProvider:
    """Provides MCP-based skills to the agent as callable tools."""

    def __init__(self, context_manager: MCPContextManager):
        self.context_manager = context_manager

    def get_skill_tools(self) -> List[Dict[str, Any]]:
        """Convert skills to tool schemas for native function calling.

        Returns:
            List of tool schemas in OpenAI function calling format
        """
        tools = []

        for skill_name in self.context_manager.list_skills():
            skill = self.context_manager.get_skill(skill_name)
            if not skill:
                continue

            # Build parameter schema
            properties = {}
            required = []

            for param in skill.get("parameters", []):
                properties[param] = {
                    "type": "string",
                    "description": f"Value for {param}"
                }
                required.append(param)

            # Create tool schema
            tools.append({
                "type": "function",
                "function": {
                    "name": f"skill_{skill_name}",
                    "description": skill.get("description", "Custom skill"),
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required,
                    }
                }
            })

        return tools

    def execute_skill(self, skill_name: str, arguments: Dict[str, Any]) -> str:
        """Execute a skill and return the formatted prompt.

        Args:
            skill_name: Skill name (with or without "skill_" prefix)
            arguments: Skill parameters

        Returns:
            Formatted prompt from the skill template
        """
        # Remove "skill_" prefix if present
        if skill_name.startswith("skill_"):
            skill_name = skill_name[6:]

        return self.context_manager.apply_skill(skill_name, **arguments)
