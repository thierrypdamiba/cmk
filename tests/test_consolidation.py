"""Tests for consolidation: decay scoring and journal digest."""

import math
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from claude_memory_kit.types import Memory, Gate, DecayClass
from claude_memory_kit.consolidation.decay import (
    compute_decay_score,
    _recency,
    _frequency,
    is_fading,
)
from claude_memory_kit.consolidation.digest import consolidate_journals


# ---------------------------------------------------------------------------
# decay.py tests
# ---------------------------------------------------------------------------


class TestRecency:
    """Tests for _recency helper."""

    def test_fresh_memory_recency_near_one(self, make_memory):
        mem = make_memory(gate=Gate.behavioral)
        score = _recency(mem)
        assert 0.99 <= score <= 1.0

    def test_never_decay_returns_one(self, make_memory):
        mem = make_memory(gate=Gate.promissory)
        assert mem.decay_class == DecayClass.never
        assert _recency(mem) == 1.0

    def test_old_memory_recency_decreases(self, make_memory):
        mem = make_memory(gate=Gate.behavioral)  # fast, 30d half-life
        old = mem.model_copy(
            update={"last_accessed": datetime.now(timezone.utc) - timedelta(days=30)}
        )
        score = _recency(old)
        # After exactly one half-life, should be ~0.5
        assert 0.45 <= score <= 0.55

    def test_very_old_memory_recency_near_zero(self, make_memory):
        mem = make_memory(gate=Gate.behavioral)  # 30d half-life
        ancient = mem.model_copy(
            update={"last_accessed": datetime.now(timezone.utc) - timedelta(days=300)}
        )
        score = _recency(ancient)
        assert score < 0.01

    def test_slow_decay_retains_longer(self, make_memory):
        mem = make_memory(gate=Gate.relational)  # slow, 180d half-life
        aged = mem.model_copy(
            update={"last_accessed": datetime.now(timezone.utc) - timedelta(days=90)}
        )
        score = _recency(aged)
        # 90 days into a 180d half-life should be ~0.707
        assert 0.65 <= score <= 0.78


class TestFrequency:
    """Tests for _frequency helper."""

    def test_single_access_gives_one(self, make_memory):
        mem = make_memory(access_count=1)
        assert _frequency(mem) == pytest.approx(1.0)

    def test_zero_access_gives_zero(self, make_memory):
        """Access count of 0: log(0+1)/log(2) = 0."""
        mem = make_memory(access_count=0)
        assert _frequency(mem) == pytest.approx(0.0)

    def test_high_access_boosts_score(self, make_memory):
        mem = make_memory(access_count=15)
        score = _frequency(mem)
        assert score == pytest.approx(math.log(16) / math.log(2))
        assert score > 3.0

    def test_frequency_increases_with_access(self, make_memory):
        low = make_memory(access_count=2)
        high = make_memory(access_count=10)
        assert _frequency(high) > _frequency(low)


class TestComputeDecayScore:
    """Tests for compute_decay_score (recency * frequency)."""

    def test_fresh_single_access_score_near_one(self, make_memory):
        mem = make_memory(gate=Gate.epistemic, access_count=1)
        score = compute_decay_score(mem)
        assert 0.95 <= score <= 1.05

    def test_never_decay_high_access_always_high(self, make_memory):
        mem = make_memory(gate=Gate.promissory, access_count=10)
        score = compute_decay_score(mem)
        # recency = 1.0, frequency = log(11)/log(2) ~ 3.46
        assert score > 3.0

    def test_old_low_access_yields_low_score(self, make_memory):
        mem = make_memory(gate=Gate.behavioral, access_count=1)
        old = mem.model_copy(
            update={"last_accessed": datetime.now(timezone.utc) - timedelta(days=200)}
        )
        score = compute_decay_score(old)
        assert score < 0.05


class TestIsFading:
    """Tests for is_fading predicate."""

    def test_never_decay_never_fades(self, make_memory):
        mem = make_memory(gate=Gate.promissory)
        assert is_fading(mem) is False

    def test_never_decay_even_if_old(self, make_memory):
        mem = make_memory(gate=Gate.promissory, access_count=0)
        old = mem.model_copy(
            update={"last_accessed": datetime.now(timezone.utc) - timedelta(days=9999)}
        )
        assert is_fading(old) is False

    def test_fresh_memory_not_fading(self, make_memory):
        mem = make_memory(gate=Gate.behavioral, access_count=1)
        assert is_fading(mem) is False

    def test_old_fast_decay_is_fading(self, make_memory):
        mem = make_memory(gate=Gate.behavioral, access_count=1)
        old = mem.model_copy(
            update={"last_accessed": datetime.now(timezone.utc) - timedelta(days=200)}
        )
        assert is_fading(old) is True

    def test_high_access_resists_fading(self, make_memory):
        """Even an old memory with many accesses may not be fading."""
        mem = make_memory(gate=Gate.behavioral, access_count=100)
        aged = mem.model_copy(
            update={"last_accessed": datetime.now(timezone.utc) - timedelta(days=60)}
        )
        # recency ~0.25, frequency ~log(101)/log(2) ~6.66, score ~1.66
        assert is_fading(aged) is False


# ---------------------------------------------------------------------------
# digest.py tests (uses mock db since consolidate_journals is duck-typed)
# ---------------------------------------------------------------------------


def _make_mock_db(stale_dates=None, entries_by_date=None):
    """Create a mock db object with journal methods."""
    db = MagicMock()
    db.stale_journal_dates.return_value = stale_dates or []

    def _journal_by_date(date, user_id="local"):
        if entries_by_date:
            return entries_by_date.get(date, [])
        return []

    db.journal_by_date.side_effect = _journal_by_date
    db.insert_journal_raw = MagicMock()
    db.archive_journal_date = MagicMock()
    return db


