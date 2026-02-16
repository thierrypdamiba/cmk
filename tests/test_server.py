"""Comprehensive tests for the MCP server module (server.py).

Covers: _auto_gate, _extract_person_project, _build_instructions,
        TOOL_DEFS, LEGACY_ALIASES, _dispatch, create_server.
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from claude_memory_kit.server import (
    LEGACY_ALIASES,
    TOOL_DEFS,
    _auto_gate,
    _build_instructions,
    _dispatch,
    _extract_person_project,
    create_server,
)
from claude_memory_kit.types import Gate, IdentityCard, JournalEntry


# ---------------------------------------------------------------------------
# _auto_gate
# ---------------------------------------------------------------------------

class TestAutoGate:
    """Tests for the keyword-based gate classifier."""

    # -- promissory --

    def test_promissory_i_will(self):
        assert _auto_gate("I will finish the report tomorrow") == "promissory"

    def test_promissory_ill(self):
        assert _auto_gate("I'll send the invoice Monday") == "promissory"

    def test_promissory_follow_up(self):
        assert _auto_gate("Need to follow up with the client") == "promissory"

    def test_promissory_follow_up_hyphen(self):
        assert _auto_gate("Schedule a follow-up meeting") == "promissory"

    def test_promissory_deadline(self):
        assert _auto_gate("The deadline is next Friday") == "promissory"

    def test_promissory_todo(self):
        assert _auto_gate("todo: refactor the auth module") == "promissory"

    def test_promissory_by_tomorrow(self):
        assert _auto_gate("Need this done by tomorrow") == "promissory"

    def test_promissory_remind_me(self):
        assert _auto_gate("Remind me to call the dentist") == "promissory"

    def test_promissory_i_should(self):
        assert _auto_gate("I should upgrade the dependencies") == "promissory"

    def test_promissory_committed_to(self):
        assert _auto_gate("I committed to delivering the prototype") == "promissory"

    def test_promissory_agreed_to(self):
        assert _auto_gate("We agreed to use PostgreSQL") == "promissory"

    def test_promissory_dont_forget(self):
        assert _auto_gate("Don't forget to deploy the hotfix") == "promissory"

    def test_promissory_i_promised(self):
        assert _auto_gate("I promised to review the PR") == "promissory"

    def test_promissory_i_need_to(self):
        assert _auto_gate("I need to rewrite the tests") == "promissory"

    def test_promissory_by_monday(self):
        assert _auto_gate("Ship the feature by monday") == "promissory"

    # -- correction --

    def test_correction_actually(self):
        assert _auto_gate("Actually, the API uses REST not GraphQL") == "correction"

    def test_correction_i_was_wrong(self):
        assert _auto_gate("I was wrong about the schema design") == "correction"

    def test_correction_turns_out(self):
        assert _auto_gate("Turns out the bug was a race condition") == "correction"

    def test_correction_no_longer(self):
        assert _auto_gate("That endpoint is no longer supported") == "correction"

    def test_correction_changed_my_mind(self):
        assert _auto_gate("I changed my mind on the approach") == "correction"

    def test_correction_instead_of(self):
        assert _auto_gate("We should use Redis instead of Memcached") == "correction"

    def test_correction_not_true(self):
        assert _auto_gate("That claim is not true") == "correction"

    def test_correction_updated(self):
        assert _auto_gate("The spec has been updated since last week") == "correction"

    def test_correction_contrary_to(self):
        assert _auto_gate("Contrary to what I said, the service is stateful") == "correction"

    def test_correction_rather_than(self):
        assert _auto_gate("Use gRPC rather than REST for this") == "correction"

    def test_correction_opposite(self):
        assert _auto_gate("The opposite is true for write-heavy workloads") == "correction"

    # -- behavioral --

    def test_behavioral_from_now_on(self):
        assert _auto_gate("From now on, use TypeScript for all new services") == "behavioral"

    def test_behavioral_prefer(self):
        assert _auto_gate("I prefer tabs over spaces") == "behavioral"

    def test_behavioral_always(self):
        assert _auto_gate("Always run the linter before committing") == "behavioral"

    def test_behavioral_never(self):
        assert _auto_gate("Never deploy on Fridays") == "behavioral"

    def test_behavioral_workflow(self):
        assert _auto_gate("My workflow involves squash merges") == "behavioral"

    def test_behavioral_habit(self):
        assert _auto_gate("I have a habit of writing tests first") == "behavioral"

    def test_behavioral_dont_like(self):
        assert _auto_gate("I don't like verbose commit messages") == "behavioral"

    def test_behavioral_preference(self):
        assert _auto_gate("My preference is dark mode everywhere") == "behavioral"

    def test_behavioral_wants_me_to(self):
        assert _auto_gate("The team wants me to write more docs") == "behavioral"

    def test_behavioral_annoyed_by(self):
        assert _auto_gate("I'm annoyed by flaky tests") == "behavioral"

    def test_behavioral_when_i(self):
        assert _auto_gate("When I review code I focus on readability") == "behavioral"

    def test_behavioral_likes_to(self):
        assert _auto_gate("She likes to pair program") == "behavioral"

    # -- relational (regex patterns) --

    def test_relational_he_is(self):
        assert _auto_gate("he is a senior engineer at Google") == "relational"

    def test_relational_she_works(self):
        assert _auto_gate("she works on the infrastructure team") == "relational"

    def test_relational_they_said(self):
        assert _auto_gate("they said the meeting went well") == "relational"

    def test_relational_person_works_at(self):
        assert _auto_gate("John works at Stripe") == "relational"

    def test_relational_person_is_a(self):
        assert _auto_gate("Sarah is a product manager") == "relational"

    # -- relational (keyword fallback) --

    def test_relational_works_at_keyword(self):
        assert _auto_gate("She currently works at Meta") == "relational"

    def test_relational_partner(self):
        assert _auto_gate("My partner also codes in Rust") == "relational"

    def test_relational_colleague(self):
        assert _auto_gate("That colleague handles the on-call rotation") == "relational"

    def test_relational_boss(self):
        assert _auto_gate("My boss approved the budget") == "relational"

    def test_relational_team_lead(self):
        assert _auto_gate("The team lead set the sprint goals") == "relational"

    def test_relational_family(self):
        assert _auto_gate("My family is visiting next week") == "relational"

    def test_relational_friend(self):
        assert _auto_gate("A friend recommended this library") == "relational"

    def test_relational_their_name(self):
        assert _auto_gate("Their name is Alex Chen") == "relational"

    def test_relational_relationship(self):
        assert _auto_gate("Our relationship with the vendor is good") == "relational"

    def test_relational_manager(self):
        assert _auto_gate("My manager wants a status update") == "relational"

    # -- epistemic (default) --

    def test_epistemic_plain_fact(self):
        assert _auto_gate("Python 3.12 supports pattern matching") == "epistemic"

    def test_epistemic_learning(self):
        assert _auto_gate("The Qdrant vector database uses HNSW indexing") == "epistemic"

    def test_epistemic_neutral(self):
        assert _auto_gate("The server runs on port 8080") == "epistemic"

    def test_epistemic_empty_string(self):
        assert _auto_gate("") == "epistemic"

    def test_epistemic_random_text(self):
        assert _auto_gate("hello world foo bar baz") == "epistemic"

    # -- case insensitivity --

    def test_case_insensitive_promissory(self):
        assert _auto_gate("I WILL finish this task") == "promissory"

    def test_case_insensitive_correction(self):
        assert _auto_gate("ACTUALLY the design changed") == "correction"

    def test_case_insensitive_behavioral(self):
        assert _auto_gate("FROM NOW ON use Python 3.12") == "behavioral"

    # -- priority: promissory wins over correction if both match --

    def test_priority_promissory_over_correction(self):
        """Promissory check runs first, so it takes precedence."""
        assert _auto_gate("I will actually do it tomorrow") == "promissory"

    def test_priority_promissory_over_behavioral(self):
        assert _auto_gate("I will always deploy on Tuesdays") == "promissory"

    def test_priority_correction_over_behavioral(self):
        assert _auto_gate("Actually, from now on use Python") == "correction"


# ---------------------------------------------------------------------------
# _extract_person_project
# ---------------------------------------------------------------------------

class TestExtractPersonProject:
    """Tests for person/project extraction heuristics."""

    # -- person extraction --

    def test_person_after_about(self):
        person, _ = _extract_person_project("I learned about Alice today")
        assert person == "Alice"

    def test_person_after_for(self):
        person, _ = _extract_person_project("Built this for Bob Smith")
        assert person == "Bob Smith"

    def test_person_after_with(self):
        person, _ = _extract_person_project("Working with Carlos on the API")
        assert person == "Carlos"

    def test_person_after_from(self):
        person, _ = _extract_person_project("Got feedback from Diana")
        assert person == "Diana"

    def test_person_none_when_lowercase(self):
        """Lowercase words after keywords are not treated as names."""
        person, _ = _extract_person_project("I talked about something else")
        assert person is None

    def test_person_skips_month(self):
        person, _ = _extract_person_project("Meeting scheduled for January")
        assert person is None

    def test_person_skips_day(self):
        person, _ = _extract_person_project("Available from Monday onwards")
        assert person is None

    def test_person_skips_the(self):
        person, _ = _extract_person_project("Read about The topic briefly")
        assert person is None

    def test_person_skips_this(self):
        person, _ = _extract_person_project("Learned about This topic")
        assert person is None

    def test_person_skips_february(self):
        person, _ = _extract_person_project("Starting from February onward")
        assert person is None

    def test_person_skips_sunday(self):
        person, _ = _extract_person_project("Meeting with Sunday as the deadline")
        assert person is None

    def test_person_two_word_name(self):
        person, _ = _extract_person_project("Pairing with Alice Johnson on tasks")
        assert person == "Alice Johnson"

    def test_person_none_no_keyword(self):
        person, _ = _extract_person_project("Alice is great")
        assert person is None

    # -- project extraction --

    def test_project_after_project(self):
        _, project = _extract_person_project("project acme-api is progressing")
        assert project == "acme-api"

    def test_project_after_repo(self):
        _, project = _extract_person_project("Pushed to repo claude-memory")
        assert project == "claude-memory"

    def test_project_after_app(self):
        _, project = _extract_person_project("Deploying app dashboard-v2")
        assert project == "dashboard-v2"

    def test_project_after_codebase(self):
        _, project = _extract_person_project("Refactoring codebase monolith")
        assert project == "monolith"

    def test_project_after_working_on(self):
        _, project = _extract_person_project("Currently working on chess-rag")
        assert project == "chess-rag"

    def test_project_quoted(self):
        _, project = _extract_person_project('the project "my-service" is ready')
        assert project == "my-service"

    def test_project_strips_trailing_punctuation(self):
        _, project = _extract_person_project("project acme-api.")
        assert project == "acme-api"

    def test_project_none_no_keyword(self):
        _, project = _extract_person_project("I'm building something cool")
        assert project is None

    # -- both person and project --

    def test_both_person_and_project(self):
        person, project = _extract_person_project(
            "Working with Alice on project acme"
        )
        assert person == "Alice"
        assert project == "acme"

    # -- neither --

    def test_neither_person_nor_project(self):
        person, project = _extract_person_project("just a plain sentence")
        assert person is None
        assert project is None

    def test_empty_string(self):
        person, project = _extract_person_project("")
        assert person is None
        assert project is None

    # -- case sensitivity of project keyword --

    def test_project_case_insensitive(self):
        _, project = _extract_person_project("PROJECT mega-app is live now")
        assert project == "mega-app"


# ---------------------------------------------------------------------------
# _build_instructions
# ---------------------------------------------------------------------------

class TestBuildInstructions:
    """Tests for dynamic instruction builder."""

    def _make_store(self, qdrant_db):
        """Create a minimal Store-like object backed by a real QdrantStore."""
        store = MagicMock()
        store.qdrant = qdrant_db
        return store

    def test_base_instructions_always_present(self, qdrant_db):
        store = self._make_store(qdrant_db)
        instructions = _build_instructions(store, "test-user")
        assert "Claude Memory Kit" in instructions
        assert "4 tools: remember_this, recall_memories, forget_memory, save_checkpoint." in instructions

    def test_includes_identity_card(self, qdrant_db):
        store = self._make_store(qdrant_db)
        card = IdentityCard(
            person="Thierry",
            project="claude-memory",
            content="I work with Thierry. He builds memory tools.",
            last_updated=datetime.now(timezone.utc),
        )
        qdrant_db.set_identity(card, user_id="test-user")

        instructions = _build_instructions(store, "test-user")
        assert "Who I am" in instructions
        assert "Thierry" in instructions
        assert "memory tools" in instructions

    def test_no_identity_section_when_missing(self, qdrant_db):
        store = self._make_store(qdrant_db)
        instructions = _build_instructions(store, "test-user")
        assert "Who I am" not in instructions

    def test_includes_recent_journal(self, qdrant_db):
        store = self._make_store(qdrant_db)
        entry = JournalEntry(
            timestamp=datetime.now(timezone.utc),
            gate=Gate.epistemic,
            content="Qdrant uses HNSW indexing for vector search.",
            person=None,
            project=None,
        )
        qdrant_db.insert_journal(entry, user_id="test-user")

        instructions = _build_instructions(store, "test-user")
        assert "Recent context" in instructions
        assert "HNSW" in instructions

    def test_no_recent_section_when_empty(self, qdrant_db):
        store = self._make_store(qdrant_db)
        instructions = _build_instructions(store, "test-user")
        assert "Recent context" not in instructions

    def test_journal_entries_capped_at_8(self, qdrant_db):
        store = self._make_store(qdrant_db)
        for i in range(15):
            entry = JournalEntry(
                timestamp=datetime.now(timezone.utc),
                gate=Gate.epistemic,
                content=f"Entry number {i}",
            )
            qdrant_db.insert_journal(entry, user_id="test-user")

        instructions = _build_instructions(store, "test-user")
        # Should have at most 8 journal lines in the output
        journal_lines = [
            line for line in instructions.split("\n")
            if line.startswith("[epistemic]")
        ]
        assert len(journal_lines) <= 8

    def test_instructions_include_proactive_saving_rules(self, qdrant_db):
        store = self._make_store(qdrant_db)
        instructions = _build_instructions(store, "test-user")
        assert "PROACTIVE SAVING" in instructions
        assert "Do NOT save" in instructions

    def test_includes_checkpoint_when_present(self, qdrant_db):
        store = self._make_store(qdrant_db)
        # Insert a checkpoint via insert_journal_raw
        qdrant_db.insert_journal_raw(
            date="2026-02-15",
            gate=Gate.checkpoint,
            content="Working on checkpoint tests. Next: coverage.",
            user_id="test-user",
        )

        instructions = _build_instructions(store, "test-user")
        assert "Last session checkpoint" in instructions
        assert "Working on checkpoint tests" in instructions

    def test_no_checkpoint_section_when_missing(self, qdrant_db):
        store = self._make_store(qdrant_db)
        instructions = _build_instructions(store, "test-user")
        assert "Last session checkpoint" not in instructions

    def test_checkpoints_excluded_from_recent_context(self, qdrant_db):
        store = self._make_store(qdrant_db)
        # Insert a normal journal entry and a checkpoint
        entry = JournalEntry(
            timestamp=datetime.now(timezone.utc),
            gate=Gate.epistemic,
            content="Regular journal entry",
        )
        qdrant_db.insert_journal(entry, user_id="test-user")
        qdrant_db.insert_journal_raw(
            date="2026-02-15",
            gate=Gate.checkpoint,
            content="Checkpoint content here",
            user_id="test-user",
        )

        instructions = _build_instructions(store, "test-user")
        assert "Regular journal entry" in instructions
        # Checkpoint should appear in its own section, not in recent context
        lines = instructions.split("\n")
        recent_section = False
        for line in lines:
            if "Recent context" in line:
                recent_section = True
            if recent_section and "checkpoint" in line.lower():
                # Should not have [checkpoint] in recent context section
                assert not line.startswith("[checkpoint]")


# ---------------------------------------------------------------------------
# TOOL_DEFS and LEGACY_ALIASES
# ---------------------------------------------------------------------------

class TestToolDefs:
    """Tests for static tool definitions."""

    def test_exactly_four_tools(self):
        assert len(TOOL_DEFS) == 4

    def test_tool_names(self):
        names = {t.name for t in TOOL_DEFS}
        assert names == {"remember_this", "recall_memories", "forget_memory", "save_checkpoint"}

    def test_remember_this_requires_text(self):
        tool = next(t for t in TOOL_DEFS if t.name == "remember_this")
        assert "text" in tool.inputSchema["required"]

    def test_recall_memories_requires_query(self):
        tool = next(t for t in TOOL_DEFS if t.name == "recall_memories")
        assert "query" in tool.inputSchema["required"]

    def test_forget_memory_requires_id_and_reason(self):
        tool = next(t for t in TOOL_DEFS if t.name == "forget_memory")
        assert "id" in tool.inputSchema["required"]
        assert "reason" in tool.inputSchema["required"]

    def test_remember_this_has_optional_person_project(self):
        tool = next(t for t in TOOL_DEFS if t.name == "remember_this")
        props = tool.inputSchema["properties"]
        assert "person" in props
        assert "project" in props
        assert "person" not in tool.inputSchema["required"]
        assert "project" not in tool.inputSchema["required"]


class TestLegacyAliases:
    """Tests for legacy tool name mappings."""

    def test_save_maps_to_remember_this(self):
        assert LEGACY_ALIASES["save"] == "remember_this"

    def test_remember_maps_to_remember_this(self):
        assert LEGACY_ALIASES["remember"] == "remember_this"

    def test_search_maps_to_recall_memories(self):
        assert LEGACY_ALIASES["search"] == "recall_memories"

    def test_recall_maps_to_recall_memories(self):
        assert LEGACY_ALIASES["recall"] == "recall_memories"

    def test_prime_maps_to_recall_memories(self):
        assert LEGACY_ALIASES["prime"] == "recall_memories"

    def test_forget_maps_to_forget_memory(self):
        assert LEGACY_ALIASES["forget"] == "forget_memory"

    def test_checkpoint_maps_to_save_checkpoint(self):
        assert LEGACY_ALIASES["checkpoint"] == "save_checkpoint"

    def test_correct_alias_count(self):
        assert len(LEGACY_ALIASES) == 7


# ---------------------------------------------------------------------------
# _dispatch
# ---------------------------------------------------------------------------

class TestDispatch:
    """Tests for the tool dispatch function."""

    @pytest.fixture
    def mock_store(self):
        store = MagicMock()
        store.qdrant = MagicMock()
        return store

    @pytest.fixture
    def counters(self):
        return {"save": 0, "checkpoint": 0}

    @pytest.mark.asyncio
    async def test_remember_this_calls_do_remember(self, mock_store, counters):
        with patch(
            "claude_memory_kit.server.do_remember",
            new_callable=AsyncMock,
            return_value="Remembered [epistemic]: test (id: mem_001)",
        ) as mock_remember:
            result = await _dispatch(
                mock_store, "remember_this",
                {"text": "Python uses indentation for blocks"},
                "user1", counters,
            )
            mock_remember.assert_awaited_once()
            assert "Remembered" in result

    @pytest.mark.asyncio
    async def test_remember_this_auto_gates_promissory(self, mock_store, counters):
        with patch(
            "claude_memory_kit.server.do_remember",
            new_callable=AsyncMock,
            return_value="ok",
        ) as mock_remember:
            await _dispatch(
                mock_store, "remember_this",
                {"text": "I will finish the feature by Friday"},
                "user1", counters,
            )
            call_args = mock_remember.call_args
            assert call_args[0][2] == "promissory"

    @pytest.mark.asyncio
    async def test_remember_this_auto_gates_correction(self, mock_store, counters):
        with patch(
            "claude_memory_kit.server.do_remember",
            new_callable=AsyncMock,
            return_value="ok",
        ) as mock_remember:
            await _dispatch(
                mock_store, "remember_this",
                {"text": "Actually the service uses gRPC"},
                "user1", counters,
            )
            call_args = mock_remember.call_args
            assert call_args[0][2] == "correction"

    @pytest.mark.asyncio
    async def test_remember_this_auto_gates_behavioral(self, mock_store, counters):
        with patch(
            "claude_memory_kit.server.do_remember",
            new_callable=AsyncMock,
            return_value="ok",
        ) as mock_remember:
            await _dispatch(
                mock_store, "remember_this",
                {"text": "From now on use pytest for all tests"},
                "user1", counters,
            )
            call_args = mock_remember.call_args
            assert call_args[0][2] == "behavioral"

    @pytest.mark.asyncio
    async def test_remember_this_auto_detects_person(self, mock_store, counters):
        with patch(
            "claude_memory_kit.server.do_remember",
            new_callable=AsyncMock,
            return_value="ok",
        ) as mock_remember:
            await _dispatch(
                mock_store, "remember_this",
                {"text": "Got feedback from Alice on the design"},
                "user1", counters,
            )
            call_args = mock_remember.call_args
            assert call_args[0][3] == "Alice"

    @pytest.mark.asyncio
    async def test_remember_this_auto_detects_project(self, mock_store, counters):
        with patch(
            "claude_memory_kit.server.do_remember",
            new_callable=AsyncMock,
            return_value="ok",
        ) as mock_remember:
            await _dispatch(
                mock_store, "remember_this",
                {"text": "Deployed project acme-api to staging"},
                "user1", counters,
            )
            call_args = mock_remember.call_args
            assert call_args[0][4] == "acme-api"

    @pytest.mark.asyncio
    async def test_remember_this_explicit_person_overrides_auto(self, mock_store, counters):
        with patch(
            "claude_memory_kit.server.do_remember",
            new_callable=AsyncMock,
            return_value="ok",
        ) as mock_remember:
            await _dispatch(
                mock_store, "remember_this",
                {"text": "Got feedback from Alice", "person": "Bob"},
                "user1", counters,
            )
            call_args = mock_remember.call_args
            assert call_args[0][3] == "Bob"

    @pytest.mark.asyncio
    async def test_remember_this_explicit_project_overrides_auto(self, mock_store, counters):
        with patch(
            "claude_memory_kit.server.do_remember",
            new_callable=AsyncMock,
            return_value="ok",
        ) as mock_remember:
            await _dispatch(
                mock_store, "remember_this",
                {"text": "Working on project foo", "project": "bar"},
                "user1", counters,
            )
            call_args = mock_remember.call_args
            assert call_args[0][4] == "bar"

    @pytest.mark.asyncio
    async def test_remember_this_increments_save_count(self, mock_store, counters):
        with patch(
            "claude_memory_kit.server.do_remember",
            new_callable=AsyncMock,
            return_value="ok",
        ):
            await _dispatch(
                mock_store, "remember_this",
                {"text": "some fact"},
                "user1", counters,
            )
            assert counters["save"] == 1

    @pytest.mark.asyncio
    async def test_remember_this_triggers_auto_reflect_at_threshold(self, mock_store, counters):
        import claude_memory_kit.server as server_mod

        counters["save"] = server_mod._REFLECT_EVERY - 1
        with patch(
            "claude_memory_kit.server.do_remember",
            new_callable=AsyncMock,
            return_value="ok",
        ), patch(
            "claude_memory_kit.server.do_reflect",
            new_callable=AsyncMock,
            return_value="reflected",
        ) as mock_reflect:
            await _dispatch(
                mock_store, "remember_this",
                {"text": "trigger reflect"},
                "user1", counters,
            )
            mock_reflect.assert_awaited_once()
            assert counters["save"] == 0

    @pytest.mark.asyncio
    async def test_remember_this_auto_reflect_failure_does_not_crash(self, mock_store, counters):
        import claude_memory_kit.server as server_mod

        counters["save"] = server_mod._REFLECT_EVERY - 1
        with patch(
            "claude_memory_kit.server.do_remember",
            new_callable=AsyncMock,
            return_value="ok",
        ), patch(
            "claude_memory_kit.server.do_reflect",
            new_callable=AsyncMock,
            side_effect=RuntimeError("reflect boom"),
        ):
            result = await _dispatch(
                mock_store, "remember_this",
                {"text": "trigger reflect that fails"},
                "user1", counters,
            )
            assert result == "ok"
            assert counters["save"] == 0

    @pytest.mark.asyncio
    async def test_remember_this_triggers_auto_checkpoint_at_threshold(self, mock_store, counters):
        from claude_memory_kit.tools.checkpoint import CHECKPOINT_EVERY
        counters["checkpoint"] = CHECKPOINT_EVERY - 1
        with patch(
            "claude_memory_kit.server.do_remember",
            new_callable=AsyncMock,
            return_value="ok",
        ):
            result = await _dispatch(
                mock_store, "remember_this",
                {"text": "trigger checkpoint"},
                "user1", counters,
            )
            assert "[auto-checkpoint]" in result
            assert counters["checkpoint"] == 0

    @pytest.mark.asyncio
    async def test_recall_memories_calls_do_recall(self, mock_store, counters):
        with patch(
            "claude_memory_kit.server.do_recall",
            new_callable=AsyncMock,
            return_value="Found 2 memories:\n...",
        ) as mock_recall:
            result = await _dispatch(
                mock_store, "recall_memories",
                {"query": "python best practices"},
                "user1", counters,
            )
            mock_recall.assert_awaited_once_with(
                mock_store, "python best practices", user_id="user1",
                team_id=None,
            )
            assert "Found" in result

    @pytest.mark.asyncio
    async def test_forget_memory_calls_do_forget(self, mock_store, counters):
        with patch(
            "claude_memory_kit.server.do_forget",
            new_callable=AsyncMock,
            return_value="Forgotten: mem_001 (reason: outdated).",
        ) as mock_forget:
            result = await _dispatch(
                mock_store, "forget_memory",
                {"id": "mem_001", "reason": "outdated"},
                "user1", counters,
            )
            mock_forget.assert_awaited_once_with(
                mock_store, "mem_001", "outdated", user_id="user1",
                team_id=None,
            )
            assert "Forgotten" in result

    @pytest.mark.asyncio
    async def test_legacy_identity_dispatch(self, mock_store, counters):
        with patch(
            "claude_memory_kit.server.do_identity",
            new_callable=AsyncMock,
            return_value="Identity card loaded.",
        ) as mock_id:
            result = await _dispatch(
                mock_store, "identity",
                {"onboard_response": "Thierry"},
                "user1", counters,
            )
            mock_id.assert_awaited_once_with(
                mock_store, "Thierry", user_id="user1",
            )
            assert "Identity" in result

    @pytest.mark.asyncio
    async def test_legacy_identity_with_none_response(self, mock_store, counters):
        with patch(
            "claude_memory_kit.server.do_identity",
            new_callable=AsyncMock,
            return_value="Cold start.",
        ) as mock_id:
            result = await _dispatch(
                mock_store, "identity",
                {},
                "user1", counters,
            )
            mock_id.assert_awaited_once_with(
                mock_store, None, user_id="user1",
            )

    @pytest.mark.asyncio
    async def test_legacy_reflect_dispatch(self, mock_store, counters):
        with patch(
            "claude_memory_kit.server.do_reflect",
            new_callable=AsyncMock,
            return_value="Reflection complete.",
        ) as mock_reflect:
            result = await _dispatch(
                mock_store, "reflect",
                {},
                "user1", counters,
            )
            mock_reflect.assert_awaited_once_with(
                mock_store, user_id="user1",
            )
            assert "Reflection" in result

    @pytest.mark.asyncio
    async def test_legacy_auto_extract_dispatch(self, mock_store, counters):
        with patch(
            "claude_memory_kit.server.do_auto_extract",
            new_callable=AsyncMock,
            return_value="Auto-extracted 3 memories.",
        ) as mock_extract:
            result = await _dispatch(
                mock_store, "auto_extract",
                {"transcript": "User said they prefer dark mode."},
                "user1", counters,
            )
            mock_extract.assert_awaited_once_with(
                mock_store, "User said they prefer dark mode.", user_id="user1",
            )
            assert "extracted" in result

    @pytest.mark.asyncio
    async def test_save_checkpoint_calls_do_checkpoint(self, mock_store, counters):
        with patch(
            "claude_memory_kit.server.do_checkpoint",
            new_callable=AsyncMock,
            return_value="Checkpoint saved. This will be loaded at the start of your next session.",
        ) as mock_ckpt:
            result = await _dispatch(
                mock_store, "save_checkpoint",
                {"summary": "Working on tests. Decided to use pytest."},
                "user1", counters,
            )
            mock_ckpt.assert_awaited_once_with(
                mock_store, "Working on tests. Decided to use pytest.", user_id="user1",
            )
            assert "Checkpoint saved" in result

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error(self, mock_store, counters):
        result = await _dispatch(
            mock_store, "nonexistent_tool",
            {},
            "user1", counters,
        )
        assert result == "Unknown tool: nonexistent_tool"

    @pytest.mark.asyncio
    async def test_unknown_tool_with_args_returns_error(self, mock_store, counters):
        result = await _dispatch(
            mock_store, "foobar",
            {"x": 1, "y": 2},
            "user1", counters,
        )
        assert "Unknown tool: foobar" in result

    @pytest.mark.asyncio
    async def test_remember_this_auto_extracts_person_project(self, mock_store, counters):
        """When neither person nor project is given, auto-extraction runs."""
        with patch(
            "claude_memory_kit.server.do_remember",
            new_callable=AsyncMock,
            return_value="ok",
        ) as mock_remember:
            await _dispatch(
                mock_store, "remember_this",
                {"text": "Working with Eve on project zeta"},
                "user1", counters,
            )
            call_args = mock_remember.call_args
            assert call_args[0][3] == "Eve"
            assert call_args[0][4] == "zeta"

    @pytest.mark.asyncio
    async def test_remember_this_passes_user_id(self, mock_store, counters):
        with patch(
            "claude_memory_kit.server.do_remember",
            new_callable=AsyncMock,
            return_value="ok",
        ) as mock_remember:
            await _dispatch(
                mock_store, "remember_this",
                {"text": "a fact"},
                "user42", counters,
            )
            call_kwargs = mock_remember.call_args[1]
            assert call_kwargs["user_id"] == "user42"


# ---------------------------------------------------------------------------
# create_server
# ---------------------------------------------------------------------------

class TestCreateServer:
    """Tests for the create_server factory."""

    def _mock_store_instance(self):
        """Create a MagicMock Store whose qdrant methods return sane defaults."""
        mock_store_inst = MagicMock()
        mock_store_inst.qdrant.get_identity.return_value = None
        mock_store_inst.qdrant.recent_journal.return_value = []
        mock_store_inst.qdrant.latest_checkpoint.return_value = None
        return mock_store_inst

    @patch("claude_memory_kit.server.get_user_id", return_value="test-user")
    @patch("claude_memory_kit.server.get_store_path")
    @patch("claude_memory_kit.server.Store")
    def test_returns_server_instance(self, MockStore, mock_path, mock_uid, tmp_path):
        mock_path.return_value = str(tmp_path / "store")
        MockStore.return_value = self._mock_store_instance()

        from mcp.server import Server
        server = create_server()
        assert isinstance(server, Server)

    @patch("claude_memory_kit.server.get_user_id", return_value="test-user")
    @patch("claude_memory_kit.server.get_store_path")
    @patch("claude_memory_kit.server.Store")
    def test_calls_migrate_and_ensure_collection(self, MockStore, mock_path, mock_uid, tmp_path):
        mock_path.return_value = str(tmp_path / "store")
        mock_store_inst = self._mock_store_instance()
        MockStore.return_value = mock_store_inst

        create_server()

        mock_store_inst.auth_db.migrate.assert_called_once()
        mock_store_inst.qdrant.ensure_collection.assert_called_once()

    @patch("claude_memory_kit.server.get_user_id", return_value="test-user")
    @patch("claude_memory_kit.server.get_store_path")
    @patch("claude_memory_kit.server.Store")
    def test_server_has_correct_name(self, MockStore, mock_path, mock_uid, tmp_path):
        mock_path.return_value = str(tmp_path / "store")
        MockStore.return_value = self._mock_store_instance()

        server = create_server()
        assert server.name == "claude-memory-kit"

    @pytest.mark.asyncio
    @patch("claude_memory_kit.server.get_user_id", return_value="test-user")
    @patch("claude_memory_kit.server.get_store_path")
    @patch("claude_memory_kit.server.Store")
    async def test_list_tools_handler(self, MockStore, mock_path, mock_uid, tmp_path):
        mock_path.return_value = str(tmp_path / "store")
        MockStore.return_value = self._mock_store_instance()

        server = create_server()
        # The list_tools handler is registered on the server
        handlers = server.request_handlers
        from mcp.types import ListToolsRequest
        handler = handlers.get(ListToolsRequest)
        assert handler is not None
        result = await handler(ListToolsRequest(method="tools/list"))
        assert len(result.root.tools) == 4

    @pytest.mark.asyncio
    @patch("claude_memory_kit.server.get_user_id", return_value="test-user")
    @patch("claude_memory_kit.server.get_store_path")
    @patch("claude_memory_kit.server.Store")
    async def test_call_tool_handler_dispatches(self, MockStore, mock_path, mock_uid, tmp_path):
        mock_path.return_value = str(tmp_path / "store")
        MockStore.return_value = self._mock_store_instance()

        server = create_server()
        from mcp.types import CallToolRequest
        handler = server.request_handlers.get(CallToolRequest)
        assert handler is not None
        with patch(
            "claude_memory_kit.server.do_recall",
            new_callable=AsyncMock,
            return_value="Found 0 memories.",
        ):
            result = await handler(
                CallToolRequest(
                    method="tools/call",
                    params={"name": "search", "arguments": {"query": "test"}},
                )
            )
            assert len(result.root.content) == 1
            assert "Found" in result.root.content[0].text

    @pytest.mark.asyncio
    @patch("claude_memory_kit.server.get_user_id", return_value="test-user")
    @patch("claude_memory_kit.server.get_store_path")
    @patch("claude_memory_kit.server.Store")
    async def test_call_tool_handler_catches_exceptions(self, MockStore, mock_path, mock_uid, tmp_path):
        mock_path.return_value = str(tmp_path / "store")
        MockStore.return_value = self._mock_store_instance()

        server = create_server()
        from mcp.types import CallToolRequest
        handler = server.request_handlers.get(CallToolRequest)
        assert handler is not None
        with patch(
            "claude_memory_kit.server.do_recall",
            new_callable=AsyncMock,
            side_effect=RuntimeError("boom"),
        ):
            result = await handler(
                CallToolRequest(
                    method="tools/call",
                    params={"name": "search", "arguments": {"query": "test"}},
                )
            )
            assert "Error" in result.root.content[0].text
