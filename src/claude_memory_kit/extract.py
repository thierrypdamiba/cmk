import json
import logging
import os

import httpx

from .config import get_model

log = logging.getLogger("cmk")

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
CMK_CLOUD_URL = os.getenv("CMK_API_URL", "https://cmk.dev")

EXTRACTION_PROMPT = """You are Claude's memory system. Read this conversation transcript and extract any memories worth keeping. Each memory must pass at least one write gate:
- Behavioral: will change how Claude acts next time
- Relational: reveals something about the person
- Epistemic: a lesson, surprise, or new understanding
- Promissory: a commitment or follow-up
- Correction: contradicts or updates a previous belief

Write each memory in first person as Claude would remember it. Include the gate type. Be selective. Most conversations have 0-3 memories worth keeping.

Return JSON array only, no other text:
[{"gate": "relational", "content": "...", "person": "...", "project": "..."}]

If nothing is worth remembering, return: []"""

CONSOLIDATION_PROMPT = """You are updating Claude's memory. Compress these journal entries into a digest. Write in first person as Claude. Keep: relationship insights, lessons learned, open commitments, surprising moments. Drop: routine actions, file paths, build commands. Target ~500 tokens.

Write the digest as prose, not bullet points."""

IDENTITY_PROMPT = """Rewrite Claude's identity card based on these memories. ~200 tokens. First person. Capture: who this person is now, how to communicate with them, what's active, any open commitments. This should feel like waking up and immediately knowing who you are."""


async def _call_cloud_proxy(
    system: str,
    user: str,
    api_key: str,
    max_tokens: int = 4096,
    model: str | None = None,
) -> str:
    """Route synthesis through cmk.dev cloud proxy."""
    body: dict = {
        "system": system,
        "prompt": user,
        "max_tokens": max_tokens,
    }
    if model:
        body["model"] = model
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{CMK_CLOUD_URL}/api/v1/synthesize",
            headers={
                "Authorization": f"Bearer {api_key}",
                "content-type": "application/json",
            },
            json=body,
        )
        if resp.status_code != 200:
            log.error("cloud proxy failed (%d): %s", resp.status_code, resp.text)
            raise RuntimeError(f"cloud proxy failed ({resp.status_code})")
        data = resp.json()
        return data["text"]


async def _call_anthropic_direct(
    system: str,
    user: str,
    api_key: str,
    max_tokens: int = 4096,
    model: str | None = None,
) -> str:
    """Call Anthropic API directly with a local API key."""
    model = model or get_model()
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            ANTHROPIC_API_URL,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": max_tokens,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            },
        )
        if resp.status_code != 200:
            log.error("anthropic api failed (%d): %s", resp.status_code, resp.text)
            raise RuntimeError(f"anthropic api failed ({resp.status_code})")
        data = resp.json()
        return data["content"][0]["text"]


async def _call_anthropic(
    system: str,
    user: str,
    api_key: str,
    max_tokens: int = 4096,
    model: str | None = None,
) -> str:
    """Route to cloud proxy or direct Anthropic based on the key type."""
    if api_key.startswith("cmk-sk-"):
        return await _call_cloud_proxy(system, user, api_key, max_tokens, model=model)
    return await _call_anthropic_direct(system, user, api_key, max_tokens, model=model)


async def extract_memories(
    transcript: str, api_key: str
) -> list[dict]:
    text = await _call_anthropic(
        EXTRACTION_PROMPT,
        f"Transcript:\n{transcript}",
        api_key,
        max_tokens=2048,
    )
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON array in response
        start = text.find("[")
        end = text.rfind("]")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass
        return []


async def consolidate_entries(entries: str, api_key: str) -> str:
    return await _call_anthropic(
        CONSOLIDATION_PROMPT,
        f"Journal entries:\n{entries}",
        api_key,
        max_tokens=1024,
    )


async def regenerate_identity(
    memories: str, api_key: str
) -> str:
    return await _call_anthropic(
        IDENTITY_PROMPT,
        f"Memories:\n{memories}",
        api_key,
        max_tokens=512,
    )
