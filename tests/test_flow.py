"""Tests for Flow Mode: compression, transcript modification, hook orchestration."""

import json
import os
import tempfile
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from claude_memory_kit.config import (
    FLOW_CHAR_THRESHOLD,
    FLOW_DEFAULT_SKIP_TOOLS,
    get_flow_char_threshold,
    get_flow_skip_tools,
    is_flow_mode,
)
from claude_memory_kit.flow.transcript import (
    FLOW_PREFIX,
    replace_tool_output_in_transcript,
    _replace_in_entry,
)
from claude_memory_kit.types import DecayClass, Gate


# ---------------------------------------------------------------------------
# TestObservationGate
# ---------------------------------------------------------------------------

class TestObservationGate:
    """Tests for the observation gate in types.py."""

    def test_observation_gate_exists(self):
        assert Gate.observation == "observation"

    def test_observation_from_str(self):
        assert Gate.from_str("observation") == Gate.observation

    def test_observation_decay_is_fast(self):
        assert DecayClass.from_gate(Gate.observation) == DecayClass.fast

    def test_observation_half_life_30_days(self):
        dc = DecayClass.from_gate(Gate.observation)
        assert dc.half_life_days() == 30.0


# ---------------------------------------------------------------------------
# TestFlowConfig
# ---------------------------------------------------------------------------

