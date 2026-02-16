"""MCP server entry point. Model-friendly design: 3 tools, auto-context, auto-maintenance."""

import asyncio
import logging
import re

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from .cli_auth import get_user_id, get_team_id
from .config import get_store_path, is_flow_mode
from .store import Store
from .tools import (
    do_remember, do_recall, do_reflect,
    do_identity, do_forget, do_auto_extract, do_prime,
)
from .tools.checkpoint import do_checkpoint, CHECKPOINT_GUIDANCE, CHECKPOINT_EVERY

log = logging.getLogger("cmk")

_REFLECT_EVERY = 15


def _auto_gate(text: str) -> str:
    """Classify gate from content using keyword heuristics.

    No API call needed. Good enough for 80% of cases.
    The gate is internal architecture, not user-facing.
    """
    lower = text.lower()

    # Promissory: commitments, promises, follow-ups
    if any(kw in lower for kw in [
        "i will", "i'll", "i promised", "i need to",
        "follow up", "follow-up", "todo", "to do",
        "i should", "committed to", "agreed to",
        "deadline", "by tomorrow", "by monday",
        "remind me", "don't forget",
    ]):
        return "promissory"

    # Correction: updates or contradicts previous knowledge
    if any(kw in lower for kw in [
        "actually", "correction", "i was wrong",
        "turns out", "not true", "no longer",
        "changed my mind", "updated", "contrary to",
        "instead of", "rather than", "opposite",
    ]):
        return "correction"

    # Behavioral: changes future actions, preferences, patterns
    if any(kw in lower for kw in [
        "from now on", "always", "never",
        "prefer", "preference", "likes to",
        "wants me to", "style is", "approach is",
        "workflow", "when i", "habit",
        "don't like", "annoyed by",
    ]):
        return "behavioral"

    # Relational: about a person, their traits, relationship dynamics
    person_patterns = [
        r"\b(he|she|they)\b.*(is|are|likes|prefers|hates|works|said)",
        r"\b\w+\b\s+(is a|works at|lives in|prefers|likes|said)",
    ]
    for pat in person_patterns:
        if re.search(pat, lower):
            return "relational"

    if any(kw in lower for kw in [
        "their name", "works at", "relationship",
        "family", "partner", "friend", "colleague",
        "boss", "manager", "team lead",
    ]):
        return "relational"

    # Default: epistemic (learning, facts, knowledge)
    return "epistemic"


def _extract_person_project(text: str) -> tuple[str | None, str | None]:
    """Try to extract person and project from content. Simple heuristics."""
    person = None
    project = None

    # Person: look for names (capitalized words after relational keywords)
    name_match = re.search(
        r"\b(?:about|for|with|from)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b",
        text,
    )
    if name_match:
        candidate = name_match.group(1)
        # Skip common non-name words
        if candidate.lower() not in {
            "the", "this", "that", "monday", "tuesday", "wednesday",
            "thursday", "friday", "saturday", "sunday",
            "january", "february", "march", "april", "may", "june",
            "july", "august", "september", "october", "november", "december",
        }:
            person = candidate

    # Project: look for quoted strings or "project X" patterns
    project_match = re.search(
        r'(?:project|repo|app|codebase|working on)\s+["\']?(\S+)["\']?',
        text,
        re.IGNORECASE,
    )
    if project_match:
        project = project_match.group(1).strip("\"'.,;")

    return person, project


