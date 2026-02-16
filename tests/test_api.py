"""Tests for the FastAPI app at /api endpoints."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from claude_memory_kit.api.app import app, _auth, _get_store
from claude_memory_kit.auth import LOCAL_USER
from claude_memory_kit.types import (
    Memory, Gate, DecayClass, IdentityCard,
)
import claude_memory_kit.api.app as app_module

# Override auth dependency to skip real auth
app.dependency_overrides[_auth] = lambda: LOCAL_USER


@pytest.fixture
def client():
    return TestClient(app)


def _make_memory(
    id="mem_test_001",
    gate=Gate.epistemic,
    content="test memory content",
    person=None,
    project=None,
):
    now = datetime.now(timezone.utc)
    return Memory(
        id=id,
        created=now,
        gate=gate,
        person=person,
        project=project,
        confidence=0.9,
        last_accessed=now,
        access_count=1,
        decay_class=DecayClass.from_gate(gate),
        content=content,
    )


@pytest.fixture(autouse=True)
def setup_store(qdrant_db, db, monkeypatch):
    store = MagicMock()
    store.qdrant = qdrant_db
    store.auth_db = db
    store.count_user_data.return_value = {"total": 0, "memories": 0}
    store.migrate_user_data.return_value = {"memories": 0}
    app.state.store = store
    return store


# ---- Health ----

def test_healthz(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_api_version_header(client):
    """All responses include X-API-Version header."""
    resp = client.get("/healthz")
    assert resp.headers["X-API-Version"] == "1"


def test_v1_routes_work(client):
    """Routes at /api/v1 mirror /api routes."""
    resp = client.get("/api/v1/stats")
    assert resp.status_code == 200
    assert "total" in resp.json()


# ---- Auth ----

def test_auth_me(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["user"]["id"] == "local"


# ---- API Keys ----

def test_create_key(client, setup_store):
    resp = client.post("/api/keys", json={"name": "test-key"})
    assert resp.status_code == 200
    key_data = resp.json()["key"]
    assert "id" in key_data
    assert key_data["key"].startswith("cmk-sk-")


def test_list_keys(client, setup_store):
    # Create a key first
    client.post("/api/keys", json={"name": "k1"})
    resp = client.get("/api/keys")
    assert resp.status_code == 200
    assert "keys" in resp.json()


def test_delete_key(client, setup_store):
    # Create then delete
    create_resp = client.post("/api/keys", json={"name": "to-delete"})
    key_id = create_resp.json()["key"]["id"]
    resp = client.delete(f"/api/keys/{key_id}")
    assert resp.status_code == 200
    assert resp.json()["revoked"] is True


def test_delete_key_not_found(client, setup_store):
    resp = client.delete("/api/keys/nonexistent-key-id")
    assert resp.status_code == 404


# ---- Memories ----

def test_list_memories_empty(client):
    resp = client.get("/api/memories")
    assert resp.status_code == 200
    assert resp.json()["memories"] == []


def test_create_memory(client, setup_store):
    with patch("claude_memory_kit.api.app.do_remember", new_callable=AsyncMock) as mock_rem:
        mock_rem.return_value = "remembered"
        resp = client.post("/api/memories", json={
            "content": "I like coffee",
            "gate": "behavioral",
        })
        assert resp.status_code == 200
        assert resp.json()["result"] == "remembered"
        mock_rem.assert_called_once()


def test_create_memory_bad_gate(client):
    resp = client.post("/api/memories", json={
        "content": "test",
        "gate": "invalid_gate",
    })
    assert resp.status_code == 422


def test_create_memory_missing_content(client):
    resp = client.post("/api/memories", json={
        "gate": "behavioral",
    })
    assert resp.status_code == 422


def test_get_memory(client, qdrant_db):
    mem = _make_memory(id="mem_get_001")
    qdrant_db.insert_memory(mem)
    resp = client.get("/api/memories/mem_get_001")
    assert resp.status_code == 200
    assert resp.json()["id"] == "mem_get_001"


def test_get_memory_not_found(client):
    resp = client.get("/api/memories/nonexistent")
    assert resp.status_code == 404


def test_update_memory(client, qdrant_db, setup_store):
    mem = _make_memory(id="mem_upd_001")
    qdrant_db.insert_memory(mem)
    resp = client.patch("/api/memories/mem_upd_001", json={
        "content": "updated content",
    })
    assert resp.status_code == 200
    assert resp.json()["result"] == "updated"


def test_update_memory_no_changes(client, qdrant_db):
    mem = _make_memory(id="mem_upd_002")
    qdrant_db.insert_memory(mem)
    resp = client.patch("/api/memories/mem_upd_002", json={})
    assert resp.status_code == 200
    assert resp.json()["result"] == "no changes"


def test_update_memory_not_found(client):
    resp = client.patch("/api/memories/nonexistent", json={
        "content": "nope",
    })
    assert resp.status_code == 404


def test_delete_memory(client, qdrant_db, setup_store):
    mem = _make_memory(id="mem_del_001")
    qdrant_db.insert_memory(mem)
    with patch("claude_memory_kit.api.app.do_forget", new_callable=AsyncMock) as mock_forget:
        mock_forget.return_value = "forgotten"
        resp = client.delete("/api/memories/mem_del_001")
        assert resp.status_code == 200
        assert resp.json()["result"] == "forgotten"


def test_list_memories_with_filters(client, qdrant_db):
    qdrant_db.insert_memory(_make_memory(id="m1", gate=Gate.behavioral, person="Alice"))
    qdrant_db.insert_memory(_make_memory(id="m2", gate=Gate.epistemic, person="Bob"))
    resp = client.get("/api/memories?gate=behavioral")
    assert resp.status_code == 200
    mems = resp.json()["memories"]
    assert all(m["gate"] == "behavioral" for m in mems)


# ---- Pin ----

def test_pin_memory(client, qdrant_db):
    mem = _make_memory(id="mem_pin_001")
    qdrant_db.insert_memory(mem)
    resp = client.post("/api/memories/mem_pin_001/pin")
    assert resp.status_code == 200
    assert resp.json()["result"] == "pinned"


def test_unpin_memory(client, qdrant_db):
    mem = _make_memory(id="mem_unpin_001")
    qdrant_db.insert_memory(mem)
    qdrant_db.set_pinned("mem_unpin_001", True)
    resp = client.delete("/api/memories/mem_unpin_001/pin")
    assert resp.status_code == 200
    assert resp.json()["result"] == "unpinned"


def test_pin_memory_not_found(client):
    resp = client.post("/api/memories/nonexistent/pin")
    assert resp.status_code == 404


def test_unpin_memory_not_found(client):
    resp = client.delete("/api/memories/nonexistent/pin")
    assert resp.status_code == 404


# ---- Search ----

def test_search(client, setup_store):
    with patch("claude_memory_kit.api.app.do_recall", new_callable=AsyncMock) as mock_recall:
        mock_recall.return_value = "found 0 results"
        resp = client.post("/api/search", json={"query": "coffee"})
        assert resp.status_code == 200
        assert "result" in resp.json()


def test_search_empty_query(client):
    resp = client.post("/api/search", json={"query": ""})
    assert resp.status_code == 422


# ---- Identity ----

def test_get_identity(client, setup_store):
    with patch("claude_memory_kit.api.app.do_identity", new_callable=AsyncMock) as mock_id:
        mock_id.return_value = "identity card content"
        resp = client.get("/api/identity")
        assert resp.status_code == 200
        assert resp.json()["identity"] == "identity card content"


def test_put_identity(client, qdrant_db):
    resp = client.put("/api/identity", json={"content": "I am a developer"})
    assert resp.status_code == 200
    assert resp.json()["result"] == "updated"
    # Verify the identity was saved
    card = qdrant_db.get_identity(user_id="local")
    assert card is not None
    assert card.content == "I am a developer"


# ---- Graph ----

def test_get_graph(client, qdrant_db):
    resp = client.get("/api/graph/some-id")
    assert resp.status_code == 200
    assert "related" in resp.json()


# ---- Reflect ----

def test_trigger_reflect(client, setup_store):
    with patch("claude_memory_kit.api.app.do_reflect", new_callable=AsyncMock) as mock_ref:
        mock_ref.return_value = "reflection complete"
        resp = client.post("/api/reflect")
        assert resp.status_code == 200
        assert resp.json()["result"] == "reflection complete"


# ---- Scan ----

def test_scan_memories(client, setup_store):
    with patch("claude_memory_kit.api.app.do_scan", new_callable=AsyncMock) as mock_scan:
        mock_scan.return_value = "Scanned 0 memories. No sensitive data patterns found."
        resp = client.get("/api/scan")
        assert resp.status_code == 200
        assert "result" in resp.json()


# ---- Privacy / Sensitivity ----

def test_list_private(client, qdrant_db):
    resp = client.get("/api/private")
    assert resp.status_code == 200
    assert "memories" in resp.json()


def test_list_private_with_level(client, qdrant_db):
    mem = _make_memory(id="priv_001", content="salary info")
    qdrant_db.insert_memory(mem)
    qdrant_db.update_sensitivity("priv_001", "sensitive", "salary info")
    resp = client.get("/api/private?level=sensitive")
    assert resp.status_code == 200


def test_privacy_stats(client, qdrant_db):
    resp = client.get("/api/privacy-stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "safe" in data
    assert "sensitive" in data
    assert "critical" in data
    assert "unclassified" in data


def test_trigger_classify(client, setup_store):
    with patch("claude_memory_kit.api.app.classify_memories", new_callable=AsyncMock) as mock_cls:
        mock_cls.return_value = "Classified 0 memories"
        resp = client.post("/api/classify")
        assert resp.status_code == 200
        assert "result" in resp.json()


def test_update_sensitivity(client, qdrant_db, setup_store):
    mem = _make_memory(id="sens_001")
    qdrant_db.insert_memory(mem)
    with patch("claude_memory_kit.api.app.reclassify_memory", new_callable=AsyncMock) as mock_rcl:
        mock_rcl.return_value = "Reclassified sens_001 as critical."
        resp = client.patch("/api/memories/sens_001/sensitivity", json={
            "level": "critical",
        })
        assert resp.status_code == 200


def test_update_sensitivity_bad_level(client):
    resp = client.patch("/api/memories/some-id/sensitivity", json={
        "level": "bogus",
    })
    assert resp.status_code == 422


def test_bulk_private_delete(client, qdrant_db, setup_store):
    mem = _make_memory(id="bulk_001")
    qdrant_db.insert_memory(mem)
    with patch("claude_memory_kit.api.app.do_forget", new_callable=AsyncMock) as mock_forget:
        mock_forget.return_value = "forgotten"
        resp = client.post("/api/private/bulk", json={
            "ids": ["bulk_001"],
            "action": "delete",
        })
        assert resp.status_code == 200
        assert "1/1" in resp.json()["result"]


def test_bulk_private_redact(client, qdrant_db, setup_store):
    mem = _make_memory(id="bulk_002")
    qdrant_db.insert_memory(mem)
    resp = client.post("/api/private/bulk", json={
        "ids": ["bulk_002"],
        "action": "redact",
    })
    assert resp.status_code == 200
    assert "1/1" in resp.json()["result"]
    # Verify content was redacted in Qdrant
    updated = qdrant_db.get_memory("bulk_002")
    assert updated.content == "[REDACTED]"


def test_bulk_private_reclassify(client, qdrant_db, setup_store):
    mem = _make_memory(id="bulk_003")
    qdrant_db.insert_memory(mem)
    resp = client.post("/api/private/bulk", json={
        "ids": ["bulk_003"],
        "action": "reclassify",
        "level": "safe",
    })
    assert resp.status_code == 200
    assert "1/1" in resp.json()["result"]


def test_bulk_private_invalid_action(client):
    resp = client.post("/api/private/bulk", json={
        "ids": ["x"],
        "action": "nuke",
    })
    assert resp.status_code == 422


def test_bulk_private_nonexistent_ids(client, qdrant_db):
    resp = client.post("/api/private/bulk", json={
        "ids": ["ghost_001"],
        "action": "delete",
    })
    assert resp.status_code == 200
    assert "0/1" in resp.json()["result"]


# ---- Stats ----

def test_get_stats(client, qdrant_db):
    resp = client.get("/api/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "by_gate" in data
    assert "has_identity" in data


def test_get_stats_with_data(client, qdrant_db):
    qdrant_db.insert_memory(_make_memory(id="stat_001", gate=Gate.behavioral))
    qdrant_db.insert_memory(_make_memory(id="stat_002", gate=Gate.epistemic))
    resp = client.get("/api/stats")
    data = resp.json()
    assert data["total"] == 2
    assert "behavioral" in data["by_gate"]


# ---- Rules ----

def test_list_rules_empty(client, qdrant_db):
    resp = client.get("/api/rules")
    assert resp.status_code == 200
    assert resp.json()["rules"] == []


def test_create_rule(client, qdrant_db):
    resp = client.post("/api/rules", json={
        "condition": "always greet the user",
        "enforcement": "suggest",
    })
    assert resp.status_code == 200
    assert resp.json()["rule"] is not None


def test_create_rule_bad_enforcement(client):
    resp = client.post("/api/rules", json={
        "condition": "test",
        "enforcement": "obliterate",
    })
    assert resp.status_code == 422


def test_update_rule(client, qdrant_db):
    # Create first
    create_resp = client.post("/api/rules", json={
        "condition": "original condition",
        "enforcement": "suggest",
    })
    rule = create_resp.json()["rule"]
    rule_id = rule["id"]

    resp = client.put(f"/api/rules/{rule_id}", json={
        "condition": "updated condition",
    })
    assert resp.status_code == 200
    assert resp.json()["result"] == "updated"


def test_update_rule_no_changes(client, qdrant_db):
    create_resp = client.post("/api/rules", json={
        "condition": "test condition",
    })
    rule_id = create_resp.json()["rule"]["id"]
    resp = client.put(f"/api/rules/{rule_id}", json={})
    assert resp.status_code == 200
    assert resp.json()["result"] == "no changes"


def test_update_rule_not_found(client):
    resp = client.put("/api/rules/nonexistent", json={
        "condition": "nope",
    })
    assert resp.status_code == 404


def test_delete_rule(client, qdrant_db):
    create_resp = client.post("/api/rules", json={
        "condition": "to be deleted",
    })
    rule_id = create_resp.json()["rule"]["id"]
    resp = client.delete(f"/api/rules/{rule_id}")
    assert resp.status_code == 200
    assert resp.json()["result"] == "deleted"


def test_delete_rule_not_found(client):
    resp = client.delete("/api/rules/nonexistent")
    assert resp.status_code == 404


# ---- Mode ----

def test_get_mode(client, monkeypatch):
    monkeypatch.setenv("QDRANT_URL", "")
    resp = client.get("/api/mode")
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "local"
    assert data["vector_store"] == "local"


# ---- Setup ----

def test_setup_init_key_local_user(client):
    """Local user should get 400 from init-key."""
    resp = client.post("/api/setup/init-key")
    assert resp.status_code == 400
    assert "authenticated" in resp.json()["detail"].lower()


def test_setup_init_key_authenticated_user(client, setup_store):
    """Authenticated (non-local) user should get a key."""
    app.dependency_overrides[_auth] = lambda: {
        "id": "user_abc123", "email": "test@example.com",
        "name": "Test", "plan": "free",
    }
    try:
        resp = client.post("/api/setup/init-key")
        assert resp.status_code == 200
        data = resp.json()
        assert data["key"].startswith("cmk-sk-")
        assert data["user_id"] == "user_abc123"
        assert "cmk init" in data["command"]
    finally:
        app.dependency_overrides[_auth] = lambda: LOCAL_USER


# ---- Data Migration ----

def test_local_data_check(client, setup_store):
    resp = client.get("/api/local-data-check")
    assert resp.status_code == 200
    data = resp.json()
    assert "has_local_data" in data
    assert "counts" in data


def test_claim_local_as_local_user(client, setup_store):
    """Local user cannot claim data."""
    resp = client.post("/api/claim-local")
    assert resp.status_code == 400


def test_claim_local_as_authenticated_user(client, setup_store):
    """Authenticated user can claim local data."""
    app.dependency_overrides[_auth] = lambda: {
        "id": "user_claim_001", "email": "claimer@example.com",
        "name": "Claimer", "plan": "free",
    }
    setup_store.count_user_data.return_value = {"total": 0}
    try:
        resp = client.post("/api/claim-local")
        assert resp.status_code == 200
        assert "no local data" in resp.json()["message"]
    finally:
        app.dependency_overrides[_auth] = lambda: LOCAL_USER


def test_claim_local_with_data(client, setup_store):
    """Authenticated user claims existing local data."""
    app.dependency_overrides[_auth] = lambda: {
        "id": "user_claim_002", "email": "c2@example.com",
        "name": "C2", "plan": "free",
    }
    setup_store.count_user_data.return_value = {"total": 5, "memories": 5}
    setup_store.migrate_user_data.return_value = {"memories": 5}
    try:
        resp = client.post("/api/claim-local")
        assert resp.status_code == 200
        assert "claimed" in resp.json()["message"]
        assert resp.json()["migrated"]["memories"] == 5
    finally:
        app.dependency_overrides[_auth] = lambda: LOCAL_USER


# ---- Security Headers ----

def test_security_headers(client):
    resp = client.get("/healthz")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"


# ---- Lifespan ----

def test_lifespan_runs(monkeypatch):
    """Lifespan context manager runs without error."""
    monkeypatch.setenv("CLERK_SECRET_KEY", "")
    from claude_memory_kit.api.app import lifespan
    import asyncio

    mock_store = MagicMock()
    with patch("claude_memory_kit.api.app.Store", return_value=mock_store), \
         patch("claude_memory_kit.api.app.get_store_path", return_value="/tmp/test"):
        async def _run():
            async with lifespan(app):
                assert app.state.store is mock_store

        asyncio.run(_run())


def test_lifespan_auth_warning(monkeypatch):
    """Lifespan warns when CLERK_SECRET_KEY is set but no frontend."""
    monkeypatch.setenv("CLERK_SECRET_KEY", "sk_test_real_key")
    monkeypatch.setenv("CLERK_FRONTEND_API", "")
    monkeypatch.setenv("CLERK_INSTANCE_ID", "")
    from claude_memory_kit.api.app import lifespan
    import asyncio

    mock_store = MagicMock()
    with patch("claude_memory_kit.api.app.Store", return_value=mock_store), \
         patch("claude_memory_kit.api.app.get_store_path", return_value="/tmp/test"):
        async def _run():
            async with lifespan(app):
                pass

        asyncio.run(_run())


def test_lifespan_auth_enabled(monkeypatch):
    """Lifespan logs auth enabled when both keys are set."""
    monkeypatch.setenv("CLERK_SECRET_KEY", "sk_test_real_key")
    monkeypatch.setenv("CLERK_FRONTEND_API", "https://clerk.example.com")
    from claude_memory_kit.api.app import lifespan
    import asyncio

    mock_store = MagicMock()
    with patch("claude_memory_kit.api.app.Store", return_value=mock_store), \
         patch("claude_memory_kit.api.app.get_store_path", return_value="/tmp/test"):
        async def _run():
            async with lifespan(app):
                pass

        asyncio.run(_run())


# ---- _get_store reads from app.state ----

def test_get_store_returns_app_state():
    """_get_store returns the store from app.state."""
    mock_store = MagicMock()
    app.state.store = mock_store
    result = _get_store()
    assert result is mock_store


# ---- _auth dependency ----

@pytest.mark.asyncio
async def test_auth_dependency_calls_get_current_user(monkeypatch, db):
    """_auth resolves user via get_current_user."""
    mock_store = MagicMock()
    mock_store.auth_db = db
    app.state.store = mock_store

    from claude_memory_kit.api.app import _auth as real_auth
    mock_request = MagicMock()
    with patch("claude_memory_kit.api.app.get_current_user", new_callable=AsyncMock, return_value=LOCAL_USER):
        result = await real_auth(mock_request)
    assert result == LOCAL_USER


# ---- Redact verifies content change ----

def test_bulk_private_redact_verifies_content(client, qdrant_db, setup_store):
    """Redact updates memory content to [REDACTED] in Qdrant."""
    mem = _make_memory(id="bulk_redact_verify")
    qdrant_db.insert_memory(mem)
    resp = client.post("/api/private/bulk", json={
        "ids": ["bulk_redact_verify"],
        "action": "redact",
    })
    assert resp.status_code == 200
    assert "1/1" in resp.json()["result"]
    # Memory content should be redacted in Qdrant
    updated = qdrant_db.get_memory("bulk_redact_verify")
    assert updated.content == "[REDACTED]"


# ---- Synthesize Proxy ----

def test_synthesize_no_server_key(client, monkeypatch):
    """Synthesize returns 503 when server has no ANTHROPIC_API_KEY."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    resp = client.post("/api/synthesize", json={
        "system": "You are a test.",
        "prompt": "Say hello.",
    })
    assert resp.status_code == 503
    assert "unavailable" in resp.json()["detail"].lower()


