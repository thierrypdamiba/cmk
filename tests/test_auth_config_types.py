"""Tests for auth.py, auth_keys.py, cli_auth.py, config.py, types.py."""

import json
import os
import stat
import tempfile
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, AsyncMock

import pytest
from starlette.testclient import TestClient
from fastapi import Request

from claude_memory_kit.types import (
    Gate, DecayClass, Memory, JournalEntry,
    IdentityCard, Visibility, SearchResult, ExtractedMemory,
)
from claude_memory_kit import config as config_module
from claude_memory_kit import auth as auth_module
from claude_memory_kit import auth_keys
from claude_memory_kit import cli_auth


# ===========================================================================
# types.py
# ===========================================================================


class TestGate:
    def test_from_str_valid(self):
        assert Gate.from_str("behavioral") == Gate.behavioral

    def test_from_str_valid_uppercase(self):
        assert Gate.from_str("RELATIONAL") == Gate.relational

    def test_from_str_invalid(self):
        assert Gate.from_str("invalid") is None

    def test_from_str_empty(self):
        assert Gate.from_str("") is None

    def test_all_gates_roundtrip(self):
        for g in Gate:
            assert Gate.from_str(g.value) == g


class TestDecayClass:
    def test_half_life_never(self):
        assert DecayClass.never.half_life_days() is None

    def test_half_life_slow(self):
        assert DecayClass.slow.half_life_days() == 180.0

    def test_half_life_moderate(self):
        assert DecayClass.moderate.half_life_days() == 90.0

    def test_half_life_fast(self):
        assert DecayClass.fast.half_life_days() == 30.0

    def test_from_gate_promissory(self):
        assert DecayClass.from_gate(Gate.promissory) == DecayClass.never

    def test_from_gate_relational(self):
        assert DecayClass.from_gate(Gate.relational) == DecayClass.slow

    def test_from_gate_epistemic(self):
        assert DecayClass.from_gate(Gate.epistemic) == DecayClass.moderate

    def test_from_gate_behavioral(self):
        assert DecayClass.from_gate(Gate.behavioral) == DecayClass.fast

    def test_from_gate_correction(self):
        assert DecayClass.from_gate(Gate.correction) == DecayClass.moderate


class TestMemoryModel:
    def test_memory_all_fields(self):
        now = datetime.now(timezone.utc)
        mem = Memory(
            id="m1",
            created=now,
            gate=Gate.behavioral,
            person="Alice",
            project="proj-x",
            confidence=0.85,
            last_accessed=now,
            access_count=3,
            decay_class=DecayClass.fast,
            content="test content",
            pinned=True,
            sensitivity="sensitive",
            sensitivity_reason="personal info",
        )
        assert mem.id == "m1"
        assert mem.person == "Alice"
        assert mem.pinned is True
        assert mem.sensitivity == "sensitive"

    def test_memory_defaults(self):
        now = datetime.now(timezone.utc)
        mem = Memory(
            id="m2",
            created=now,
            gate=Gate.epistemic,
            last_accessed=now,
            decay_class=DecayClass.moderate,
            content="minimal",
        )
        assert mem.person is None
        assert mem.project is None
        assert mem.confidence == 0.9
        assert mem.access_count == 1
        assert mem.pinned is False
        assert mem.sensitivity is None
        assert mem.sensitivity_reason is None


class TestJournalEntry:
    def test_journal_entry(self):
        now = datetime.now(timezone.utc)
        entry = JournalEntry(
            timestamp=now,
            gate=Gate.behavioral,
            content="did a thing",
        )
        assert entry.person is None
        assert entry.project is None
        assert entry.content == "did a thing"


class TestIdentityCard:
    def test_identity_card(self):
        now = datetime.now(timezone.utc)
        card = IdentityCard(
            content="I am a developer",
            last_updated=now,
        )
        assert card.person is None
        assert card.project is None
        assert card.content == "I am a developer"


class TestVisibility:
    def test_private_default(self):
        assert Visibility.private == "private"

    def test_team_value(self):
        assert Visibility.team == "team"


class TestSearchResult:
    def test_search_result(self):
        now = datetime.now(timezone.utc)
        mem = Memory(
            id="sr1", created=now, gate=Gate.epistemic,
            last_accessed=now, decay_class=DecayClass.moderate,
            content="test",
        )
        sr = SearchResult(memory=mem, score=0.95, source="vector")
        assert sr.score == 0.95
        assert sr.source == "vector"


