"""FastAPI server for the dashboard."""

import asyncio
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from ..auth import get_current_user, is_auth_enabled, LOCAL_USER
from ..auth_keys import create_api_key, list_keys, revoke_key
from ..config import get_store_path, is_cloud_mode, get_database_url
from ..store import Store
from ..types import IdentityCard
from ..tools import (
    do_remember, do_recall, do_reflect,
    do_identity, do_forget, do_prime, do_scan,
    classify_memories, reclassify_memory,
)

log = logging.getLogger("cmk")

GATE_PATTERN = r"^(behavioral|relational|epistemic|promissory|correction)$"
ENFORCEMENT_PATTERN = r"^(suggest|enforce|block)$"
API_VERSION = 1


@asynccontextmanager
async def lifespan(app: FastAPI):
    mode = "cloud" if is_cloud_mode() else "local"
    log.info("cmk starting in %s mode", mode)

    # Warn about partial auth config
    auth_url = os.getenv("BETTER_AUTH_URL", "")
    auth_secret = os.getenv("BETTER_AUTH_SECRET", "")
    has_url = bool(auth_url and not auth_url.startswith("<"))
    has_secret = bool(auth_secret and not auth_secret.startswith("<"))
    if has_url and not has_secret:
        log.warning(
            "BETTER_AUTH_URL is set but BETTER_AUTH_SECRET is missing. "
            "Auth will be disabled."
        )
    elif has_url and has_secret:
        log.info("betterauth enabled")
    else:
        log.info("running without auth (local mode)")

    # Initialize store in lifespan, not as a global singleton
    store = Store(get_store_path())
    # Only run SQLite migrations; Postgres schema is managed externally
    if not get_database_url():
        store.auth_db.migrate()
    store.qdrant.ensure_collection()
    app.state.store = store

    yield


app = FastAPI(title="claude-memory-kit", lifespan=lifespan)
origins = os.getenv("CORS_ORIGINS", "http://localhost:5555,http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-API-Version"] = str(API_VERSION)
    return response


def _get_store() -> Store:
    return app.state.store


async def _auth(request: Request) -> dict:
    """Resolve current user. Local mode returns local user."""
    store = _get_store()
    return await get_current_user(request, db=store.auth_db)


class CreateMemoryRequest(BaseModel):
    content: str = Field(..., max_length=100_000)
    gate: str = Field(..., pattern=GATE_PATTERN)
    person: str | None = Field(None, max_length=500)
    project: str | None = Field(None, max_length=500)


class UpdateMemoryRequest(BaseModel):
    content: str | None = Field(None, max_length=100_000)
    gate: str | None = Field(None, pattern=GATE_PATTERN)
    person: str | None = Field(None, max_length=500)
    project: str | None = Field(None, max_length=500)


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=10_000)


class CreateKeyRequest(BaseModel):
    name: str = Field("", max_length=200)


class UpdateIdentityRequest(BaseModel):
    content: str = Field(..., max_length=50_000)


class CreateRuleRequest(BaseModel):
    scope: str = Field("global", max_length=100)
    condition: str = Field(..., max_length=10_000)
    enforcement: str = Field("suggest", pattern=ENFORCEMENT_PATTERN)


class UpdateRuleRequest(BaseModel):
    scope: str | None = Field(None, max_length=100)
    condition: str | None = Field(None, max_length=10_000)
    enforcement: str | None = Field(None, pattern=ENFORCEMENT_PATTERN)


SENSITIVITY_PATTERN = r"^(safe|sensitive|critical)$"


class ReclassifyRequest(BaseModel):
    level: str = Field(..., pattern=SENSITIVITY_PATTERN)


class BulkPrivateRequest(BaseModel):
    ids: list[str] = Field(..., min_length=1, max_length=100)
    action: str = Field(..., pattern=r"^(delete|redact|reclassify)$")
    level: str | None = Field(None, pattern=SENSITIVITY_PATTERN)


class CreateTeamRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)


class AddMemberRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=500)
    role: str = Field("member", pattern=r"^(admin|member)$")


class SynthesizeRequest(BaseModel):
    system: str = Field(..., max_length=50_000)
    prompt: str = Field(..., max_length=100_000)
    max_tokens: int = Field(4096, ge=1, le=8192)
    model: str | None = Field(None, max_length=100)


ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-6")


