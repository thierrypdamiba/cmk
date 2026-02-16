"""API key management for CMK cloud mode."""

import hashlib
import secrets
import uuid

PREFIX = "cmk-sk-"


def generate_api_key() -> str:
    """Generate a new API key: cmk-sk-{64 hex chars}."""
    return PREFIX + secrets.token_hex(32)


def hash_key(raw_key: str) -> str:
    """SHA256 hash of the raw API key. Never store the raw key."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


def create_api_key(db, user_id: str, name: str = "") -> dict:
    """Create a new API key for a user. Returns the raw key (only time it's visible)."""
    raw = generate_api_key()
    key_id = str(uuid.uuid4())
    key_hash = hash_key(raw)
    display_prefix = raw[:12]  # "cmk-sk-xxxx" for display

    db.insert_api_key(key_id, user_id, key_hash, display_prefix, name)

    return {
        "id": key_id,
        "key": raw,
        "prefix": display_prefix,
        "name": name,
    }


def validate_api_key(raw_key: str, db) -> dict | None:
    """Validate an API key. Returns user dict or None."""
    if not db:
        return None
    if not raw_key.startswith(PREFIX):
        return None

    key_hash = hash_key(raw_key)
    row = db.get_api_key_by_hash(key_hash)
    if not row:
        return None

    user = db.get_user(row["user_id"])
    return {
        "id": row["user_id"],
        "email": user.get("email") if user else None,
        "name": user.get("name", "") if user else "",
        "plan": user.get("plan", "free") if user else "free",
    }


def list_keys(db, user_id: str) -> list[dict]:
    """List API keys for a user (masked, no raw keys)."""
    return db.list_api_keys(user_id)


def revoke_key(db, key_id: str, user_id: str) -> bool:
    """Revoke an API key."""
    return db.revoke_api_key(key_id, user_id)