class TestExtractedMemory:
    def test_defaults(self):
        em = ExtractedMemory(gate="behavioral", content="likes coffee")
        assert em.person is None
        assert em.project is None
        assert em.gate == "behavioral"


# ===========================================================================
# config.py
# ===========================================================================


class TestConfig:
    def test_get_model_default(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
        model = config_module.get_model()
        assert model == config_module.OPUS

    def test_get_model_custom(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")
        model = config_module.get_model()
        assert model == "claude-sonnet-4-5-20250929"

    def test_get_api_key_empty(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "")
        with patch("claude_memory_kit.cli_auth.get_api_key", return_value=None):
            key = config_module.get_api_key()
        assert key == ""

    def test_get_api_key_placeholder(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "<your-api-key>")
        with patch("claude_memory_kit.cli_auth.get_api_key", return_value=None):
            key = config_module.get_api_key()
        assert key == "<your-api-key>"

    def test_get_api_key_real(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-real-key-123")
        with patch("claude_memory_kit.cli_auth.get_api_key", return_value=None):
            key = config_module.get_api_key()
        assert key == "sk-ant-real-key-123"

    def test_get_api_key_cmk_cloud_key(self, monkeypatch):
        """CMK cloud key takes priority over local ANTHROPIC_API_KEY."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-local-key")
        with patch("claude_memory_kit.cli_auth.get_api_key", return_value="cmk-sk-cloud-key-123"):
            key = config_module.get_api_key()
        assert key == "cmk-sk-cloud-key-123"

    def test_get_store_path_default(self, monkeypatch):
        monkeypatch.delenv("MEMORY_STORE_PATH", raising=False)
        path = config_module.get_store_path()
        assert path.endswith(".claude-memory")

    def test_get_store_path_custom(self, monkeypatch):
        monkeypatch.setenv("MEMORY_STORE_PATH", "/tmp/custom-store")
        path = config_module.get_store_path()
        assert path == "/tmp/custom-store"

    def test_get_qdrant_config_local(self, monkeypatch):
        monkeypatch.setenv("QDRANT_URL", "")
        cfg = config_module.get_qdrant_config()
        assert cfg["mode"] == "local"

    def test_get_qdrant_config_cloud(self, monkeypatch):
        monkeypatch.setenv("QDRANT_URL", "https://my-cluster.qdrant.io")
        monkeypatch.setenv("QDRANT_API_KEY", "qdrant-key-123")
        monkeypatch.setenv("JINA_API_KEY", "jina-key-456")
        cfg = config_module.get_qdrant_config()
        assert cfg["mode"] == "cloud"
        assert cfg["url"] == "https://my-cluster.qdrant.io"
        assert cfg["api_key"] == "qdrant-key-123"
        assert cfg["jina_api_key"] == "jina-key-456"

    def test_get_qdrant_config_placeholder_url(self, monkeypatch):
        monkeypatch.setenv("QDRANT_URL", "<your-qdrant-url>")
        cfg = config_module.get_qdrant_config()
        assert cfg["mode"] == "local"

    def test_is_cloud_mode_false(self, monkeypatch):
        monkeypatch.setenv("QDRANT_URL", "")
        assert config_module.is_cloud_mode() is False

    def test_is_cloud_mode_true(self, monkeypatch):
        monkeypatch.setenv("QDRANT_URL", "https://qdrant.example.com")
        monkeypatch.setenv("QDRANT_API_KEY", "key")
        monkeypatch.setenv("JINA_API_KEY", "jk")
        assert config_module.is_cloud_mode() is True


# ===========================================================================
# auth.py
# ===========================================================================


class TestAuth:
    def test_is_auth_enabled_no_url(self, monkeypatch):
        monkeypatch.setenv("BETTER_AUTH_URL", "")
        monkeypatch.setenv("BETTER_AUTH_SECRET", "some-secret")
        assert auth_module.is_auth_enabled() is False

    def test_is_auth_enabled_placeholder(self, monkeypatch):
        monkeypatch.setenv("BETTER_AUTH_URL", "<your-url>")
        monkeypatch.setenv("BETTER_AUTH_SECRET", "some-secret")
        assert auth_module.is_auth_enabled() is False

    def test_is_auth_enabled_no_secret(self, monkeypatch):
        monkeypatch.setenv("BETTER_AUTH_URL", "https://cmk.dev")
        monkeypatch.setenv("BETTER_AUTH_SECRET", "")
        # Reset the JWK client cache
        monkeypatch.setattr(auth_module, "_jwk_client", None)
        monkeypatch.setattr(auth_module, "_jwk_cache_time", 0)
        assert auth_module.is_auth_enabled() is False

    def test_is_auth_enabled_both_set(self, monkeypatch):
        monkeypatch.setenv("BETTER_AUTH_URL", "https://cmk.dev")
        monkeypatch.setenv("BETTER_AUTH_SECRET", "real-secret-abc")
        assert auth_module.is_auth_enabled() is True

    def test_extract_bearer_present(self):
        request = MagicMock()
        request.headers = {"authorization": "Bearer my-token-123"}
        result = auth_module._extract_bearer(request)
        assert result == "my-token-123"

    def test_extract_bearer_missing(self):
        request = MagicMock()
        request.headers = {}
        result = auth_module._extract_bearer(request)
        assert result is None

    def test_extract_bearer_no_prefix(self):
        request = MagicMock()
        request.headers = {"authorization": "Basic abc123"}
        result = auth_module._extract_bearer(request)
        assert result is None

    def test_local_user_dict(self):
        assert auth_module.LOCAL_USER["id"] == "local"
        assert auth_module.LOCAL_USER["email"] is None
        assert "plan" in auth_module.LOCAL_USER

    @pytest.mark.asyncio
    async def test_get_current_user_auth_disabled(self, monkeypatch):
        monkeypatch.setenv("BETTER_AUTH_URL", "")
        monkeypatch.setenv("BETTER_AUTH_SECRET", "")
        request = MagicMock()
        result = await auth_module.get_current_user(request)
        assert result["id"] == "local"

    @pytest.mark.asyncio
    async def test_optional_auth_disabled(self, monkeypatch):
        monkeypatch.setenv("BETTER_AUTH_URL", "")
        monkeypatch.setenv("BETTER_AUTH_SECRET", "")
        request = MagicMock()
        result = await auth_module.optional_auth(request)
        assert result["id"] == "local"


# ===========================================================================
# auth_keys.py
# ===========================================================================


class TestAuthKeys:
    def test_generate_api_key_prefix(self):
        key = auth_keys.generate_api_key()
        assert key.startswith("cmk-sk-")

    def test_generate_api_key_length(self):
        key = auth_keys.generate_api_key()
        # cmk-sk- (7 chars) + 64 hex chars = 71 total
        assert len(key) == 71

    def test_generate_api_key_unique(self):
        k1 = auth_keys.generate_api_key()
        k2 = auth_keys.generate_api_key()
        assert k1 != k2

    def test_hash_key_hex(self):
        hashed = auth_keys.hash_key("cmk-sk-test123")
        assert len(hashed) == 64
        assert all(c in "0123456789abcdef" for c in hashed)

    def test_hash_key_deterministic(self):
        h1 = auth_keys.hash_key("cmk-sk-same-input")
        h2 = auth_keys.hash_key("cmk-sk-same-input")
        assert h1 == h2

    def test_create_api_key(self, db):
        result = auth_keys.create_api_key(db, "user_123", "my-key")
        assert "id" in result
        assert "key" in result
        assert result["key"].startswith("cmk-sk-")
        assert "prefix" in result
        assert result["name"] == "my-key"

    def test_validate_api_key_valid(self, db):
        # Create a user first
        db.upsert_user("user_v1", "test@example.com", "Test")
        result = auth_keys.create_api_key(db, "user_v1", "test-key")
        raw_key = result["key"]

        validated = auth_keys.validate_api_key(raw_key, db)
        assert validated is not None
        assert validated["id"] == "user_v1"
        assert validated["email"] == "test@example.com"

    def test_validate_api_key_invalid(self, db):
        result = auth_keys.validate_api_key("cmk-sk-bogus-key-that-doesnt-exist", db)
        assert result is None

    def test_validate_api_key_no_db(self):
        result = auth_keys.validate_api_key("cmk-sk-whatever", None)
        assert result is None

    def test_validate_api_key_wrong_prefix(self, db):
        result = auth_keys.validate_api_key("wrong-prefix-key", db)
        assert result is None

    def test_list_keys(self, db):
        auth_keys.create_api_key(db, "user_list", "key1")
        auth_keys.create_api_key(db, "user_list", "key2")
        keys = auth_keys.list_keys(db, "user_list")
        assert len(keys) == 2

    def test_revoke_key(self, db):
        result = auth_keys.create_api_key(db, "user_rev", "revocable")
        key_id = result["id"]

        ok = auth_keys.revoke_key(db, key_id, "user_rev")
        assert ok is True

        # Validate should fail after revocation
        validated = auth_keys.validate_api_key(result["key"], db)
        assert validated is None

    def test_revoke_key_nonexistent(self, db):
        ok = auth_keys.revoke_key(db, "nonexistent-id", "user_x")
        assert ok is False


# ===========================================================================
# cli_auth.py
# ===========================================================================


class TestCliAuth:
    def test_get_user_id_from_env(self, monkeypatch):
        monkeypatch.setenv("CMK_USER_ID", "env-user-42")
        result = cli_auth.get_user_id()
        assert result == "env-user-42"

    def test_get_user_id_from_credentials(self, monkeypatch, tmp_path):
        monkeypatch.delenv("CMK_USER_ID", raising=False)
        creds_file = tmp_path / "credentials.json"
        creds_file.write_text(json.dumps({"user_id": "cred-user-99"}))
        monkeypatch.setattr(cli_auth, "CREDENTIALS_FILE", str(creds_file))
        result = cli_auth.get_user_id()
        assert result == "cred-user-99"

    def test_get_user_id_default(self, monkeypatch, tmp_path):
        monkeypatch.delenv("CMK_USER_ID", raising=False)
        creds_file = tmp_path / "nonexistent" / "credentials.json"
        monkeypatch.setattr(cli_auth, "CREDENTIALS_FILE", str(creds_file))
        result = cli_auth.get_user_id()
        assert result == "local"

    def test_load_credentials_missing_file(self, monkeypatch, tmp_path):
        creds_file = tmp_path / "does_not_exist.json"
        monkeypatch.setattr(cli_auth, "CREDENTIALS_FILE", str(creds_file))
        result = cli_auth.load_credentials()
        assert result is None

    def test_load_credentials_valid(self, monkeypatch, tmp_path):
        creds_file = tmp_path / "credentials.json"
        data = {"api_key": "cmk-sk-test", "user_id": "u1", "email": "a@b.com"}
        creds_file.write_text(json.dumps(data))
        monkeypatch.setattr(cli_auth, "CREDENTIALS_FILE", str(creds_file))
        result = cli_auth.load_credentials()
        assert result["user_id"] == "u1"
        assert result["api_key"] == "cmk-sk-test"

    def test_load_credentials_corrupt(self, monkeypatch, tmp_path):
        creds_file = tmp_path / "credentials.json"
        creds_file.write_text("this is not json {{{")
        monkeypatch.setattr(cli_auth, "CREDENTIALS_FILE", str(creds_file))
        result = cli_auth.load_credentials()
        assert result is None

    def test_save_credentials_writes_file(self, monkeypatch, tmp_path):
        creds_dir = tmp_path / "creds-dir"
        creds_file = creds_dir / "credentials.json"
        monkeypatch.setattr(cli_auth, "CREDENTIALS_DIR", str(creds_dir))
        monkeypatch.setattr(cli_auth, "CREDENTIALS_FILE", str(creds_file))

        cli_auth._save_credentials({"api_key": "cmk-sk-x", "user_id": "u2"})

        assert creds_file.exists()
        data = json.loads(creds_file.read_text())
        assert data["user_id"] == "u2"

    def test_save_credentials_permissions(self, monkeypatch, tmp_path):
        creds_dir = tmp_path / "creds-perm"
        creds_file = creds_dir / "credentials.json"
        monkeypatch.setattr(cli_auth, "CREDENTIALS_DIR", str(creds_dir))
        monkeypatch.setattr(cli_auth, "CREDENTIALS_FILE", str(creds_file))

        cli_auth._save_credentials({"api_key": "cmk-sk-y"})

        mode = os.stat(str(creds_file)).st_mode
        assert stat.S_IMODE(mode) == 0o600