# ---- Public (no prefix) ----

@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


# ---- API Router (mounted at /api and /api/v1) ----

router = APIRouter()


# ---- Auth ----

@router.get("/auth/me")
async def auth_me(user: dict = Depends(_auth)):
    return {"user": user}


@router.post("/keys")
async def create_key(
    req: CreateKeyRequest, user: dict = Depends(_auth)
):
    store = _get_store()
    result = create_api_key(store.auth_db, user["id"], req.name)
    return {"key": result}


@router.get("/keys")
async def get_keys(user: dict = Depends(_auth)):
    store = _get_store()
    keys = list_keys(store.auth_db, user["id"])
    return {"keys": keys}


@router.delete("/keys/{key_id}")
async def delete_key(key_id: str, user: dict = Depends(_auth)):
    store = _get_store()
    ok = revoke_key(store.auth_db, key_id, user["id"])
    if not ok:
        raise HTTPException(404, "key not found")
    return {"revoked": True}


# ---- Synthesis Proxy ----

@router.post("/synthesize")
async def synthesize(req: SynthesizeRequest, user: dict = Depends(_auth)):
    """Proxy Anthropic API calls for cloud users.

    Accepts a system prompt and user prompt, calls Anthropic using the
    server-side API key, and returns the generated text. This lets
    users run synthesis features without their own Anthropic key.
    """
    server_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not server_key or server_key.startswith("<"):
        raise HTTPException(
            503,
            "Synthesis unavailable: server ANTHROPIC_API_KEY not configured.",
        )

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                ANTHROPIC_API_URL,
                headers={
                    "x-api-key": server_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": req.model or ANTHROPIC_MODEL,
                    "max_tokens": req.max_tokens,
                    "system": req.system,
                    "messages": [{"role": "user", "content": req.prompt}],
                },
            )
    except httpx.HTTPError as e:
        log.error("anthropic proxy request failed: %s", e)
        raise HTTPException(502, f"Upstream request failed: {e}")

    if resp.status_code != 200:
        log.error(
            "anthropic api returned %d: %s", resp.status_code, resp.text[:500]
        )
        raise HTTPException(502, f"Upstream returned {resp.status_code}")

    data = resp.json()
    text = data["content"][0]["text"]
    return {"text": text}


# ---- Memories ----

@router.get("/memories")
async def list_memories(
    limit: int = 50, offset: int = 0,
    gate: str | None = None,
    person: str | None = None,
    project: str | None = None,
    user: dict = Depends(_auth),
):
    limit = min(max(1, limit), 500)
    offset = max(0, offset)
    store = _get_store()
    memories = store.qdrant.list_memories(
        limit, offset, user_id=user["id"],
        gate=gate, person=person, project=project,
    )
    return {"memories": [m.model_dump() for m in memories]}


@router.post("/memories")
async def create_memory(
    req: CreateMemoryRequest, user: dict = Depends(_auth)
):
    store = _get_store()
    result = await do_remember(
        store, req.content, req.gate, req.person, req.project,
        user_id=user["id"],
    )
    return {"result": result}


@router.get("/memories/{id}")
async def get_memory(id: str, user: dict = Depends(_auth)):
    store = _get_store()
    mem = store.qdrant.get_memory(id, user_id=user["id"])
    if not mem:
        raise HTTPException(404, "memory not found")
    return mem.model_dump()


@router.patch("/memories/{id}")
async def update_memory(
    id: str, req: UpdateMemoryRequest, user: dict = Depends(_auth)
):
    store = _get_store()
    mem = store.qdrant.get_memory(id, user_id=user["id"])
    if not mem:
        raise HTTPException(404, "memory not found")

    updates = req.model_dump(exclude_none=True)
    if not updates:
        return {"result": "no changes"}

    store.qdrant.update_memory(id, user_id=user["id"], **updates)
    return {"result": "updated"}


@router.delete("/memories/{id}")
async def delete_memory(
    id: str, reason: str = "", user: dict = Depends(_auth)
):
    store = _get_store()
    result = await do_forget(
        store, id, reason or "deleted via API", user_id=user["id"]
    )
    return {"result": result}


