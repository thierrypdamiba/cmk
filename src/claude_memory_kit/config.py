import os
import logging

from dotenv import load_dotenv

load_dotenv()

OPUS = "claude-opus-4-6"
SONNET = "claude-sonnet-4-5-20250929"
HAIKU = "claude-haiku-4-5-20251001"

log = logging.getLogger("cmk")


def get_model() -> str:
    model = os.getenv("ANTHROPIC_MODEL", OPUS)
    if model != OPUS:
        log.warning(
            "using %s for synthesis. "
            "i'll remember things, but like, less poetically. "
            "set ANTHROPIC_MODEL=%s if you want me at my best.",
            model,
            OPUS,
        )
    return model


def get_api_key() -> str:
    """Get API key for synthesis. Checks CMK cloud key first, then local Anthropic key."""
    # Check for CMK cloud API key (no local Anthropic key needed)
    from .cli_auth import get_api_key as get_cmk_key
    cmk_key = get_cmk_key()
    if cmk_key and cmk_key.startswith("cmk-sk-"):
        return cmk_key

    key = os.getenv("ANTHROPIC_API_KEY", "")
    if not key or key.startswith("<"):
        log.debug("no synthesis key available (set CMK cloud key or ANTHROPIC_API_KEY)")
    return key


def get_store_path() -> str:
    return os.path.expanduser(
        os.getenv("MEMORY_STORE_PATH", "~/.claude-memory")
    )


def get_database_url() -> str | None:
    """Return DATABASE_URL if set and non-placeholder, else None."""
    url = os.getenv("DATABASE_URL", "")
    if url and not url.startswith("<"):
        return url
    return None


def get_qdrant_config() -> dict:
    """Return Qdrant connection config. Cloud if URL set, local otherwise."""
    url = os.getenv("QDRANT_URL", "")
    api_key = os.getenv("QDRANT_API_KEY", "")
    jina_key = os.getenv("JINA_API_KEY", "")
    if url and not url.startswith("<"):
        return {
            "mode": "cloud",
            "url": url,
            "api_key": api_key,
            "jina_api_key": jina_key,
        }
    return {"mode": "local"}


def is_cloud_mode() -> bool:
    cfg = get_qdrant_config()
    return cfg["mode"] == "cloud"


# ---- Flow Mode ----

FLOW_CHAR_THRESHOLD = 2000  # ~500 tokens

FLOW_DEFAULT_SKIP_TOOLS = frozenset({
    "mcp__claude-memory-kit__remember_this",
    "mcp__claude-memory-kit__recall_memories",
    "mcp__claude-memory-kit__forget_memory",
    "mcp__claude-memory-kit__save_checkpoint",
    "remember_this",
    "recall_memories",
    "forget_memory",
    "save_checkpoint",
})


def is_flow_mode() -> bool:
    return os.getenv("CMK_FLOW_MODE", "").lower() in ("true", "1", "yes")


def get_flow_skip_tools() -> frozenset[str]:
    extra = os.getenv("CMK_FLOW_SKIP_TOOLS", "")
    if not extra.strip():
        return FLOW_DEFAULT_SKIP_TOOLS
    custom = frozenset(t.strip() for t in extra.split(",") if t.strip())
    return FLOW_DEFAULT_SKIP_TOOLS | custom


def get_flow_char_threshold() -> int:
    val = os.getenv("CMK_FLOW_THRESHOLD", "")
    if val.strip().isdigit():
        return int(val)
    return FLOW_CHAR_THRESHOLD
