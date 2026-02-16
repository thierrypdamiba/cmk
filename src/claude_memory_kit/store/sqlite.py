"""SQLite store for auth data only (users, API keys, teams).

Memory storage moved to Qdrant in v0.2.0. This module retains schema
migrations for backward compatibility and provides auth-related tables.
"""

import os
import sqlite3
from datetime import datetime, timezone


class SqliteStore:
    def __init__(self, store_path: str):
        os.makedirs(store_path, exist_ok=True)
        db_path = os.path.join(store_path, "index.db")
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

    # Current schema version. Bump when adding new migrations.
    SCHEMA_VERSION = 6

    def migrate(self) -> None:
        """Run all pending schema migrations in order."""
        current = self._get_schema_version()
        migrations = [
            self._migration_1_initial_schema,
            self._migration_2_add_columns,
            self._migration_3_add_pinned,
            self._migration_4_indexes,
            self._migration_5_fts,
            self._migration_6_teams,
        ]
        for i, fn in enumerate(migrations, start=1):
            if current < i:
                fn()
        self._set_schema_version(self.SCHEMA_VERSION)
        self.conn.commit()

    def _get_schema_version(self) -> int:
        """Get current schema version, creating tracking table if needed."""
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_version "
            "(id INTEGER PRIMARY KEY CHECK (id = 1), version INTEGER NOT NULL)"
        )
        row = self.conn.execute(
            "SELECT version FROM schema_version WHERE id = 1"
        ).fetchone()
        if row:
            return row[0]
        return 0

    def _set_schema_version(self, version: int) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO schema_version (id, version) VALUES (1, ?)",
            (version,),
        )

    # ------------------------------------------------------------------ #
    #  Schema migrations (kept for backward compat with existing DBs)     #
    # ------------------------------------------------------------------ #

    def _migration_1_initial_schema(self) -> None:
        """Create all core tables (legacy memory tables + auth tables)."""
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                created TEXT NOT NULL,
                gate TEXT NOT NULL,
                person TEXT,
                project TEXT,
                confidence REAL NOT NULL DEFAULT 0.9,
                last_accessed TEXT NOT NULL,
                access_count INTEGER NOT NULL DEFAULT 1,
                decay_class TEXT NOT NULL,
                content TEXT NOT NULL,
                user_id TEXT NOT NULL DEFAULT 'local'
            );

            CREATE TABLE IF NOT EXISTS journal (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                gate TEXT NOT NULL,
                content TEXT NOT NULL,
                person TEXT,
                project TEXT,
                user_id TEXT NOT NULL DEFAULT 'local'
            );
            CREATE INDEX IF NOT EXISTS idx_journal_date
                ON journal(date);

            CREATE TABLE IF NOT EXISTS identity (
                user_id TEXT PRIMARY KEY DEFAULT 'local',
                person TEXT,
                project TEXT,
                content TEXT NOT NULL,
                last_updated TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS edges (
                from_id TEXT NOT NULL,
                to_id TEXT NOT NULL,
                relation TEXT NOT NULL,
                created TEXT NOT NULL,
                user_id TEXT NOT NULL DEFAULT 'local',
                PRIMARY KEY (from_id, to_id, relation)
            );

            CREATE TABLE IF NOT EXISTS relationships (
                person TEXT PRIMARY KEY,
                communication_style TEXT,
                vals TEXT,
                energizers TEXT,
                triggers TEXT,
                open_commitments TEXT,
                last_updated TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS onboarding (
                user_id TEXT PRIMARY KEY DEFAULT 'local',
                step INTEGER NOT NULL DEFAULT 0,
                person TEXT,
                project TEXT,
                style TEXT
            );

            CREATE TABLE IF NOT EXISTS archive (
                id TEXT PRIMARY KEY,
                original_gate TEXT,
                content TEXT NOT NULL,
                reason TEXT NOT NULL,
                archived_at TEXT NOT NULL,
                user_id TEXT NOT NULL DEFAULT 'local'
            );

            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT,
                name TEXT DEFAULT '',
                plan TEXT DEFAULT 'free',
                created TEXT NOT NULL,
                last_seen TEXT
            );

            CREATE TABLE IF NOT EXISTS api_keys (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                name TEXT DEFAULT '',
                key_hash TEXT UNIQUE NOT NULL,
                prefix TEXT NOT NULL,
                created TEXT NOT NULL,
                last_used TEXT,
                revoked INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS rules (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL DEFAULT 'local',
                scope TEXT NOT NULL DEFAULT 'global',
                condition TEXT NOT NULL,
                enforcement TEXT NOT NULL DEFAULT 'suggest',
                created TEXT NOT NULL,
                last_triggered TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_rules_user
                ON rules(user_id);
        """)

    def _migration_2_add_columns(self) -> None:
        columns = [
            ("memories", "user_id", "TEXT NOT NULL DEFAULT 'local'"),
            ("journal", "user_id", "TEXT NOT NULL DEFAULT 'local'"),
            ("edges", "user_id", "TEXT NOT NULL DEFAULT 'local'"),
            ("archive", "user_id", "TEXT NOT NULL DEFAULT 'local'"),
            ("memories", "sensitivity", "TEXT"),
            ("memories", "sensitivity_reason", "TEXT"),
        ]
        for table, col, typedef in columns:
            if not self._has_column(table, col):
                self.conn.execute(
                    f"ALTER TABLE {table} ADD COLUMN {col} {typedef}"
                )

    def _migration_3_add_pinned(self) -> None:
        if not self._has_column("memories", "pinned"):
            self.conn.execute(
                "ALTER TABLE memories ADD COLUMN pinned INTEGER DEFAULT 0"
            )

    def _migration_4_indexes(self) -> None:
        self.conn.executescript("""
            CREATE INDEX IF NOT EXISTS idx_memories_user
                ON memories(user_id);
            CREATE INDEX IF NOT EXISTS idx_journal_user
                ON journal(user_id);
            CREATE INDEX IF NOT EXISTS idx_archive_user
                ON archive(user_id);
            CREATE INDEX IF NOT EXISTS idx_memories_user_gate_created
                ON memories(user_id, gate, created DESC);
            CREATE INDEX IF NOT EXISTS idx_memories_user_person
                ON memories(user_id, person);
            CREATE INDEX IF NOT EXISTS idx_memories_user_project
                ON memories(user_id, project);
            CREATE INDEX IF NOT EXISTS idx_journal_user_date
                ON journal(user_id, date, timestamp);
            CREATE INDEX IF NOT EXISTS idx_edges_user_from
                ON edges(user_id, from_id);
            CREATE INDEX IF NOT EXISTS idx_edges_user_to
                ON edges(user_id, to_id);
            CREATE INDEX IF NOT EXISTS idx_memories_user_sensitivity
                ON memories(user_id, sensitivity);
        """)

    def _migration_5_fts(self) -> None:
        fts_exists = self.conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='memories_fts'"
        ).fetchone()
        if not fts_exists:
            self.conn.executescript("""
                CREATE VIRTUAL TABLE memories_fts USING fts5(
                    content, person, project,
                    content='memories', content_rowid='rowid'
                );
                CREATE TRIGGER memories_ai AFTER INSERT ON memories BEGIN
                    INSERT INTO memories_fts(rowid, content, person, project)
                    VALUES (new.rowid, new.content, new.person, new.project);
                END;
                CREATE TRIGGER memories_ad AFTER DELETE ON memories BEGIN
                    INSERT INTO memories_fts(
                        memories_fts, rowid, content, person, project
                    ) VALUES (
                        'delete', old.rowid, old.content, old.person, old.project
                    );
                END;
                CREATE TRIGGER memories_au AFTER UPDATE ON memories BEGIN
                    INSERT INTO memories_fts(
                        memories_fts, rowid, content, person, project
                    ) VALUES (
                        'delete', old.rowid, old.content, old.person, old.project
                    );
                    INSERT INTO memories_fts(rowid, content, person, project)
                    VALUES (new.rowid, new.content, new.person, new.project);
                END;
            """)
            return
        au_exists = self.conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='trigger' AND name='memories_au'"
        ).fetchone()
        if not au_exists:
            self.conn.executescript("""
                CREATE TRIGGER memories_au AFTER UPDATE ON memories BEGIN
                    INSERT INTO memories_fts(
                        memories_fts, rowid, content, person, project
                    ) VALUES (
                        'delete', old.rowid, old.content, old.person, old.project
                    );
                    INSERT INTO memories_fts(rowid, content, person, project)
                    VALUES (new.rowid, new.content, new.person, new.project);
                END;
            """)

    def _migration_6_teams(self) -> None:
        """Add teams and team_members tables."""
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS teams (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                created_by TEXT NOT NULL,
                created TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS team_members (
                team_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'member',
                joined TEXT NOT NULL,
                PRIMARY KEY (team_id, user_id),
                FOREIGN KEY (team_id) REFERENCES teams(id)
            );
            CREATE INDEX IF NOT EXISTS idx_team_members_user
                ON team_members(user_id);
        """)

    # ------------------------------------------------------------------ #
    #  Helpers                                                             #
    # ------------------------------------------------------------------ #

    def _has_column(self, table: str, column: str) -> bool:
        cols = self.conn.execute(f"PRAGMA table_info({table})").fetchall()
        return any(c[1] == column for c in cols)

    # ------------------------------------------------------------------ #
    #  Users                                                               #
    # ------------------------------------------------------------------ #

    def upsert_user(
        self, user_id: str, email: str | None = None,
        name: str = "", plan: str = "free",
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            "INSERT INTO users (id, email, name, plan, created, last_seen) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET "
            "last_seen = ?, name = COALESCE(?, name), "
            "email = COALESCE(?, email)",
            (user_id, email, name, plan, now, now, now, name, email),
        )
        self.conn.commit()

    def get_user(self, user_id: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        return dict(row) if row else None

    # ------------------------------------------------------------------ #
    #  API Keys                                                            #
    # ------------------------------------------------------------------ #

    def insert_api_key(
        self, key_id: str, user_id: str, key_hash: str,
        prefix: str, name: str = "",
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            "INSERT INTO api_keys "
            "(id, user_id, name, key_hash, prefix, created) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (key_id, user_id, name, key_hash, prefix, now),
        )
        self.conn.commit()

    def get_api_key_by_hash(self, key_hash: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM api_keys "
            "WHERE key_hash = ? AND revoked = 0",
            (key_hash,),
        ).fetchone()
        if row:
            self.conn.execute(
                "UPDATE api_keys SET last_used = ? WHERE id = ?",
                (datetime.now(timezone.utc).isoformat(), row["id"]),
            )
            self.conn.commit()
        return dict(row) if row else None

    def list_api_keys(self, user_id: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT id, name, prefix, created, last_used, revoked "
            "FROM api_keys WHERE user_id = ? ORDER BY created DESC",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def revoke_api_key(self, key_id: str, user_id: str) -> bool:
        cur = self.conn.execute(
            "UPDATE api_keys SET revoked = 1 "
            "WHERE id = ? AND user_id = ?",
            (key_id, user_id),
        )
        self.conn.commit()
        return cur.rowcount > 0

    # ------------------------------------------------------------------ #
    #  Teams                                                               #
    # ------------------------------------------------------------------ #

    def create_team(self, team_id: str, name: str, created_by: str) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            "INSERT INTO teams (id, name, created_by, created) "
            "VALUES (?, ?, ?, ?)",
            (team_id, name, created_by, now),
        )
        # Auto-add creator as owner
        self.conn.execute(
            "INSERT INTO team_members (team_id, user_id, role, joined) "
            "VALUES (?, ?, 'owner', ?)",
            (team_id, created_by, now),
        )
        self.conn.commit()
        return {"id": team_id, "name": name, "created_by": created_by, "created": now}

    def get_team(self, team_id: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM teams WHERE id = ?", (team_id,)
        ).fetchone()
        return dict(row) if row else None

    def list_user_teams(self, user_id: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT t.*, tm.role FROM teams t "
            "JOIN team_members tm ON t.id = tm.team_id "
            "WHERE tm.user_id = ? ORDER BY t.created DESC",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def add_team_member(
        self, team_id: str, user_id: str, role: str = "member",
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            "INSERT OR REPLACE INTO team_members (team_id, user_id, role, joined) "
            "VALUES (?, ?, ?, ?)",
            (team_id, user_id, role, now),
        )
        self.conn.commit()

    def remove_team_member(self, team_id: str, user_id: str) -> bool:
        cur = self.conn.execute(
            "DELETE FROM team_members WHERE team_id = ? AND user_id = ?",
            (team_id, user_id),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def list_team_members(self, team_id: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT tm.user_id, tm.role, tm.joined, u.email, u.name "
            "FROM team_members tm "
            "LEFT JOIN users u ON tm.user_id = u.id "
            "WHERE tm.team_id = ? ORDER BY tm.joined",
            (team_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def is_team_member(self, team_id: str, user_id: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM team_members WHERE team_id = ? AND user_id = ?",
            (team_id, user_id),
        ).fetchone()
        return row is not None

    def get_member_role(self, team_id: str, user_id: str) -> str | None:
        row = self.conn.execute(
            "SELECT role FROM team_members WHERE team_id = ? AND user_id = ?",
            (team_id, user_id),
        ).fetchone()
        return row[0] if row else None

    def delete_team(self, team_id: str) -> bool:
        self.conn.execute(
            "DELETE FROM team_members WHERE team_id = ?", (team_id,)
        )
        cur = self.conn.execute(
            "DELETE FROM teams WHERE id = ?", (team_id,)
        )
        self.conn.commit()
        return cur.rowcount > 0
