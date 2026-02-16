"""Modify Claude Code JSONL transcript to replace tool output with compressed version."""

import json
import logging
import os
import tempfile

log = logging.getLogger("cmk.flow")

FLOW_PREFIX = "[flow compressed] "


def replace_tool_output_in_transcript(
    transcript_path: str,
    tool_use_id: str,
    compressed: str,
) -> bool:
    """Replace a tool's output in the JSONL transcript file.

    Reads the transcript, finds the entry matching tool_use_id,
    replaces its content with the compressed version, and writes
    back atomically via tempfile + os.replace.

    Returns True if the replacement was made, False otherwise.
    """
    if not transcript_path or not os.path.isfile(transcript_path):
        return False

    try:
        with open(transcript_path, "r") as f:
            lines = f.readlines()
    except (OSError, IOError) as e:
        log.debug("failed to read transcript: %s", e)
        return False

    found = False
    new_lines = []
    tagged = f"{FLOW_PREFIX}{compressed}"

    for line in lines:
        stripped = line.strip()
        if not stripped:
            new_lines.append(line)
            continue

        try:
            entry = json.loads(stripped)
        except json.JSONDecodeError:
            new_lines.append(line)
            continue

        if _replace_in_entry(entry, tool_use_id, tagged):
            found = True
            new_lines.append(json.dumps(entry) + "\n")
        else:
            new_lines.append(line)

    if not found:
        return False

    # Atomic write
    try:
        dir_name = os.path.dirname(transcript_path) or "."
        fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                f.writelines(new_lines)
            os.replace(tmp_path, transcript_path)
        except Exception:
            # Clean up temp file on failure
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
    except (OSError, IOError) as e:
        log.debug("failed to write transcript: %s", e)
        return False

    return True


def _replace_in_entry(entry: dict, tool_use_id: str, tagged: str) -> bool:
    """Try to replace tool output in various known transcript formats.

    Returns True if a replacement was made.
    """
    # Format 1: top-level tool_result with tool_use_id
    if entry.get("type") == "tool_result" and entry.get("tool_use_id") == tool_use_id:
        if isinstance(entry.get("content"), str):
            entry["content"] = tagged
            return True
        if isinstance(entry.get("content"), list):
            for block in entry["content"]:
                if isinstance(block, dict) and block.get("type") == "text":
                    block["text"] = tagged
                    return True

    # Format 2: message with content array containing tool_result blocks
    if isinstance(entry.get("content"), list):
        for block in entry["content"]:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_result" and block.get("tool_use_id") == tool_use_id:
                if isinstance(block.get("content"), str):
                    block["content"] = tagged
                    return True
                if isinstance(block.get("content"), list):
                    for sub in block["content"]:
                        if isinstance(sub, dict) and sub.get("type") == "text":
                            sub["text"] = tagged
                            return True

    # Format 3: message.content[].output (alternate transcript format)
    if isinstance(entry.get("content"), list):
        for block in entry["content"]:
            if not isinstance(block, dict):
                continue
            if block.get("id") == tool_use_id and "output" in block:
                block["output"] = tagged
                return True

    return False
