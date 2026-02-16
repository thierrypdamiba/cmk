"""Compress tool output using Haiku for flow mode."""

import logging

from ..config import HAIKU, get_api_key
from ..extract import _call_anthropic

log = logging.getLogger("cmk.flow")

COMPRESS_SYSTEM = """You are a tool output compressor for Claude Code. Your job is to reduce verbose tool output to a concise observation that preserves the essential information.

Preserve:
- File paths, line numbers, function/class names
- Error messages and stack traces (summarized)
- Numbers, counts, versions, sizes
- Key findings, status results, success/failure
- Code signatures and type information

Drop:
- Repetitive file listings (summarize count + pattern)
- Boilerplate output, headers, decorative formatting
- Redundant whitespace, blank lines
- Full file contents (summarize structure instead)
- Verbose help text or usage instructions

Write a concise observation in plain text. No markdown formatting. Start directly with the content."""

# Truncate input to avoid sending huge payloads to Haiku
MAX_INPUT_CHARS = 15000


async def compress_tool_output(
    tool_name: str,
    tool_input: str,
    tool_output: str,
) -> str | None:
    """Compress tool output into a concise observation using Haiku.

    Returns the compressed text, or None if no API key is available.
    """
    api_key = get_api_key()
    if not api_key or api_key.startswith("<"):
        return None

    truncated = tool_output[:MAX_INPUT_CHARS]
    if len(tool_output) > MAX_INPUT_CHARS:
        truncated += f"\n... ({len(tool_output) - MAX_INPUT_CHARS} chars truncated)"

    user_msg = f"Tool: {tool_name}\nInput: {tool_input[:500]}\nOutput:\n{truncated}"

    try:
        result = await _call_anthropic(
            COMPRESS_SYSTEM,
            user_msg,
            api_key,
            max_tokens=700,
            model=HAIKU,
        )
        return result.strip()
    except Exception as e:
        log.debug("compression failed: %s", e)
        return None