def _build_instructions(store: Store, user_id: str, team_id: str | None = None) -> str:
    """Build dynamic server instructions with identity card and recent context."""
    parts = [
        "You have persistent memory via Claude Memory Kit (CMK).",
        "You WILL forget everything between sessions unless you save it.",
        "",
        "4 tools: remember_this, recall_memories, forget_memory, save_checkpoint.",
        "",
        "PROACTIVE SAVING (do this automatically, user should not have to ask):",
        "- User states a preference or opinion: save it.",
        "- User corrects you or says you're wrong: save the correction.",
        "- User mentions a person, their role, or relationship: save it.",
        "- User makes a commitment or asks you to follow up: save it.",
        "- You learn something surprising or non-obvious: save it.",
        "- A decision is made about architecture, approach, or tooling: save it.",
        "- The user's name, project, or working style comes up: save it.",
        "",
        "Do NOT save: routine commands, file paths, build output, small talk.",
        "Do NOT ask permission to save. Just save. The user expects it.",
        "",
        "When context might exist from past sessions, call search first.",
        "Everything else (classification, consolidation, identity) is automatic.",
        "",
        "SESSION CONTINUITY:",
        "- Checkpoints are auto-saved every 8 memory saves.",
        "- You can also call checkpoint manually when wrapping up complex work.",
        "- Your last checkpoint is loaded above at session start.",
    ]

    # Team memory instructions
    if team_id:
        parts.append("")
        parts.append("TEAM MEMORY:")
        parts.append(f"- You are part of team: {team_id}")
        parts.append("- By default, memories are private (only you can see them).")
        parts.append("- Set visibility='team' when saving knowledge the whole team should share.")
        parts.append("- Recall automatically searches both your private and team memories.")
        parts.append("- Team memories show a [team] tag in results.")

        # Load team rules alongside personal rules
        team_rules = store.qdrant.list_rules(user_id=f"team:{team_id}")
        if team_rules:
            parts.append("")
            parts.append("--- Team rules ---")
            for r in team_rules:
                parts.append(f"- [{r['scope']}] {r['condition']} ({r['enforcement']})")

    # Load identity card if it exists
    identity = store.qdrant.get_identity(user_id=user_id)
    if identity:
        parts.append("")
        parts.append("--- Who I am ---")
        parts.append(identity.content)

    # Load latest checkpoint (where we left off last session)
    checkpoint = store.qdrant.latest_checkpoint(user_id=user_id)
    if checkpoint:
        parts.append("")
        parts.append("--- Last session checkpoint ---")
        parts.append(checkpoint["content"])

    # Load recent context (last few journal entries, excluding checkpoints and observations)
    recent = store.qdrant.recent_journal(days=2, user_id=user_id)
    if recent:
        non_checkpoint = [
            e for e in recent
            if e.get("gate") not in ("checkpoint", "observation")
        ]
        if non_checkpoint:
            parts.append("")
            parts.append("--- Recent context ---")
            for e in non_checkpoint[:8]:
                parts.append(f"[{e['gate']}] {e['content']}")

    # Flow mode: inject recent observations for session continuity
    if is_flow_mode() and recent:
        observations = [e for e in recent if e.get("gate") == "observation"]
        if observations:
            parts.append("")
            parts.append("--- Recent observations (flow mode) ---")
            for e in observations[:5]:
                parts.append(e["content"])

    return "\n".join(parts)


# Tool definitions with natural-language names and descriptions
TOOL_DEFS = [
    Tool(
        name="remember_this",
        description=(
            "Remember something about the user or their work. "
            "Call this whenever you learn a preference, commitment, "
            "correction, or fact worth keeping. "
            "You don't need permission. Just remember it."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": (
                        "What you want to remember. "
                        "Write it like you'd tell a colleague."
                    ),
                },
                "person": {
                    "type": "string",
                    "description": "Person this is about (auto-detected if omitted)",
                },
                "project": {
                    "type": "string",
                    "description": "Project context (auto-detected if omitted)",
                },
                "visibility": {
                    "type": "string",
                    "description": "Set to 'team' to share with your team. Default: private.",
                    "enum": ["private", "team"],
                },
            },
            "required": ["text"],
        },
    ),
    Tool(
        name="recall_memories",
        description=(
            "Look up what you know about a topic. "
            "Searches across all saved memories using keywords and meaning. "
            "Use this at the start of sessions and whenever past context might help."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "What you're looking for. Use natural language or keywords.",
                },
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="forget_memory",
        description=(
            "Remove a specific memory. "
            "Use when the user asks you to forget something, "
            "or when information is outdated or wrong. "
            "Requires the memory ID from search results and a reason."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "id": {
                    "type": "string",
                    "description": "The memory ID (from search results) to remove.",
                },
                "reason": {
                    "type": "string",
                    "description": "Why this memory should be removed.",
                },
            },
            "required": ["id", "reason"],
        },
    ),
    Tool(
        name="save_checkpoint",
        description=(
            "Save a snapshot of the current session. "
            "Captures what you're working on, key decisions, and next steps. "
            "Called automatically, but you can also call it when finishing complex work. "
            + CHECKPOINT_GUIDANCE
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": (
                        "Structured session summary. " + CHECKPOINT_GUIDANCE
                    ),
                },
            },
            "required": ["summary"],
        },
    ),
]

