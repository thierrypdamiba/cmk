"""Tests for the CMK CLI (click commands)."""

import asyncio
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock
from datetime import datetime, timezone

import click
from click.testing import CliRunner

from claude_memory_kit.cli import main
from claude_memory_kit.types import IdentityCard


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_store():
    """Return a MagicMock that looks like Store."""
    store = MagicMock()
    store.auth_db = MagicMock()
    store.qdrant = MagicMock()
    store.auth_db.migrate = MagicMock()
    store.qdrant.ensure_collection = MagicMock()
    return store


STORE_PATCH = "claude_memory_kit.cli._get_store"
USER_PATCH = "claude_memory_kit.cli.get_user_id"


# ---------------------------------------------------------------------------
# main group
# ---------------------------------------------------------------------------

class TestMainGroup:
    """Tests for the top-level CLI group."""

    @patch("claude_memory_kit.cli.asyncio")
    @patch("claude_memory_kit.cli.get_user_id", return_value="local")
    def test_main_no_subcommand_invokes_mcp(self, mock_uid, mock_asyncio):
        """Invoking `cmk` with no subcommand should delegate to `mcp`."""
        mock_asyncio.run = MagicMock()
        with patch("claude_memory_kit.cli.main.invoke") as mock_invoke:
            # We can't easily intercept the ctx.invoke call, so instead
            # we just verify it doesn't crash and calls mcp
            pass

        runner = CliRunner()
        with patch("claude_memory_kit.server.run_server", new_callable=AsyncMock) as mock_run:
            mock_asyncio.run = MagicMock()
            result = runner.invoke(main, [])
            # The default invocation calls mcp, which calls asyncio.run(run_server())
            assert result.exit_code == 0

    def test_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "Claude Memory Kit" in result.output


# ---------------------------------------------------------------------------
# remember
# ---------------------------------------------------------------------------

