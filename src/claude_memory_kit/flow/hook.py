"""PostToolUse hook entry point for Flow Mode.

Reads hook input from stdin, compresses large tool outputs,
stores observations in Qdrant, and modifies the transcript.
"""

import asyncio
import json
import logging
import sys
from datetime import datetime, timezone

from ..config import (
    get_flow_char_threshold,
    get_flow_skip_tools,
    get_store_path,
    is_flow_mode,
)
from ..types import Gate, JournalEntry

log = logging.getLogger("cmk.flow")


def run_flow_hook() -> None:
    """CLI entry point. Reads stdin JSON, runs the async pipeline."""
    if not is_flow_mode():
        return

    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return
        hook_input = json.loads(raw)
    except (json.JSONDecodeError, IOError):
        return

    try:
        result = asyncio.run(_handle_hook(hook_input))
        if result:
            print(json.dumps(result))
    except Exception:
        # Fail open: never break the user's session
        pass


async def _handle_hook(hook_input: dict) -> dict | None:
    """Orchestrate compression, storage, and transcript modification.

    Returns a dict with hookSpecificOutput for MCP tools, or None for built-in tools.
    """
    tool_name = hook_input.get("tool_name", "")
    tool_response = hook_input.get("tool_response", "")
    tool_input = hook_input.get("tool_input", "")
    tool_use_id = hook_input.get("tool_use_id", "")
    transcript_path = hook_input.get("transcript_path", "")

    # Convert tool_input to string if it's a dict
    if isinstance(tool_input, dict):
        tool_input = json.dumps(tool_input, default=str)
    if isinstance(tool_response, dict):
        tool_response = json.dumps(tool_response, default=str)

    # Skip excluded tools
    skip_tools = get_flow_skip_tools()
    if tool_name in skip_tools:
        return None

    # Skip small outputs
    threshold = get_flow_char_threshold()
    if len(tool_response) < threshold:
        return None

    # Compress
    from .compress import compress_tool_output
    compressed = await compress_tool_output(tool_name, tool_input, tool_response)
    if not compressed:
        return None

    # Store observation in Qdrant (best effort)
    await _store_observation(tool_name, compressed)

    # MCP tools (contain __) return updated output via hook protocol
    if "__" in tool_name:
        return {
            "hookSpecificOutput": {
                "updatedMCPToolOutput": f"[flow compressed] {compressed}",
            }
        }

    # Built-in tools: modify the transcript file directly
    if tool_use_id and transcript_path:
        from .transcript import replace_tool_output_in_transcript
        replace_tool_output_in_transcript(transcript_path, tool_use_id, compressed)

    return None


async def _store_observation(tool_name: str, compressed: str) -> None:
    """Store compressed observation as a journal entry in Qdrant."""
    try:
        from ..cli_auth import get_user_id
        from ..store import Store

        store = Store(get_store_path())
        store.qdrant.ensure_collection()
        user_id = get_user_id()

        entry = JournalEntry(
            timestamp=datetime.now(timezone.utc),
            gate=Gate.observation,
            content=f"[{tool_name}] {compressed}",
            person=None,
            project=None,
        )
        store.qdrant.insert_journal(entry, user_id=user_id)
    except Exception as e:
        log.debug("observation storage failed: %s", e)