# Legacy and shorthand aliases all resolve to new names
LEGACY_ALIASES = {
    "save": "remember_this",
    "remember": "remember_this",
    "search": "recall_memories",
    "recall": "recall_memories",
    "prime": "recall_memories",
    "forget": "forget_memory",
    "checkpoint": "save_checkpoint",
}


def create_server() -> Server:
    store_path = get_store_path()
    store = Store(store_path)
    store.auth_db.migrate()
    store.qdrant.ensure_collection()
    user_id = get_user_id()
    team_id = get_team_id()

    # Counters live in the closure, not as module globals
    counters = {"save": 0, "checkpoint": 0}

    instructions = _build_instructions(store, user_id, team_id=team_id)
    server = Server("claude-memory-kit", instructions=instructions)

    @server.list_tools()
    async def list_tools():
        return TOOL_DEFS

    @server.call_tool()
    async def call_tool(name: str, arguments: dict):
        # Resolve legacy aliases
        resolved = LEGACY_ALIASES.get(name, name)
        try:
            result = await _dispatch(
                store, resolved, arguments, user_id, counters,
                team_id=team_id,
            )
        except Exception as e:
            log.error("tool %s failed: %s", name, e)
            result = f"Error: {e}"
        return [TextContent(type="text", text=result)]

    return server


async def _dispatch(
    store: Store, name: str, args: dict, user_id: str,
    counters: dict, team_id: str | None = None,
) -> str:
    if name == "remember_this":
        text = args["text"]
        gate = _auto_gate(text)
        person = args.get("person")
        project = args.get("project")
        visibility = args.get("visibility", "private")

        # Auto-detect person/project if not provided
        if not person or not project:
            auto_person, auto_project = _extract_person_project(text)
            if not person:
                person = auto_person
            if not project:
                project = auto_project

        result = await do_remember(
            store, text, gate, person, project, user_id=user_id,
            visibility=visibility, team_id=team_id,
        )

        counters["save"] += 1
        counters["checkpoint"] += 1

        # Auto-reflect after N saves
        if counters["save"] >= _REFLECT_EVERY:
            counters["save"] = 0
            try:
                reflect_result = await do_reflect(store, user_id=user_id)
                log.info("auto-reflect: %s", reflect_result)
            except Exception as e:
                log.warning("auto-reflect failed: %s", e)

        # Auto-checkpoint: prompt to save session state
        if counters["checkpoint"] >= CHECKPOINT_EVERY:
            counters["checkpoint"] = 0
            result += (
                "\n\n[auto-checkpoint] You've saved 8 memories this session. "
                "Call save_checkpoint with a structured summary of: "
                "current task, decisions made, what didn't work, and next steps."
            )

        return result

    if name == "save_checkpoint":
        return await do_checkpoint(store, args["summary"], user_id=user_id)

    if name == "recall_memories":
        return await do_recall(
            store, args["query"], user_id=user_id, team_id=team_id,
        )

    if name == "forget_memory":
        return await do_forget(
            store, args["id"], args["reason"], user_id=user_id,
            team_id=team_id,
        )

    # Legacy tool names still work through the API/CLI
    if name == "identity":
        return await do_identity(
            store, args.get("onboard_response"), user_id=user_id,
        )
    if name == "reflect":
        return await do_reflect(store, user_id=user_id)
    if name == "auto_extract":
        return await do_auto_extract(
            store, args["transcript"], user_id=user_id,
        )

    return f"Unknown tool: {name}"


async def run_server() -> None:  # pragma: no cover
    server = create_server()
    async with stdio_server() as (read_stream, write_stream):
        log.info("starting claude-memory-kit MCP server (stdio)")
        await server.run(
            read_stream, write_stream,
            server.create_initialization_options(),
        )
