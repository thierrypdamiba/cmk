"""Tests for SqliteStore (auth-only: users, API keys, teams)."""

import uuid
from datetime import datetime, timezone

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _uid() -> str:
    return f"u_{uuid.uuid4().hex[:8]}"


# ===========================================================================
# Migration
# ===========================================================================


class TestMigration:
    def test_migrate_creates_tables(self, db):
        tables = {
            r[0]
            for r in db.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        expected = {
            "memories", "journal", "identity", "edges",
            "relationships", "onboarding", "archive",
            "users", "api_keys", "rules", "memories_fts",
            "teams", "team_members",
        }
        assert expected.issubset(tables)

    def test_migrate_idempotent(self, db):
        """Running migrate() twice must not raise."""
        db.migrate()
        db.migrate()

    def test_fts_triggers_exist(self, db):
        triggers = {
            r[0]
            for r in db.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger'"
            ).fetchall()
        }
        assert {"memories_ai", "memories_ad", "memories_au"}.issubset(triggers)

    def test_indexes_exist(self, db):
        indexes = {
            r[0]
            for r in db.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()
        }
        assert "idx_memories_user" in indexes
        assert "idx_journal_user" in indexes
        assert "idx_rules_user" in indexes
        assert "idx_memories_user_sensitivity" in indexes
        assert "idx_team_members_user" in indexes

    def test_schema_version(self, db):
        row = db.conn.execute(
            "SELECT version FROM schema_version WHERE id = 1"
        ).fetchone()
        assert row[0] == 6


# ===========================================================================
# Users
# ===========================================================================


class TestUsers:
    def test_upsert_and_get_user(self, db):
        db.upsert_user("u1", email="u1@example.com", name="User One")
        user = db.get_user("u1")
        assert user is not None
        assert user["email"] == "u1@example.com"
        assert user["name"] == "User One"
        assert user["plan"] == "free"

    def test_get_user_nonexistent(self, db):
        assert db.get_user("ghost") is None

    def test_upsert_updates_last_seen(self, db):
        db.upsert_user("u1", email="a@b.com")
        first = db.get_user("u1")
        db.upsert_user("u1", name="Updated")
        second = db.get_user("u1")
        assert second["name"] == "Updated"
        assert second["last_seen"] >= first["last_seen"]

    def test_upsert_preserves_existing_email(self, db):
        db.upsert_user("u1", email="original@test.com")
        db.upsert_user("u1")  # no email passed
        user = db.get_user("u1")
        assert user["email"] == "original@test.com"


# ===========================================================================
# API Keys
# ===========================================================================


class TestAPIKeys:
    def test_insert_and_get_by_hash(self, db):
        db.insert_api_key("k1", "u1", "hash123", "cmk_", name="test key")
        got = db.get_api_key_by_hash("hash123")
        assert got is not None
        assert got["id"] == "k1"
        assert got["user_id"] == "u1"
        assert got["name"] == "test key"

    def test_get_by_hash_nonexistent(self, db):
        assert db.get_api_key_by_hash("no_such_hash") is None

    def test_get_by_hash_updates_last_used(self, db):
        db.insert_api_key("k1", "u1", "hash1", "cmk_")
        # First call updates the DB but returns the pre-update row
        db.get_api_key_by_hash("hash1")
        # Second call returns the row that was updated by the first call
        second = db.get_api_key_by_hash("hash1")
        assert second["last_used"] is not None

    def test_list_api_keys(self, db):
        db.insert_api_key("k1", "u1", "h1", "cmk_", name="key1")
        db.insert_api_key("k2", "u1", "h2", "cmk_", name="key2")
        db.insert_api_key("k3", "u2", "h3", "cmk_", name="other")
        keys = db.list_api_keys("u1")
        assert len(keys) == 2
        names = {k["name"] for k in keys}
        assert names == {"key1", "key2"}

    def test_revoke_api_key(self, db):
        db.insert_api_key("k1", "u1", "hash1", "cmk_")
        assert db.revoke_api_key("k1", "u1") is True
        # Revoked key should not be returned
        assert db.get_api_key_by_hash("hash1") is None

    def test_revoke_nonexistent_key(self, db):
        assert db.revoke_api_key("ghost", "u1") is False

    def test_revoke_wrong_user(self, db):
        db.insert_api_key("k1", "u1", "hash1", "cmk_")
        assert db.revoke_api_key("k1", "u2") is False
        # Key should still work
        assert db.get_api_key_by_hash("hash1") is not None