# ---- Pin ----

@router.post("/memories/{id}/pin")
async def pin_memory(id: str, user: dict = Depends(_auth)):
    store = _get_store()
    mem = store.qdrant.get_memory(id, user_id=user["id"])
    if not mem:
        raise HTTPException(404, "memory not found")
    store.qdrant.set_pinned(id, True, user_id=user["id"])
    return {"result": "pinned"}


@router.delete("/memories/{id}/pin")
async def unpin_memory(id: str, user: dict = Depends(_auth)):
    store = _get_store()
    mem = store.qdrant.get_memory(id, user_id=user["id"])
    if not mem:
        raise HTTPException(404, "memory not found")
    store.qdrant.set_pinned(id, False, user_id=user["id"])
    return {"result": "unpinned"}


# ---- Search ----

@router.post("/search")
async def search(
    req: SearchRequest, user: dict = Depends(_auth)
):
    store = _get_store()
    result = await do_recall(store, req.query, user_id=user["id"])
    return {"result": result}


# ---- Identity ----

@router.get("/identity")
async def get_identity(user: dict = Depends(_auth)):
    store = _get_store()
    result = await do_identity(store, user_id=user["id"])
    return {"identity": result}


@router.put("/identity")
async def update_identity(
    req: UpdateIdentityRequest, user: dict = Depends(_auth)
):
    store = _get_store()
    card = IdentityCard(
        person=None,
        project=None,
        content=req.content,
        last_updated=datetime.now(timezone.utc),
    )
    store.qdrant.set_identity(card, user_id=user["id"])
    return {"result": "updated"}


@router.get("/graph/{id}")
async def get_graph(id: str, user: dict = Depends(_auth)):
    store = _get_store()
    related = store.qdrant.find_related(
        id, depth=2, user_id=user["id"]
    )
    return {"related": related}


@router.post("/reflect")
async def trigger_reflect(user: dict = Depends(_auth)):
    store = _get_store()
    result = await do_reflect(store, user_id=user["id"])
    return {"result": result}


@router.get("/scan")
async def scan_memories(user: dict = Depends(_auth)):
    """Scan memories for PII and sensitive data patterns."""
    store = _get_store()
    result = await do_scan(store, user_id=user["id"])
    return {"result": result}


# ---- Privacy / Sensitivity ----

@router.get("/private")
async def list_private(
    level: str = "flagged",
    limit: int = 50, offset: int = 0,
    user: dict = Depends(_auth),
):
    """List memories filtered by sensitivity level."""
    limit = min(max(1, limit), 500)
    offset = max(0, offset)
    store = _get_store()
    memories = store.qdrant.list_memories_by_sensitivity(
        level if level != "flagged" else "flagged",
        limit, offset, user_id=user["id"],
    )
    return {"memories": [m.model_dump() for m in memories]}


@router.get("/privacy-stats")
async def privacy_stats(user: dict = Depends(_auth)):
    """Get sensitivity classification counts."""
    store = _get_store()
    counts = store.qdrant.count_by_sensitivity(user_id=user["id"])
    total = store.qdrant.count_memories(user_id=user["id"])
    return {
        "total": total,
        "safe": counts.get("safe", 0),
        "sensitive": counts.get("sensitive", 0),
        "critical": counts.get("critical", 0),
        "unclassified": counts.get("unclassified", 0),
    }


@router.post("/classify")
async def trigger_classify(user: dict = Depends(_auth)):
    """Batch-classify all unclassified memories."""
    store = _get_store()
    result = await classify_memories(store, user_id=user["id"])
    return {"result": result}


@router.patch("/memories/{id}/sensitivity")
async def update_sensitivity(
    id: str, req: ReclassifyRequest, user: dict = Depends(_auth)
):
    """Manually reclassify a memory's sensitivity."""
    store = _get_store()
    result = await reclassify_memory(store, id, req.level, user_id=user["id"])
    return {"result": result}