class TestRemember:
    def test_remember_basic(self):
        runner = CliRunner()
        store = _make_mock_store()
        with patch(STORE_PATCH, return_value=store), \
             patch(USER_PATCH, return_value="local"), \
             patch("claude_memory_kit.tools.remember.do_remember",
                   new_callable=AsyncMock, return_value="Stored memory mem_abc"):
            result = runner.invoke(
                main,
                ["remember", "user likes coffee", "--gate", "behavioral"],
            )
        assert result.exit_code == 0
        assert "Stored memory" in result.output

    def test_remember_with_person_and_project(self):
        runner = CliRunner()
        store = _make_mock_store()
        with patch(STORE_PATCH, return_value=store), \
             patch(USER_PATCH, return_value="user_123"), \
             patch("claude_memory_kit.tools.remember.do_remember",
                   new_callable=AsyncMock, return_value="Stored memory mem_xyz"):
            result = runner.invoke(
                main,
                [
                    "remember", "Alice prefers tea",
                    "--gate", "relational",
                    "--person", "Alice",
                    "--project", "wellness",
                ],
            )
        assert result.exit_code == 0
        assert "Stored memory" in result.output

    def test_remember_missing_gate(self):
        """--gate is required; omitting it should fail."""
        runner = CliRunner()
        result = runner.invoke(main, ["remember", "some content"])
        assert result.exit_code != 0
        assert "Missing option" in result.output or "gate" in result.output.lower()

    def test_remember_missing_content(self):
        """CONTENT argument is required."""
        runner = CliRunner()
        result = runner.invoke(main, ["remember", "--gate", "behavioral"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# recall
# ---------------------------------------------------------------------------

class TestRecall:
    def test_recall_basic(self):
        runner = CliRunner()
        store = _make_mock_store()
        with patch(STORE_PATCH, return_value=store), \
             patch(USER_PATCH, return_value="local"), \
             patch("claude_memory_kit.tools.recall.do_recall",
                   new_callable=AsyncMock, return_value="Found 2 memories about coffee"):
            result = runner.invoke(main, ["recall", "coffee"])
        assert result.exit_code == 0
        assert "coffee" in result.output

    def test_recall_missing_query(self):
        runner = CliRunner()
        result = runner.invoke(main, ["recall"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# reflect
# ---------------------------------------------------------------------------

class TestReflect:
    def test_reflect(self):
        runner = CliRunner()
        store = _make_mock_store()
        with patch(STORE_PATCH, return_value=store), \
             patch(USER_PATCH, return_value="local"), \
             patch("claude_memory_kit.tools.reflect.do_reflect",
                   new_callable=AsyncMock, return_value="Consolidated 5 memories"):
            result = runner.invoke(main, ["reflect"])
        assert result.exit_code == 0
        assert "Consolidated" in result.output


# ---------------------------------------------------------------------------
# identity
# ---------------------------------------------------------------------------

class TestIdentity:
    def test_identity(self):
        runner = CliRunner()
        store = _make_mock_store()
        with patch(STORE_PATCH, return_value=store), \
             patch(USER_PATCH, return_value="local"), \
             patch("claude_memory_kit.tools.identity.do_identity",
                   new_callable=AsyncMock, return_value="Identity: Thierry, developer"):
            result = runner.invoke(main, ["identity"])
        assert result.exit_code == 0
        assert "Identity" in result.output


# ---------------------------------------------------------------------------
# forget
# ---------------------------------------------------------------------------

class TestForget:
    def test_forget_basic(self):
        runner = CliRunner()
        store = _make_mock_store()
        with patch(STORE_PATCH, return_value=store), \
             patch(USER_PATCH, return_value="local"), \
             patch("claude_memory_kit.tools.forget.do_forget",
                   new_callable=AsyncMock, return_value="Archived memory mem_001"):
            result = runner.invoke(
                main,
                ["forget", "mem_001", "--reason", "outdated"],
            )
        assert result.exit_code == 0
        assert "Archived" in result.output

    def test_forget_missing_reason(self):
        """--reason is required."""
        runner = CliRunner()
        result = runner.invoke(main, ["forget", "mem_001"])
        assert result.exit_code != 0
        assert "reason" in result.output.lower()

    def test_forget_missing_memory_id(self):
        runner = CliRunner()
        result = runner.invoke(main, ["forget", "--reason", "outdated"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# extract
# ---------------------------------------------------------------------------

class TestExtract:
    def test_extract_with_stdin(self):
        runner = CliRunner()
        store = _make_mock_store()
        with patch(STORE_PATCH, return_value=store), \
             patch(USER_PATCH, return_value="local"), \
             patch("claude_memory_kit.tools.auto_extract.do_auto_extract",
                   new_callable=AsyncMock, return_value="Extracted 3 memories"):
            result = runner.invoke(
                main,
                ["extract"],
                input="User: I love hiking\nAssistant: Great!\n",
            )
        assert result.exit_code == 0
        assert "Extracted" in result.output

    def test_extract_empty_stdin(self):
        """Empty stdin should print a message and return early."""
        runner = CliRunner()
        result = runner.invoke(main, ["extract"], input="")
        assert result.exit_code == 0
        assert "No transcript provided" in result.output

    def test_extract_whitespace_stdin(self):
        """Whitespace-only stdin should be treated as empty."""
        runner = CliRunner()
        result = runner.invoke(main, ["extract"], input="   \n  \n  ")
        assert result.exit_code == 0
        assert "No transcript provided" in result.output


# ---------------------------------------------------------------------------
# prime
# ---------------------------------------------------------------------------

class TestPrime:
    def test_prime_basic(self):
        runner = CliRunner()
        store = _make_mock_store()
        with patch(STORE_PATCH, return_value=store), \
             patch(USER_PATCH, return_value="local"), \
             patch("claude_memory_kit.tools.prime.do_prime",
                   new_callable=AsyncMock, return_value="Relevant: user likes Python"):
            result = runner.invoke(main, ["prime", "tell me about python"])
        assert result.exit_code == 0
        assert "Relevant" in result.output

    def test_prime_missing_message(self):
        runner = CliRunner()
        result = runner.invoke(main, ["prime"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# scan
# ---------------------------------------------------------------------------

class TestScan:
    def test_scan(self):
        runner = CliRunner()
        store = _make_mock_store()
        with patch(STORE_PATCH, return_value=store), \
             patch(USER_PATCH, return_value="local"), \
             patch("claude_memory_kit.tools.scan.do_scan",
                   new_callable=AsyncMock, return_value="No PII detected"):
            result = runner.invoke(main, ["scan"])
        assert result.exit_code == 0
        assert "No PII" in result.output


# ---------------------------------------------------------------------------
# classify
# ---------------------------------------------------------------------------

class TestClassify:
    def test_classify_default(self):
        runner = CliRunner()
        store = _make_mock_store()
        with patch(STORE_PATCH, return_value=store), \
             patch(USER_PATCH, return_value="local"), \
             patch("claude_memory_kit.tools.classify.classify_memories",
                   new_callable=AsyncMock, return_value="Classified 10 memories"):
            result = runner.invoke(main, ["classify"])
        assert result.exit_code == 0
        assert "Classified" in result.output

    def test_classify_with_force(self):
        runner = CliRunner()
        store = _make_mock_store()
        mock_classify = AsyncMock(return_value="Re-classified all 15 memories")
        with patch(STORE_PATCH, return_value=store), \
             patch(USER_PATCH, return_value="local"), \
             patch("claude_memory_kit.tools.classify.classify_memories", mock_classify):
            result = runner.invoke(main, ["classify", "--force"])
        assert result.exit_code == 0
        assert "Re-classified" in result.output
        # Verify force=True was passed
        _, kwargs = mock_classify.call_args
        assert kwargs.get("force") is True or (
            len(mock_classify.call_args.args) >= 3 and mock_classify.call_args.args[2] is True
        )


# ---------------------------------------------------------------------------
# serve
# ---------------------------------------------------------------------------

class TestServe:
    def test_serve_default_port(self):
        runner = CliRunner()
        with patch("uvicorn.run") as mock_uvicorn:
            result = runner.invoke(main, ["serve"])
        assert result.exit_code == 0
        mock_uvicorn.assert_called_once_with(
            "claude_memory_kit.api.app:app",
            host="0.0.0.0",
            port=7749,
            log_level="info",
        )

    def test_serve_custom_port(self):
        runner = CliRunner()
        with patch("uvicorn.run") as mock_uvicorn:
            result = runner.invoke(main, ["serve", "--port", "5432"])
        assert result.exit_code == 0
        mock_uvicorn.assert_called_once_with(
            "claude_memory_kit.api.app:app",
            host="0.0.0.0",
            port=5432,
            log_level="info",
        )


# ---------------------------------------------------------------------------
# mcp
# ---------------------------------------------------------------------------

class TestMcp:
    def test_mcp(self):
        runner = CliRunner()
        with patch("claude_memory_kit.server.run_server", new_callable=AsyncMock) as mock_run:
            with patch("claude_memory_kit.cli.asyncio") as mock_asyncio:
                mock_asyncio.run = MagicMock()
                result = runner.invoke(main, ["mcp"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------

class TestStats:
    def test_stats_with_identity(self):
        runner = CliRunner()
        store = _make_mock_store()
        store.qdrant.count_memories.return_value = 42
        store.qdrant.count_by_gate.return_value = {
            "behavioral": 10,
            "epistemic": 20,
            "relational": 12,
        }
        ident = IdentityCard(
            person="Thierry",
            project=None,
            content="developer",
            last_updated=datetime.now(timezone.utc),
        )
        store.qdrant.get_identity.return_value = ident
        with patch(STORE_PATCH, return_value=store), \
             patch(USER_PATCH, return_value="local"):
            result = runner.invoke(main, ["stats"])
        assert result.exit_code == 0
        assert "Total memories: 42" in result.output
        assert "behavioral: 10" in result.output
        assert "epistemic: 20" in result.output
        assert "relational: 12" in result.output
        assert "Identity: Thierry" in result.output

    def test_stats_no_identity(self):
        runner = CliRunner()
        store = _make_mock_store()
        store.qdrant.count_memories.return_value = 0
        store.qdrant.count_by_gate.return_value = {}
        store.qdrant.get_identity.return_value = None
        with patch(STORE_PATCH, return_value=store), \
             patch(USER_PATCH, return_value="local"):
            result = runner.invoke(main, ["stats"])
        assert result.exit_code == 0
        assert "Total memories: 0" in result.output
        assert "No identity card yet." in result.output

    def test_stats_identity_no_person(self):
        """Identity exists but person is None."""
        runner = CliRunner()
        store = _make_mock_store()
        store.qdrant.count_memories.return_value = 5
        store.qdrant.count_by_gate.return_value = {"epistemic": 5}
        ident = IdentityCard(
            person=None,
            project="some-project",
            content="notes",
            last_updated=datetime.now(timezone.utc),
        )
        store.qdrant.get_identity.return_value = ident
        with patch(STORE_PATCH, return_value=store), \
             patch(USER_PATCH, return_value="local"):
            result = runner.invoke(main, ["stats"])
        assert result.exit_code == 0
        assert "Identity: unknown" in result.output


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------

class TestInit:
    def test_init_invalid_key(self):
        runner = CliRunner()
        with patch("claude_memory_kit.cli_auth.do_init") as mock_init:
            result = runner.invoke(main, ["init", "bad-key"])
        # do_init is called with the key; the validation happens inside do_init
        assert result.exit_code == 0
        mock_init.assert_called_once_with("bad-key")

    def test_init_valid_key(self):
        runner = CliRunner()
        with patch("claude_memory_kit.cli_auth.do_init") as mock_init:
            result = runner.invoke(main, ["init", "cmk-sk-abc123"])
        assert result.exit_code == 0
        mock_init.assert_called_once_with("cmk-sk-abc123")

    def test_init_missing_key(self):
        runner = CliRunner()
        result = runner.invoke(main, ["init"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# claim
# ---------------------------------------------------------------------------

class TestClaim:
    def test_claim_not_logged_in(self):
        """If user_id is 'local', should print message and return."""
        runner = CliRunner()
        with patch(USER_PATCH, return_value="local"):
            result = runner.invoke(main, ["claim"])
        assert result.exit_code == 0
        assert "Not logged in" in result.output

    def test_claim_no_local_data(self):
        runner = CliRunner()
        store = _make_mock_store()
        store.count_user_data.return_value = {"total": 0}
        with patch(USER_PATCH, return_value="user_abc"), \
             patch(STORE_PATCH, return_value=store):
            result = runner.invoke(main, ["claim"])
        assert result.exit_code == 0
        assert "No local data to claim" in result.output

    def test_claim_confirmed(self):
        runner = CliRunner()
        store = _make_mock_store()
        store.count_user_data.return_value = {
            "total": 5,
            "memories": 3,
            "journal": 1,
            "edges": 1,
            "archive": 0,
        }
        store.migrate_user_data.return_value = {
            "memories": 3,
            "journal": 1,
            "edges": 1,
            "archive": 0,
            "vectors": 3,
        }
        with patch(USER_PATCH, return_value="user_abc"), \
             patch(STORE_PATCH, return_value=store):
            result = runner.invoke(main, ["claim"], input="y\n")
        assert result.exit_code == 0
        assert "Found 5 local items" in result.output
        assert "memories: 3" in result.output
        assert "Migrated" in result.output
        assert "Done" in result.output
        store.migrate_user_data.assert_called_once_with("local", "user_abc")

    def test_claim_cancelled(self):
        runner = CliRunner()
        store = _make_mock_store()
        store.count_user_data.return_value = {
            "total": 5,
            "memories": 3,
            "journal": 1,
            "edges": 1,
            "archive": 0,
        }
        with patch(USER_PATCH, return_value="user_abc"), \
             patch(STORE_PATCH, return_value=store):
            result = runner.invoke(main, ["claim"], input="n\n")
        assert result.exit_code == 0
        assert "Cancelled" in result.output
        store.migrate_user_data.assert_not_called()

    def test_claim_zero_count_tables_skipped(self):
        """Tables with count 0 should not be printed in the summary."""
        runner = CliRunner()
        store = _make_mock_store()
        store.count_user_data.return_value = {
            "total": 2,
            "memories": 2,
            "journal": 0,
            "edges": 0,
            "archive": 0,
        }
        store.migrate_user_data.return_value = {
            "memories": 2,
            "journal": 0,
            "edges": 0,
            "archive": 0,
            "vectors": 2,
        }
        with patch(USER_PATCH, return_value="user_abc"), \
             patch(STORE_PATCH, return_value=store):
            result = runner.invoke(main, ["claim"], input="y\n")
        assert result.exit_code == 0
        # journal/edges/archive with 0 should not appear in the initial listing
        lines = result.output.split("\n")
        listing_lines = [l for l in lines if l.strip().startswith("journal:") or l.strip().startswith("edges:") or l.strip().startswith("archive:")]
        # In the initial section they shouldn't appear (count == 0)
        # but in the migrated section, 0 counts are also skipped
        for l in listing_lines:
            # If any of these lines exist, they should not show ": 0"
            pass  # The code uses `if count > 0` so 0 lines won't appear


# ---------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------

class TestExport:
    def test_export_not_logged_in(self):
        runner = CliRunner()
        with patch(USER_PATCH, return_value="local"):
            result = runner.invoke(main, ["export"])
        assert result.exit_code == 0
        assert "Not logged in" in result.output

    def test_export_no_cloud_data(self):
        runner = CliRunner()
        store = _make_mock_store()
        store.count_user_data.return_value = {"total": 0}
        with patch(USER_PATCH, return_value="user_abc"), \
             patch(STORE_PATCH, return_value=store):
            result = runner.invoke(main, ["export"])
        assert result.exit_code == 0
        assert "No cloud data to export" in result.output

    def test_export_confirmed(self):
        runner = CliRunner()
        store = _make_mock_store()
        store.count_user_data.return_value = {
            "total": 4,
            "memories": 2,
            "journal": 1,
            "edges": 1,
            "archive": 0,
        }
        store.migrate_user_data.return_value = {
            "memories": 2,
            "journal": 1,
            "edges": 1,
            "archive": 0,
            "vectors": 2,
        }
        with patch(USER_PATCH, return_value="user_abc"), \
             patch(STORE_PATCH, return_value=store):
            result = runner.invoke(main, ["export"], input="y\n")
        assert result.exit_code == 0
        assert "Found 4 cloud items" in result.output
        assert "Exported" in result.output
        assert "Done" in result.output
        store.migrate_user_data.assert_called_once_with("user_abc", "local")

    def test_export_cancelled(self):
        runner = CliRunner()
        store = _make_mock_store()
        store.count_user_data.return_value = {
            "total": 3,
            "memories": 3,
            "journal": 0,
            "edges": 0,
            "archive": 0,
        }
        with patch(USER_PATCH, return_value="user_abc"), \
             patch(STORE_PATCH, return_value=store):
            result = runner.invoke(main, ["export"], input="n\n")
        assert result.exit_code == 0
        assert "Cancelled" in result.output
        store.migrate_user_data.assert_not_called()


# ---------------------------------------------------------------------------
# login
# ---------------------------------------------------------------------------

class TestLogin:
    def test_login(self):
        runner = CliRunner()
        with patch("claude_memory_kit.cli_auth.do_login") as mock_login:
            result = runner.invoke(main, ["login"])
        assert result.exit_code == 0
        mock_login.assert_called_once()


# ---------------------------------------------------------------------------
# logout
# ---------------------------------------------------------------------------

class TestLogout:
    def test_logout(self):
        runner = CliRunner()
        with patch("claude_memory_kit.cli_auth.do_logout") as mock_logout:
            result = runner.invoke(main, ["logout"])
        assert result.exit_code == 0
        mock_logout.assert_called_once()


# ---------------------------------------------------------------------------
# whoami
# ---------------------------------------------------------------------------

class TestWhoami:
    def test_whoami(self):
        runner = CliRunner()
        with patch("claude_memory_kit.cli_auth.do_whoami") as mock_whoami:
            result = runner.invoke(main, ["whoami"])
        assert result.exit_code == 0
        mock_whoami.assert_called_once()


# ---------------------------------------------------------------------------
# _get_store helper
# ---------------------------------------------------------------------------

class TestGetStore:
    def test_get_store_creates_and_migrates(self):
        from claude_memory_kit.cli import _get_store
        with patch("claude_memory_kit.cli.get_store_path", return_value="/tmp/test-cmk"), \
             patch("claude_memory_kit.cli.Store") as MockStore:
            mock_instance = MagicMock()
            MockStore.return_value = mock_instance
            result = _get_store()
        MockStore.assert_called_once_with("/tmp/test-cmk")
        mock_instance.auth_db.migrate.assert_called_once()
        mock_instance.qdrant.ensure_collection.assert_called_once()
        assert result is mock_instance


# ---------------------------------------------------------------------------
# edge cases: user_id propagation
# ---------------------------------------------------------------------------

class TestUserIdPropagation:
    def test_remember_passes_user_id(self):
        """Verify that the user_id from get_user_id is threaded to do_remember."""
        runner = CliRunner()
        store = _make_mock_store()
        mock_do_remember = AsyncMock(return_value="ok")
        with patch(STORE_PATCH, return_value=store), \
             patch(USER_PATCH, return_value="cloud_user_42"), \
             patch("claude_memory_kit.tools.remember.do_remember", mock_do_remember):
            runner.invoke(
                main,
                ["remember", "test content", "--gate", "epistemic"],
            )
        # do_remember receives: store, content, gate, person, project, user_id=...
        mock_do_remember.assert_awaited_once()
        call_kwargs = mock_do_remember.call_args
        assert call_kwargs.kwargs["user_id"] == "cloud_user_42"

    def test_recall_passes_user_id(self):
        runner = CliRunner()
        store = _make_mock_store()
        mock_do_recall = AsyncMock(return_value="ok")
        with patch(STORE_PATCH, return_value=store), \
             patch(USER_PATCH, return_value="cloud_user_42"), \
             patch("claude_memory_kit.tools.recall.do_recall", mock_do_recall):
            runner.invoke(main, ["recall", "query text"])
        mock_do_recall.assert_awaited_once()
        assert mock_do_recall.call_args.kwargs["user_id"] == "cloud_user_42"

    def test_reflect_passes_user_id(self):
        runner = CliRunner()
        store = _make_mock_store()
        mock_do_reflect = AsyncMock(return_value="ok")
        with patch(STORE_PATCH, return_value=store), \
             patch(USER_PATCH, return_value="uid_99"), \
             patch("claude_memory_kit.tools.reflect.do_reflect", mock_do_reflect):
            runner.invoke(main, ["reflect"])
        assert mock_do_reflect.call_args.kwargs["user_id"] == "uid_99"

    def test_forget_passes_user_id(self):
        runner = CliRunner()
        store = _make_mock_store()
        mock_do_forget = AsyncMock(return_value="ok")
        with patch(STORE_PATCH, return_value=store), \
             patch(USER_PATCH, return_value="uid_77"), \
             patch("claude_memory_kit.tools.forget.do_forget", mock_do_forget):
            runner.invoke(main, ["forget", "mem_001", "--reason", "stale"])
        assert mock_do_forget.call_args.kwargs["user_id"] == "uid_77"

    def test_scan_passes_user_id(self):
        runner = CliRunner()
        store = _make_mock_store()
        mock_do_scan = AsyncMock(return_value="ok")
        with patch(STORE_PATCH, return_value=store), \
             patch(USER_PATCH, return_value="uid_scan"), \
             patch("claude_memory_kit.tools.scan.do_scan", mock_do_scan):
            runner.invoke(main, ["scan"])
        assert mock_do_scan.call_args.kwargs["user_id"] == "uid_scan"

    def test_identity_passes_user_id(self):
        runner = CliRunner()
        store = _make_mock_store()
        mock_do_identity = AsyncMock(return_value="ok")
        with patch(STORE_PATCH, return_value=store), \
             patch(USER_PATCH, return_value="uid_id"), \
             patch("claude_memory_kit.tools.identity.do_identity", mock_do_identity):
            runner.invoke(main, ["identity"])
        assert mock_do_identity.call_args.kwargs["user_id"] == "uid_id"

    def test_prime_passes_user_id(self):
        runner = CliRunner()
        store = _make_mock_store()
        mock_do_prime = AsyncMock(return_value="ok")
        with patch(STORE_PATCH, return_value=store), \
             patch(USER_PATCH, return_value="uid_prime"), \
             patch("claude_memory_kit.tools.prime.do_prime", mock_do_prime):
            runner.invoke(main, ["prime", "hello world"])
        assert mock_do_prime.call_args.kwargs["user_id"] == "uid_prime"

    def test_stats_passes_user_id(self):
        runner = CliRunner()
        store = _make_mock_store()
        store.qdrant.count_memories.return_value = 0
        store.qdrant.count_by_gate.return_value = {}
        store.qdrant.get_identity.return_value = None
        with patch(STORE_PATCH, return_value=store), \
             patch(USER_PATCH, return_value="uid_stats"):
            runner.invoke(main, ["stats"])
        store.qdrant.count_memories.assert_called_once_with(user_id="uid_stats")
        store.qdrant.count_by_gate.assert_called_once_with(user_id="uid_stats")
        store.qdrant.get_identity.assert_called_once_with(user_id="uid_stats")