def test_synthesize_placeholder_key(client, monkeypatch):
    """Synthesize returns 503 when key starts with <."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "<your-key-here>")
    resp = client.post("/api/synthesize", json={
        "system": "test",
        "prompt": "test",
    })
    assert resp.status_code == 503


def test_synthesize_success(client, monkeypatch):
    """Synthesize proxies to Anthropic and returns text."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "content": [{"type": "text", "text": "Hello from Claude!"}],
    }

    with patch("claude_memory_kit.api.app.httpx.AsyncClient") as MockClient:
        mock_client_instance = AsyncMock()
        mock_client_instance.post.return_value = mock_response
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        MockClient.return_value = mock_client_instance

        resp = client.post("/api/synthesize", json={
            "system": "You are a test assistant.",
            "prompt": "Say hello.",
            "max_tokens": 100,
        })

    assert resp.status_code == 200
    assert resp.json()["text"] == "Hello from Claude!"


def test_synthesize_upstream_error(client, monkeypatch):
    """Synthesize returns 502 when Anthropic returns non-200."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key")

    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_response.text = "Rate limited"

    with patch("claude_memory_kit.api.app.httpx.AsyncClient") as MockClient:
        mock_client_instance = AsyncMock()
        mock_client_instance.post.return_value = mock_response
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        MockClient.return_value = mock_client_instance

        resp = client.post("/api/synthesize", json={
            "system": "test",
            "prompt": "test",
        })

    assert resp.status_code == 502
    assert "429" in resp.json()["detail"]


def test_synthesize_network_error(client, monkeypatch):
    """Synthesize returns 502 on network failure."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key")

    with patch("claude_memory_kit.api.app.httpx.AsyncClient") as MockClient:
        mock_client_instance = AsyncMock()
        mock_client_instance.post.side_effect = httpx.ConnectError("connection refused")
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        MockClient.return_value = mock_client_instance

        resp = client.post("/api/synthesize", json={
            "system": "test",
            "prompt": "test",
        })

    assert resp.status_code == 502
    assert "request failed" in resp.json()["detail"].lower()