@router.post("/private/bulk")
async def bulk_private_action(
    req: BulkPrivateRequest, user: dict = Depends(_auth)
):
    """Bulk actions on private memories: delete, redact, or reclassify."""
    store = _get_store()
    uid = user["id"]
    processed = 0

    for mem_id in req.ids:
        mem = store.qdrant.get_memory(mem_id, user_id=uid)
        if not mem:
            continue

        if req.action == "delete":
            await do_forget(store, mem_id, "bulk privacy action", user_id=uid)
            processed += 1

        elif req.action == "redact":
            store.qdrant.update_memory(mem_id, user_id=uid, content="[REDACTED]")
            store.qdrant.update_sensitivity(
                mem_id, "safe", "content redacted by user", user_id=uid,
            )
            processed += 1

        elif req.action == "reclassify" and req.level:
            store.qdrant.update_sensitivity(
                mem_id, req.level, "bulk reclassified by user", user_id=uid,
            )
            processed += 1

    return {"result": f"{req.action}: {processed}/{len(req.ids)} memories processed"}


@router.get("/stats")
async def get_stats(user: dict = Depends(_auth)):
    store = _get_store()
    uid = user["id"]
    return {
        "total": store.qdrant.count_memories(user_id=uid),
        "by_gate": store.qdrant.count_by_gate(user_id=uid),
        "has_identity": store.qdrant.get_identity(user_id=uid) is not None,
    }


# ---- Rules ----

@router.get("/rules")
async def list_rules(user: dict = Depends(_auth)):
    store = _get_store()
    rules = store.qdrant.list_rules(user_id=user["id"])
    return {"rules": rules}


@router.post("/rules")
async def create_rule(
    req: CreateRuleRequest, user: dict = Depends(_auth)
):
    store = _get_store()
    rule_id = str(uuid.uuid4())[:12]
    store.qdrant.insert_rule(
        rule_id, user["id"], req.scope,
        req.condition, req.enforcement,
    )
    rule = store.qdrant.get_rule(rule_id, user_id=user["id"])
    return {"rule": rule}


@router.put("/rules/{rule_id}")
async def update_rule(
    rule_id: str, req: UpdateRuleRequest, user: dict = Depends(_auth)
):
    store = _get_store()
    existing = store.qdrant.get_rule(rule_id, user_id=user["id"])
    if not existing:
        raise HTTPException(404, "rule not found")

    updates = req.model_dump(exclude_none=True)
    if not updates:
        return {"result": "no changes"}

    store.qdrant.update_rule(rule_id, user_id=user["id"], **updates)
    return {"result": "updated"}


@router.delete("/rules/{rule_id}")
async def delete_rule(rule_id: str, user: dict = Depends(_auth)):
    store = _get_store()
    ok = store.qdrant.delete_rule(rule_id, user_id=user["id"])
    if not ok:
        raise HTTPException(404, "rule not found")
    return {"result": "deleted"}


# ---- Teams ----

def _require_team_member(store: Store, team_id: str, user_id: str) -> None:
    if not store.auth_db.is_team_member(team_id, user_id):
        raise HTTPException(403, "not a member of this team")


def _require_team_role(store: Store, team_id: str, user_id: str, roles: set) -> str:
    role = store.auth_db.get_member_role(team_id, user_id)
    if role not in roles:
        raise HTTPException(403, f"requires one of: {', '.join(roles)}")
    return role


@router.post("/teams")
async def create_team(req: CreateTeamRequest, user: dict = Depends(_auth)):
    store = _get_store()
    uid = user["id"]
    team_id = f"team_{uuid.uuid4().hex[:8]}"
    team = store.auth_db.create_team(team_id, req.name, uid)
    return {"team": team}


@router.get("/teams")
async def list_teams(user: dict = Depends(_auth)):
    store = _get_store()
    teams = store.auth_db.list_user_teams(user["id"])
    return {"teams": teams}


@router.get("/teams/{team_id}")
async def get_team(team_id: str, user: dict = Depends(_auth)):
    store = _get_store()
    _require_team_member(store, team_id, user["id"])
    team = store.auth_db.get_team(team_id)
    if not team:
        raise HTTPException(404, "team not found")
    members = store.auth_db.list_team_members(team_id)
    team["members"] = members
    return {"team": team}


@router.delete("/teams/{team_id}")
async def delete_team(team_id: str, user: dict = Depends(_auth)):
    store = _get_store()
    _require_team_role(store, team_id, user["id"], {"owner"})
    ok = store.auth_db.delete_team(team_id)
    if not ok:
        raise HTTPException(404, "team not found")
    return {"result": "deleted"}


