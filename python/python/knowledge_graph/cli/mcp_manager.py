"""CLI tool for managing MCP context and skills.

Usage:
    python -m knowledge_graph.cli.mcp_manager context add "Your context here" --category user_preference
    python -m knowledge_graph.cli.mcp_manager context list
    python -m knowledge_graph.cli.mcp_manager context clear --category user_preference

    python -m knowledge_graph.cli.mcp_manager skills list
    python -m knowledge_graph.cli.mcp_manager skills add analyze_network "Analyze network topology" --template "..." --params entity
    python -m knowledge_graph.cli.mcp_manager skills test analyze_timeline --entity_type Person --target "John Smith" --table_name calls
"""

import argparse
import sys
from pathlib import Path

from ..agent.mcp_integration import MCPContextManager


def setup_context_commands(subparsers):
    """Set up context management commands."""
    context_parser = subparsers.add_parser("context", help="Manage persistent context")
    context_subparsers = context_parser.add_subparsers(dest="context_command")

    # context add
    add_parser = context_subparsers.add_parser("add", help="Add context entry")
    add_parser.add_argument("content", help="Context content")
    add_parser.add_argument(
        "--category",
        default="user_preference",
        choices=["user_preference", "domain_knowledge", "constraint", "general"],
        help="Context category",
    )
    add_parser.add_argument("--metadata", help="JSON metadata")

    # context list
    list_parser = context_subparsers.add_parser("list", help="List context entries")
    list_parser.add_argument("--category", help="Filter by category")
    list_parser.add_argument("--limit", type=int, default=20, help="Max entries to show")

    # context clear
    clear_parser = context_subparsers.add_parser("clear", help="Clear context entries")
    clear_parser.add_argument("--category", help="Clear only this category")


def setup_skills_commands(subparsers):
    """Set up skills management commands."""
    skills_parser = subparsers.add_parser("skills", help="Manage custom skills")
    skills_subparsers = skills_parser.add_subparsers(dest="skills_command")

    # skills list
    skills_subparsers.add_parser("list", help="List all skills")

    # skills add
    add_parser = skills_subparsers.add_parser("add", help="Add a new skill")
    add_parser.add_argument("name", help="Skill name")
    add_parser.add_argument("description", help="Skill description")
    add_parser.add_argument("--template", required=True, help="Prompt template")
    add_parser.add_argument("--params", nargs="+", help="Required parameters")

    # skills show
    show_parser = skills_subparsers.add_parser("show", help="Show skill details")
    show_parser.add_argument("name", help="Skill name")

    # skills test
    test_parser = skills_subparsers.add_parser("test", help="Test a skill")
    test_parser.add_argument("name", help="Skill name")
    test_parser.add_argument("params", nargs="*", help="Parameters as key=value pairs")


def handle_context_command(args, manager: MCPContextManager):
    """Handle context management commands."""
    if args.context_command == "add":
        import json

        metadata = json.loads(args.metadata) if args.metadata else {}
        manager.add_context(args.content, args.category, metadata)
        print(f"✓ Added context to category '{args.category}'")

    elif args.context_command == "list":
        entries = manager.get_context(args.category, args.limit)
        if not entries:
            print("No context entries found")
            return

        print(f"\n{'Category':<20} {'Content':<60}")
        print("=" * 82)
        for entry in entries:
            category = entry.get("category", "general")
            content = entry.get("content", "")[:57] + "..."
            print(f"{category:<20} {content:<60}")

        print(f"\nTotal: {len(entries)} entries")

    elif args.context_command == "clear":
        manager.clear_context(args.category)
        target = args.category or "all"
        print(f"✓ Cleared context: {target}")


def handle_skills_command(args, manager: MCPContextManager):
    """Handle skills management commands."""
    if args.skills_command == "list":
        skills = manager.list_skills()
        if not skills:
            print("No custom skills found")
            return

        print(f"\n{'Skill Name':<30} {'Parameters':<30}")
        print("=" * 62)
        for skill_name in skills:
            skill = manager.get_skill(skill_name)
            params = ", ".join(skill.get("parameters", []))
            print(f"{skill_name:<30} {params:<30}")

        print(f"\nTotal: {len(skills)} skills")

    elif args.skills_command == "add":
        manager.add_skill(
            args.name,
            args.description,
            args.template,
            args.params or [],
        )
        print(f"✓ Added skill '{args.name}'")

    elif args.skills_command == "show":
        skill = manager.get_skill(args.name)
        if not skill:
            print(f"Skill '{args.name}' not found")
            return

        print(f"\nSkill: {args.name}")
        print(f"Description: {skill.get('description')}")
        print(f"Parameters: {', '.join(skill.get('parameters', []))}")
        print(f"\nTemplate:\n{skill.get('prompt_template')}")

    elif args.skills_command == "test":
        skill = manager.get_skill(args.name)
        if not skill:
            print(f"Skill '{args.name}' not found")
            return

        # Parse key=value params
        params_dict = {}
        for param in args.params:
            if "=" not in param:
                print(f"Invalid parameter format: {param} (use key=value)")
                return
            key, value = param.split("=", 1)
            params_dict[key] = value

        try:
            result = manager.apply_skill(args.name, **params_dict)
            print("\n=== Skill Output ===")
            print(result)
        except ValueError as e:
            print(f"Error: {e}")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Manage MCP context and skills for Lance Graph Agent"
    )

    parser.add_argument(
        "--context-file",
        type=Path,
        help="Path to context file (default: .lance-graph/context.jsonl)",
    )
    parser.add_argument(
        "--skills-file",
        type=Path,
        help="Path to skills file (default: .lance-graph/skills.yaml)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)
    setup_context_commands(subparsers)
    setup_skills_commands(subparsers)

    args = parser.parse_args()

    # Create manager
    manager = MCPContextManager(
        context_file=args.context_file,
        skills_file=args.skills_file,
    )

    # Dispatch command
    if args.command == "context":
        handle_context_command(args, manager)
    elif args.command == "skills":
        handle_skills_command(args, manager)


if __name__ == "__main__":
    main()