def test_synthesize_validation_error(client, monkeypatch):
    """Synthesize rejects invalid input."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key")
    # max_tokens out of range
    resp = client.post("/api/synthesize", json={
        "system": "test",
        "prompt": "test",
        "max_tokens": 99999,
    })
    assert resp.status_code == 422


# ---- Team API Tests ----

class TestTeamAPI:
    def test_create_team(self, client):
        resp = client.post("/api/teams", json={"name": "Test Team"})
        assert resp.status_code == 200
        data = resp.json()["team"]
        assert data["name"] == "Test Team"
        assert data["id"].startswith("team_")

    def test_list_teams(self, client):
        # Create a team first
        client.post("/api/teams", json={"name": "My Team"})
        resp = client.get("/api/teams")
        assert resp.status_code == 200
        teams = resp.json()["teams"]
        assert len(teams) >= 1
        assert any(t["name"] == "My Team" for t in teams)

    def test_get_team_detail(self, client):
        create_resp = client.post("/api/teams", json={"name": "Detail Team"})
        team_id = create_resp.json()["team"]["id"]

        resp = client.get(f"/api/teams/{team_id}")
        assert resp.status_code == 200
        team = resp.json()["team"]
        assert team["name"] == "Detail Team"
        assert "members" in team
        assert len(team["members"]) == 1  # owner

    def test_get_team_not_member(self, client, setup_store):
        # Create a team as a different user
        setup_store.auth_db.create_team("team_other", "Other", "other_user")
        resp = client.get("/api/teams/team_other")
        assert resp.status_code == 403

    def test_delete_team(self, client):
        create_resp = client.post("/api/teams", json={"name": "Delete Me"})
        team_id = create_resp.json()["team"]["id"]

        resp = client.delete(f"/api/teams/{team_id}")
        assert resp.status_code == 200
        assert resp.json()["result"] == "deleted"

    def test_delete_team_not_owner(self, client, setup_store):
        # Create team owned by someone else, add local as member
        setup_store.auth_db.create_team("team_notmine", "Not Mine", "other_user")
        setup_store.auth_db.add_team_member("team_notmine", "local", "member")

        resp = client.delete("/api/teams/team_notmine")
        assert resp.status_code == 403

    def test_add_member(self, client):
        create_resp = client.post("/api/teams", json={"name": "Invite Team"})
        team_id = create_resp.json()["team"]["id"]

        resp = client.post(
            f"/api/teams/{team_id}/members",
            json={"user_id": "new_user", "role": "member"},
        )
        assert resp.status_code == 200
        assert resp.json()["member"]["user_id"] == "new_user"

    def test_add_member_not_admin(self, client, setup_store):
        setup_store.auth_db.create_team("team_noadmin", "No Admin", "other_user")
        setup_store.auth_db.add_team_member("team_noadmin", "local", "member")

        resp = client.post(
            "/api/teams/team_noadmin/members",
            json={"user_id": "another", "role": "member"},
        )
        assert resp.status_code == 403

    def test_remove_member(self, client):
        create_resp = client.post("/api/teams", json={"name": "Remove Team"})
        team_id = create_resp.json()["team"]["id"]
        client.post(
            f"/api/teams/{team_id}/members",
            json={"user_id": "removable", "role": "member"},
        )

        resp = client.delete(f"/api/teams/{team_id}/members/removable")
        assert resp.status_code == 200

    def test_remove_self(self, client, setup_store):
        setup_store.auth_db.create_team("team_selfleave", "Self Leave", "other_user")
        setup_store.auth_db.add_team_member("team_selfleave", "local", "member")

        resp = client.delete("/api/teams/team_selfleave/members/local")
        assert resp.status_code == 200

    def test_list_team_memories(self, client, setup_store):
        create_resp = client.post("/api/teams", json={"name": "Mem Team"})
        team_id = create_resp.json()["team"]["id"]

        # Insert a team memory directly
        mem = _make_memory(id="mem_team_001", content="shared knowledge")
        setup_store.qdrant.insert_memory(
            mem, user_id=f"team:{team_id}",
            visibility="team", team_id=team_id, created_by="local",
        )

        resp = client.get(f"/api/teams/{team_id}/memories")
        assert resp.status_code == 200
        memories = resp.json()["memories"]
        assert len(memories) >= 1

    def test_create_team_rule(self, client):
        create_resp = client.post("/api/teams", json={"name": "Rule Team"})
        team_id = create_resp.json()["team"]["id"]

        resp = client.post(
            f"/api/teams/{team_id}/rules",
            json={"scope": "global", "condition": "always be kind", "enforcement": "suggest"},
        )
        assert resp.status_code == 200
        assert resp.json()["rule"] is not None

    def test_list_team_rules(self, client):
        create_resp = client.post("/api/teams", json={"name": "List Rules Team"})
        team_id = create_resp.json()["team"]["id"]

        client.post(
            f"/api/teams/{team_id}/rules",
            json={"scope": "global", "condition": "test rule", "enforcement": "enforce"},
        )

        resp = client.get(f"/api/teams/{team_id}/rules")
        assert resp.status_code == 200
        rules = resp.json()["rules"]
        assert len(rules) >= 1