class TestFlowConfig:
    """Tests for flow mode config helpers."""

    def test_is_flow_mode_false_by_default(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CMK_FLOW_MODE", None)
            assert is_flow_mode() is False

    def test_is_flow_mode_true(self):
        with patch.dict(os.environ, {"CMK_FLOW_MODE": "true"}):
            assert is_flow_mode() is True

    def test_is_flow_mode_1(self):
        with patch.dict(os.environ, {"CMK_FLOW_MODE": "1"}):
            assert is_flow_mode() is True

    def test_is_flow_mode_yes(self):
        with patch.dict(os.environ, {"CMK_FLOW_MODE": "yes"}):
            assert is_flow_mode() is True

    def test_is_flow_mode_false_string(self):
        with patch.dict(os.environ, {"CMK_FLOW_MODE": "false"}):
            assert is_flow_mode() is False

    def test_skip_tools_defaults(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CMK_FLOW_SKIP_TOOLS", None)
            tools = get_flow_skip_tools()
            assert "remember_this" in tools
            assert "recall_memories" in tools
            assert "mcp__claude-memory-kit__remember_this" in tools

    def test_skip_tools_custom_extends_defaults(self):
        with patch.dict(os.environ, {"CMK_FLOW_SKIP_TOOLS": "my_tool,other_tool"}):
            tools = get_flow_skip_tools()
            assert "my_tool" in tools
            assert "other_tool" in tools
            # Defaults still present
            assert "remember_this" in tools

    def test_skip_tools_empty_custom_returns_defaults(self):
        with patch.dict(os.environ, {"CMK_FLOW_SKIP_TOOLS": "  "}):
            tools = get_flow_skip_tools()
            assert tools == FLOW_DEFAULT_SKIP_TOOLS

    def test_char_threshold_default(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CMK_FLOW_THRESHOLD", None)
            assert get_flow_char_threshold() == FLOW_CHAR_THRESHOLD

    def test_char_threshold_custom(self):
        with patch.dict(os.environ, {"CMK_FLOW_THRESHOLD": "5000"}):
            assert get_flow_char_threshold() == 5000

    def test_char_threshold_invalid_returns_default(self):
        with patch.dict(os.environ, {"CMK_FLOW_THRESHOLD": "abc"}):
            assert get_flow_char_threshold() == FLOW_CHAR_THRESHOLD


# ---------------------------------------------------------------------------
# TestCompress
# ---------------------------------------------------------------------------

class TestCompress:
    """Tests for compress_tool_output."""

    @pytest.mark.asyncio
    async def test_compress_calls_anthropic_with_haiku(self):
        with patch(
            "claude_memory_kit.flow.compress._call_anthropic",
            new_callable=AsyncMock,
            return_value="  compressed output  ",
        ) as mock_call, patch(
            "claude_memory_kit.flow.compress.get_api_key",
            return_value="sk-ant-test-key",
        ):
            from claude_memory_kit.flow.compress import compress_tool_output
            from claude_memory_kit.config import HAIKU

            result = await compress_tool_output("Bash", "ls -la", "file1\nfile2\nfile3")
            assert result == "compressed output"
            mock_call.assert_awaited_once()
            call_kwargs = mock_call.call_args
            assert call_kwargs[1]["model"] == HAIKU
            assert call_kwargs[1]["max_tokens"] == 700

    @pytest.mark.asyncio
    async def test_compress_returns_none_without_api_key(self):
        with patch(
            "claude_memory_kit.flow.compress.get_api_key",
            return_value="",
        ):
            from claude_memory_kit.flow.compress import compress_tool_output

            result = await compress_tool_output("Bash", "ls", "output")
            assert result is None

    @pytest.mark.asyncio
    async def test_compress_returns_none_with_placeholder_key(self):
        with patch(
            "claude_memory_kit.flow.compress.get_api_key",
            return_value="<your-api-key>",
        ):
            from claude_memory_kit.flow.compress import compress_tool_output

            result = await compress_tool_output("Bash", "ls", "output")
            assert result is None

    @pytest.mark.asyncio
    async def test_compress_truncates_large_input(self):
        with patch(
            "claude_memory_kit.flow.compress._call_anthropic",
            new_callable=AsyncMock,
            return_value="truncated result",
        ) as mock_call, patch(
            "claude_memory_kit.flow.compress.get_api_key",
            return_value="sk-ant-test-key",
        ):
            from claude_memory_kit.flow.compress import compress_tool_output, MAX_INPUT_CHARS

            big_output = "x" * 20000
            await compress_tool_output("Read", "/some/file", big_output)

            user_msg = mock_call.call_args[0][1]
            assert "truncated" in user_msg

    @pytest.mark.asyncio
    async def test_compress_returns_none_on_api_error(self):
        with patch(
            "claude_memory_kit.flow.compress._call_anthropic",
            new_callable=AsyncMock,
            side_effect=RuntimeError("api error"),
        ), patch(
            "claude_memory_kit.flow.compress.get_api_key",
            return_value="sk-ant-test-key",
        ):
            from claude_memory_kit.flow.compress import compress_tool_output

            result = await compress_tool_output("Bash", "cmd", "output")
            assert result is None


# ---------------------------------------------------------------------------
# TestTranscript
# ---------------------------------------------------------------------------

class TestTranscript:
    """Tests for transcript JSONL modification."""

    def _write_jsonl(self, path, entries):
        with open(path, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")

    def test_replace_direct_tool_result(self, tmp_path):
        transcript = tmp_path / "transcript.jsonl"
        entries = [
            {"type": "tool_result", "tool_use_id": "tu_1", "content": "original output"},
            {"type": "tool_result", "tool_use_id": "tu_2", "content": "keep this"},
        ]
        self._write_jsonl(str(transcript), entries)

        result = replace_tool_output_in_transcript(str(transcript), "tu_1", "compressed")
        assert result is True

        with open(str(transcript)) as f:
            lines = [json.loads(line) for line in f]
        assert lines[0]["content"] == "[flow compressed] compressed"
        assert lines[1]["content"] == "keep this"

    def test_replace_content_array_text_block(self, tmp_path):
        transcript = tmp_path / "transcript.jsonl"
        entries = [
            {
                "type": "tool_result",
                "tool_use_id": "tu_1",
                "content": [{"type": "text", "text": "original"}],
            },
        ]
        self._write_jsonl(str(transcript), entries)

        result = replace_tool_output_in_transcript(str(transcript), "tu_1", "short")
        assert result is True

        with open(str(transcript)) as f:
            lines = [json.loads(line) for line in f]
        assert lines[0]["content"][0]["text"] == "[flow compressed] short"

    def test_replace_nested_tool_result_in_message(self, tmp_path):
        transcript = tmp_path / "transcript.jsonl"
        entries = [
            {
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": "tu_1", "content": "original"},
                ],
            },
        ]
        self._write_jsonl(str(transcript), entries)

        result = replace_tool_output_in_transcript(str(transcript), "tu_1", "compressed")
        assert result is True

        with open(str(transcript)) as f:
            lines = [json.loads(line) for line in f]
        assert lines[0]["content"][0]["content"] == "[flow compressed] compressed"

    def test_replace_output_field_format(self, tmp_path):
        transcript = tmp_path / "transcript.jsonl"
        entries = [
            {
                "role": "tool",
                "content": [
                    {"id": "tu_1", "output": "original output"},
                ],
            },
        ]
        self._write_jsonl(str(transcript), entries)

        result = replace_tool_output_in_transcript(str(transcript), "tu_1", "compressed")
        assert result is True

        with open(str(transcript)) as f:
            lines = [json.loads(line) for line in f]
        assert lines[0]["content"][0]["output"] == "[flow compressed] compressed"

    def test_id_not_found(self, tmp_path):
        transcript = tmp_path / "transcript.jsonl"
        entries = [
            {"type": "tool_result", "tool_use_id": "tu_1", "content": "output"},
        ]
        self._write_jsonl(str(transcript), entries)

        result = replace_tool_output_in_transcript(str(transcript), "tu_999", "compressed")
        assert result is False

    def test_missing_file(self):
        result = replace_tool_output_in_transcript("/nonexistent/path.jsonl", "tu_1", "x")
        assert result is False

    def test_empty_path(self):
        result = replace_tool_output_in_transcript("", "tu_1", "x")
        assert result is False

    def test_preserves_other_entries(self, tmp_path):
        transcript = tmp_path / "transcript.jsonl"
        entries = [
            {"role": "assistant", "content": "Hello"},
            {"type": "tool_result", "tool_use_id": "tu_1", "content": "original"},
            {"role": "user", "content": "Thanks"},
        ]
        self._write_jsonl(str(transcript), entries)

        replace_tool_output_in_transcript(str(transcript), "tu_1", "compressed")

        with open(str(transcript)) as f:
            lines = [json.loads(line) for line in f]
        assert lines[0] == {"role": "assistant", "content": "Hello"}
        assert lines[2] == {"role": "user", "content": "Thanks"}

    def test_handles_malformed_json_lines(self, tmp_path):
        transcript = tmp_path / "transcript.jsonl"
        with open(str(transcript), "w") as f:
            f.write('{"type":"tool_result","tool_use_id":"tu_1","content":"original"}\n')
            f.write("not valid json\n")
            f.write('{"role":"user","content":"ok"}\n')

        result = replace_tool_output_in_transcript(str(transcript), "tu_1", "compressed")
        assert result is True

        with open(str(transcript)) as f:
            lines = f.readlines()
        assert len(lines) == 3
        first = json.loads(lines[0])
        assert first["content"] == "[flow compressed] compressed"
        assert lines[1].strip() == "not valid json"


# ---------------------------------------------------------------------------
# TestReplaceInEntry
# ---------------------------------------------------------------------------

class TestReplaceInEntry:
    """Unit tests for _replace_in_entry helper."""

    def test_no_match_returns_false(self):
        entry = {"type": "message", "content": "hello"}
        assert _replace_in_entry(entry, "tu_1", "tagged") is False

    def test_wrong_tool_use_id_returns_false(self):
        entry = {"type": "tool_result", "tool_use_id": "tu_2", "content": "data"}
        assert _replace_in_entry(entry, "tu_1", "tagged") is False


# ---------------------------------------------------------------------------
# TestHook
# ---------------------------------------------------------------------------

class TestHook:
    """Tests for the hook orchestrator."""

    @pytest.mark.asyncio
    async def test_skips_small_output(self):
        from claude_memory_kit.flow.hook import _handle_hook

        result = await _handle_hook({
            "tool_name": "Bash",
            "tool_response": "small",
            "tool_use_id": "tu_1",
        })
        assert result is None

    @pytest.mark.asyncio
    async def test_skips_excluded_tools(self):
        from claude_memory_kit.flow.hook import _handle_hook

        big_output = "x" * 5000
        result = await _handle_hook({
            "tool_name": "remember_this",
            "tool_response": big_output,
            "tool_use_id": "tu_1",
        })
        assert result is None

    @pytest.mark.asyncio
    async def test_mcp_tool_returns_updated_output(self):
        from claude_memory_kit.flow.hook import _handle_hook

        big_output = "x" * 5000
        with patch(
            "claude_memory_kit.flow.compress.compress_tool_output",
            new_callable=AsyncMock,
            return_value="compressed mcp output",
        ), patch(
            "claude_memory_kit.flow.hook._store_observation",
            new_callable=AsyncMock,
        ):
            result = await _handle_hook({
                "tool_name": "mcp__some-server__some_tool",
                "tool_response": big_output,
                "tool_use_id": "tu_1",
            })
            assert result is not None
            assert "updatedMCPToolOutput" in result["hookSpecificOutput"]
            assert "[flow compressed]" in result["hookSpecificOutput"]["updatedMCPToolOutput"]

    @pytest.mark.asyncio
    async def test_builtin_tool_modifies_transcript(self):
        from claude_memory_kit.flow.hook import _handle_hook

        big_output = "x" * 5000
        with patch(
            "claude_memory_kit.flow.compress.compress_tool_output",
            new_callable=AsyncMock,
            return_value="compressed bash output",
        ), patch(
            "claude_memory_kit.flow.hook._store_observation",
            new_callable=AsyncMock,
        ), patch(
            "claude_memory_kit.flow.transcript.replace_tool_output_in_transcript",
            return_value=True,
        ) as mock_replace:
            result = await _handle_hook({
                "tool_name": "Bash",
                "tool_response": big_output,
                "tool_use_id": "tu_1",
                "transcript_path": "/tmp/test.jsonl",
            })
            assert result is None  # built-in tools return None
            mock_replace.assert_called_once_with("/tmp/test.jsonl", "tu_1", "compressed bash output")

    @pytest.mark.asyncio
    async def test_returns_none_when_compression_fails(self):
        from claude_memory_kit.flow.hook import _handle_hook

        big_output = "x" * 5000
        with patch(
            "claude_memory_kit.flow.compress.compress_tool_output",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await _handle_hook({
                "tool_name": "Bash",
                "tool_response": big_output,
                "tool_use_id": "tu_1",
            })
            assert result is None

    @pytest.mark.asyncio
    async def test_handles_dict_tool_input(self):
        from claude_memory_kit.flow.hook import _handle_hook

        big_output = "x" * 5000
        with patch(
            "claude_memory_kit.flow.compress.compress_tool_output",
            new_callable=AsyncMock,
            return_value="compressed",
        ), patch(
            "claude_memory_kit.flow.hook._store_observation",
            new_callable=AsyncMock,
        ):
            result = await _handle_hook({
                "tool_name": "mcp__server__tool",
                "tool_input": {"key": "value"},
                "tool_response": big_output,
                "tool_use_id": "tu_1",
            })
            assert result is not None

    @pytest.mark.asyncio
    async def test_handles_dict_tool_response(self):
        from claude_memory_kit.flow.hook import _handle_hook

        big_response = {"data": "x" * 5000}
        with patch(
            "claude_memory_kit.flow.compress.compress_tool_output",
            new_callable=AsyncMock,
            return_value="compressed",
        ), patch(
            "claude_memory_kit.flow.hook._store_observation",
            new_callable=AsyncMock,
        ):
            result = await _handle_hook({
                "tool_name": "mcp__server__tool",
                "tool_input": "query",
                "tool_response": big_response,
                "tool_use_id": "tu_1",
            })
            assert result is not None

    def test_run_flow_hook_exits_when_disabled(self):
        """run_flow_hook should exit immediately when flow mode is off."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CMK_FLOW_MODE", None)
            from claude_memory_kit.flow.hook import run_flow_hook
            # Should not raise, just return
            run_flow_hook()

    def test_run_flow_hook_fails_open_on_error(self):
        """run_flow_hook should never raise, even with bad input."""
        with patch.dict(os.environ, {"CMK_FLOW_MODE": "true"}), \
             patch("sys.stdin") as mock_stdin:
            mock_stdin.read.side_effect = IOError("broken pipe")
            from claude_memory_kit.flow.hook import run_flow_hook
            run_flow_hook()  # Should not raise


# ---------------------------------------------------------------------------
# TestStoreObservation
# ---------------------------------------------------------------------------

class TestStoreObservation:
    """Tests for observation storage."""

    @pytest.mark.asyncio
    async def test_stores_journal_entry(self):
        from claude_memory_kit.flow.hook import _store_observation

        mock_qdrant = MagicMock()
        mock_store = MagicMock()
        mock_store.qdrant = mock_qdrant

        with patch("claude_memory_kit.store.Store.__new__", return_value=mock_store), \
             patch("claude_memory_kit.store.Store.__init__", return_value=None), \
             patch("claude_memory_kit.cli_auth.get_user_id", return_value="test-user"):
            await _store_observation("Bash", "ls output with 50 files")

            mock_qdrant.ensure_collection.assert_called_once()
            mock_qdrant.insert_journal.assert_called_once()
            entry = mock_qdrant.insert_journal.call_args[0][0]
            assert entry.gate == Gate.observation
            assert "[Bash]" in entry.content
            assert "ls output" in entry.content

    @pytest.mark.asyncio
    async def test_store_observation_fails_silently(self):
        from claude_memory_kit.flow.hook import _store_observation

        with patch("claude_memory_kit.store.Store.__init__", side_effect=RuntimeError("lock")):
            # Should not raise
            await _store_observation("Bash", "output")


# ---------------------------------------------------------------------------
# TestBuildInstructionsFlowMode
# ---------------------------------------------------------------------------

class TestBuildInstructionsFlowMode:
    """Tests for flow mode observation injection in _build_instructions."""

    def _make_store(self, qdrant_db):
        store = MagicMock()
        store.qdrant = qdrant_db
        return store

    def test_observations_excluded_from_recent_context(self, qdrant_db):
        from claude_memory_kit.server import _build_instructions

        store = self._make_store(qdrant_db)
        qdrant_db.insert_journal_raw(
            date="2026-02-16",
            gate=Gate.observation,
            content="[Bash] found 50 files",
            user_id="test-user",
        )
        qdrant_db.insert_journal_raw(
            date="2026-02-16",
            gate=Gate.epistemic,
            content="Python uses HNSW",
            user_id="test-user",
        )

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CMK_FLOW_MODE", None)
            instructions = _build_instructions(store, "test-user")

        assert "Python uses HNSW" in instructions
        # Observation should not appear in recent context section
        lines = instructions.split("\n")
        in_recent = False
        for line in lines:
            if "Recent context" in line:
                in_recent = True
            if in_recent and "[observation]" in line:
                pytest.fail("observation found in recent context when flow mode off")

    def test_observations_shown_in_flow_mode(self, qdrant_db):
        from claude_memory_kit.server import _build_instructions

        store = self._make_store(qdrant_db)
        qdrant_db.insert_journal_raw(
            date="2026-02-16",
            gate=Gate.observation,
            content="[Bash] found 50 files in /src",
            user_id="test-user",
        )

        with patch.dict(os.environ, {"CMK_FLOW_MODE": "true"}):
            instructions = _build_instructions(store, "test-user")

        assert "Recent observations (flow mode)" in instructions
        assert "[Bash] found 50 files" in instructions

    def test_no_observation_section_when_flow_mode_off(self, qdrant_db):
        from claude_memory_kit.server import _build_instructions

        store = self._make_store(qdrant_db)
        qdrant_db.insert_journal_raw(
            date="2026-02-16",
            gate=Gate.observation,
            content="[Bash] some output",
            user_id="test-user",
        )

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CMK_FLOW_MODE", None)
            instructions = _build_instructions(store, "test-user")

        assert "Recent observations (flow mode)" not in instructions

    def test_no_observation_section_when_no_observations(self, qdrant_db):
        from claude_memory_kit.server import _build_instructions

        store = self._make_store(qdrant_db)
        qdrant_db.insert_journal_raw(
            date="2026-02-16",
            gate=Gate.epistemic,
            content="just a fact",
            user_id="test-user",
        )

        with patch.dict(os.environ, {"CMK_FLOW_MODE": "true"}):
            instructions = _build_instructions(store, "test-user")

        assert "Recent observations (flow mode)" not in instructions