# ===========================================================================
# Teams
# ===========================================================================


class TestTeams:
    def test_create_team(self, db):
        team = db.create_team("t1", "Alpha Team", "user_a")
        assert team["id"] == "t1"
        assert team["name"] == "Alpha Team"
        assert team["created_by"] == "user_a"
        assert "created" in team

    def test_create_team_adds_owner(self, db):
        db.create_team("t1", "Alpha", "user_a")
        role = db.get_member_role("t1", "user_a")
        assert role == "owner"

    def test_get_team(self, db):
        db.create_team("t1", "Alpha", "user_a")
        team = db.get_team("t1")
        assert team is not None
        assert team["name"] == "Alpha"

    def test_get_team_nonexistent(self, db):
        assert db.get_team("ghost") is None

    def test_list_user_teams(self, db):
        db.create_team("t1", "Alpha", "user_a")
        db.create_team("t2", "Beta", "user_a")
        db.create_team("t3", "Gamma", "user_b")
        teams = db.list_user_teams("user_a")
        assert len(teams) == 2
        names = {t["name"] for t in teams}
        assert names == {"Alpha", "Beta"}

    def test_list_user_teams_empty(self, db):
        assert db.list_user_teams("nobody") == []

    def test_add_team_member(self, db):
        db.create_team("t1", "Alpha", "user_a")
        db.add_team_member("t1", "user_b", role="member")
        assert db.is_team_member("t1", "user_b") is True
        assert db.get_member_role("t1", "user_b") == "member"

    def test_add_team_member_upsert_role(self, db):
        db.create_team("t1", "Alpha", "user_a")
        db.add_team_member("t1", "user_b", role="member")
        db.add_team_member("t1", "user_b", role="admin")
        assert db.get_member_role("t1", "user_b") == "admin"

    def test_remove_team_member(self, db):
        db.create_team("t1", "Alpha", "user_a")
        db.add_team_member("t1", "user_b")
        assert db.remove_team_member("t1", "user_b") is True
        assert db.is_team_member("t1", "user_b") is False

    def test_remove_team_member_nonexistent(self, db):
        db.create_team("t1", "Alpha", "user_a")
        assert db.remove_team_member("t1", "ghost") is False

    def test_list_team_members(self, db):
        db.upsert_user("user_a", email="a@test.com", name="Alice")
        db.upsert_user("user_b", email="b@test.com", name="Bob")
        db.create_team("t1", "Alpha", "user_a")
        db.add_team_member("t1", "user_b", role="member")
        members = db.list_team_members("t1")
        assert len(members) == 2
        roles = {m["user_id"]: m["role"] for m in members}
        assert roles["user_a"] == "owner"
        assert roles["user_b"] == "member"

    def test_list_team_members_includes_user_info(self, db):
        db.upsert_user("user_a", email="a@test.com", name="Alice")
        db.create_team("t1", "Alpha", "user_a")
        members = db.list_team_members("t1")
        assert members[0]["email"] == "a@test.com"
        assert members[0]["name"] == "Alice"

    def test_is_team_member(self, db):
        db.create_team("t1", "Alpha", "user_a")
        assert db.is_team_member("t1", "user_a") is True
        assert db.is_team_member("t1", "user_b") is False

    def test_get_member_role_nonexistent(self, db):
        db.create_team("t1", "Alpha", "user_a")
        assert db.get_member_role("t1", "ghost") is None

    def test_delete_team(self, db):
        db.create_team("t1", "Alpha", "user_a")
        db.add_team_member("t1", "user_b")
        assert db.delete_team("t1") is True
        assert db.get_team("t1") is None
        # Members should also be removed
        assert db.is_team_member("t1", "user_a") is False
        assert db.is_team_member("t1", "user_b") is False

    def test_delete_team_nonexistent(self, db):
        assert db.delete_team("ghost") is False

    def test_member_appears_in_list_user_teams(self, db):
        """Non-owner members should see the team in list_user_teams."""
        db.create_team("t1", "Alpha", "user_a")
        db.add_team_member("t1", "user_b", role="member")
        teams = db.list_user_teams("user_b")
        assert len(teams) == 1
        assert teams[0]["name"] == "Alpha"
        assert teams[0]["role"] == "member"