class TestConsolidateJournals:
    """Tests for consolidate_journals async function."""

    @pytest.mark.asyncio
    async def test_returns_none_when_no_stale_entries(self):
        db = _make_mock_db()
        result = await consolidate_journals(db, api_key="fake-key", user_id="local")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_entries_are_recent(self):
        db = _make_mock_db()  # no stale dates
        result = await consolidate_journals(db, api_key="fake-key", user_id="local")
        assert result is None

    @pytest.mark.asyncio
    async def test_consolidates_stale_entries(self):
        old_date = (datetime.now(timezone.utc) - timedelta(days=20)).strftime("%Y-%m-%d")
        entries = {
            old_date: [
                {"gate": "epistemic", "content": "old insight one"},
                {"gate": "relational", "content": "old relationship note"},
            ]
        }
        db = _make_mock_db(stale_dates=[old_date], entries_by_date=entries)

        with patch(
            "claude_memory_kit.extract._call_anthropic",
            new_callable=AsyncMock,
            return_value="This week I learned important things.",
        ):
            result = await consolidate_journals(db, api_key="fake-key", user_id="local")

        assert result is not None
        assert "Consolidated 1 weeks" in result

    @pytest.mark.asyncio
    async def test_digest_stored_as_journal_entry(self):
        old_date = (datetime.now(timezone.utc) - timedelta(days=20)).strftime("%Y-%m-%d")
        entries = {
            old_date: [{"gate": "behavioral", "content": "testing digest storage"}]
        }
        db = _make_mock_db(stale_dates=[old_date], entries_by_date=entries)

        with patch(
            "claude_memory_kit.extract._call_anthropic",
            new_callable=AsyncMock,
            return_value="Digest text here.",
        ):
            await consolidate_journals(db, api_key="fake-key", user_id="local")

        db.insert_journal_raw.assert_called_once()
        call_kwargs = db.insert_journal_raw.call_args
        assert "Digest text here." in call_kwargs.kwargs.get("content", call_kwargs.args[2] if len(call_kwargs.args) > 2 else "")

    @pytest.mark.asyncio
    async def test_original_entries_archived(self):
        old_date = (datetime.now(timezone.utc) - timedelta(days=20)).strftime("%Y-%m-%d")
        entries = {
            old_date: [{"gate": "epistemic", "content": "will be archived"}]
        }
        db = _make_mock_db(stale_dates=[old_date], entries_by_date=entries)

        with patch(
            "claude_memory_kit.extract._call_anthropic",
            new_callable=AsyncMock,
            return_value="Digest.",
        ):
            await consolidate_journals(db, api_key="fake-key", user_id="local")

        db.archive_journal_date.assert_called_once_with(old_date, user_id="local")

    @pytest.mark.asyncio
    async def test_multiple_weeks_consolidated_separately(self):
        # Two dates in different ISO weeks
        date_week1 = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
        date_week2 = (datetime.now(timezone.utc) - timedelta(days=40)).strftime("%Y-%m-%d")
        entries = {
            date_week1: [{"gate": "epistemic", "content": "week A note"}],
            date_week2: [{"gate": "behavioral", "content": "week B note"}],
        }
        db = _make_mock_db(
            stale_dates=[date_week1, date_week2],
            entries_by_date=entries,
        )

        with patch(
            "claude_memory_kit.extract._call_anthropic",
            new_callable=AsyncMock,
            return_value="Weekly summary.",
        ):
            result = await consolidate_journals(db, api_key="fake-key", user_id="local")

        assert result is not None
        assert "Consolidated" in result
        assert db.insert_journal_raw.call_count >= 1

    @pytest.mark.asyncio
    async def test_user_isolation(self):
        old_date = (datetime.now(timezone.utc) - timedelta(days=20)).strftime("%Y-%m-%d")
        entries = {
            old_date: [{"gate": "epistemic", "content": "user A data"}]
        }
        db = _make_mock_db(stale_dates=[old_date], entries_by_date=entries)

        with patch(
            "claude_memory_kit.extract._call_anthropic",
            new_callable=AsyncMock,
            return_value="User A digest.",
        ):
            result = await consolidate_journals(db, api_key="fake-key", user_id="user_a")

        assert result is not None
        db.stale_journal_dates.assert_called_with(max_age_days=14, user_id="user_a")
        db.archive_journal_date.assert_called_with(old_date, user_id="user_a")

    @pytest.mark.asyncio
    async def test_digest_date_key_is_iso_week(self):
        old_date = (datetime.now(timezone.utc) - timedelta(days=20)).strftime("%Y-%m-%d")
        entries = {
            old_date: [{"gate": "epistemic", "content": "week key test"}]
        }
        db = _make_mock_db(stale_dates=[old_date], entries_by_date=entries)

        with patch(
            "claude_memory_kit.extract._call_anthropic",
            new_callable=AsyncMock,
            return_value="Summary.",
        ):
            await consolidate_journals(db, api_key="fake-key", user_id="local")

        call_kwargs = db.insert_journal_raw.call_args
        # The date arg should be in ISO week format
        date_arg = call_kwargs.kwargs.get("date", call_kwargs.args[0] if call_kwargs.args else "")
        assert "-W" in date_arg

    @pytest.mark.asyncio
    async def test_empty_combined_entries_skipped(self):
        """If stale dates exist but journal_by_date returns empty, no digest."""
        old_date = (datetime.now(timezone.utc) - timedelta(days=20)).strftime("%Y-%m-%d")
        db = _make_mock_db(stale_dates=[old_date], entries_by_date={old_date: []})

        result = await consolidate_journals(db, api_key="fake-key", user_id="local")
        assert result is None
        db.insert_journal_raw.assert_not_called()