@router.post("/teams/{team_id}/members")
async def add_member(
    team_id: str, req: AddMemberRequest, user: dict = Depends(_auth)
):
    store = _get_store()
    _require_team_role(store, team_id, user["id"], {"owner", "admin"})
    store.auth_db.add_team_member(team_id, req.user_id, req.role)
    return {"member": {"team_id": team_id, "user_id": req.user_id, "role": req.role}}


@router.delete("/teams/{team_id}/members/{member_id}")
async def remove_member(
    team_id: str, member_id: str, user: dict = Depends(_auth)
):
    store = _get_store()
    uid = user["id"]
    # Can remove yourself, or admin+ can remove others
    if member_id != uid:
        _require_team_role(store, team_id, uid, {"owner", "admin"})
    ok = store.auth_db.remove_team_member(team_id, member_id)
    if not ok:
        raise HTTPException(404, "member not found")
    return {"result": "removed"}


@router.get("/teams/{team_id}/memories")
async def list_team_memories(
    team_id: str,
    limit: int = 50, offset: int = 0,
    user: dict = Depends(_auth),
):
    limit = min(max(1, limit), 500)
    offset = max(0, offset)
    store = _get_store()
    _require_team_member(store, team_id, user["id"])
    memories = store.qdrant.list_memories(
        limit, offset, user_id=f"team:{team_id}",
        visibility="team",
    )
    return {"memories": [m.model_dump() for m in memories]}


@router.post("/teams/{team_id}/rules")
async def create_team_rule(
    team_id: str, req: CreateRuleRequest, user: dict = Depends(_auth)
):
    store = _get_store()
    _require_team_role(store, team_id, user["id"], {"owner", "admin"})
    rule_id = str(uuid.uuid4())[:12]
    store.qdrant.insert_rule(
        rule_id, f"team:{team_id}", req.scope,
        req.condition, req.enforcement,
    )
    rule = store.qdrant.get_rule(rule_id, user_id=f"team:{team_id}")
    return {"rule": rule}


@router.get("/teams/{team_id}/rules")
async def list_team_rules(
    team_id: str, user: dict = Depends(_auth)
):
    store = _get_store()
    _require_team_member(store, team_id, user["id"])
    rules = store.qdrant.list_rules(user_id=f"team:{team_id}")
    return {"rules": rules}


# ---- Mode ----

@router.get("/mode")
async def get_mode():
    cloud = is_cloud_mode()
    return {
        "mode": "cloud" if cloud else "local",
        "vector_store": "qdrant" if cloud else "local",
    }


# ---- Setup ----

@router.post("/setup/init-key")
async def setup_init_key(user: dict = Depends(_auth)):
    """Generate an API key and return the cmk init command."""
    store = _get_store()
    uid = user["id"]

    if uid == "local":
        raise HTTPException(400, "must be authenticated")

    result = create_api_key(store.auth_db, uid, "cmk-init")
    raw_key = result["key"]
    return {
        "key": raw_key,
        "user_id": uid,
        "command": f"cmk init {raw_key}",
        "mcp_config": {
            "memory": {
                "command": "cmk",
                "env": {"CMK_USER_ID": uid},
            },
        },
    }


# ---- Data Migration ----

@router.get("/local-data-check")
async def local_data_check(user: dict = Depends(_auth)):
    """Check if unclaimed local data exists."""
    store = _get_store()
    counts = store.count_user_data("local")
    total = counts.get("total", 0)
    return {
        "has_local_data": total > 0,
        "counts": counts,
    }


@router.post("/claim-local")
async def claim_local(user: dict = Depends(_auth)):
    """Claim local data for the authenticated user."""
    store = _get_store()
    uid = user["id"]

    if uid == "local":
        raise HTTPException(400, "cannot claim data as local user")

    counts = store.count_user_data("local")
    if counts.get("total", 0) == 0:
        return {"migrated": {}, "message": "no local data to claim"}

    result = store.migrate_user_data("local", uid)
    return {"migrated": result, "message": "local data claimed"}


# Mount router at /api (backward compat) and /api/v1
app.include_router(router, prefix="/api")
app.include_router(router, prefix="/api/v1")
