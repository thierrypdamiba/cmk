"""Postgres store for auth data (users, API keys, teams).

Used when DATABASE_URL is set. Connects to Supabase Postgres where
BetterAuth manages core user/session tables and CMK adds api_keys,
teams, and team_members.
"""

from datetime import datetime, timezone

import psycopg
from psycopg.rows import dict_row


class PostgresStore:
    def __init__(self, dsn: str):
        self.conn = psycopg.connect(dsn, row_factory=dict_row)
        self.conn.autocommit = True

    # ------------------------------------------------------------------ #
    #  Users (BetterAuth "user" table with CMK columns)                   #
    # ------------------------------------------------------------------ #

    def upsert_user(
        self, user_id: str, email: str | None = None,
        name: str = "", plan: str = "free",
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO "user" (id, email, name, plan, "createdAt", "updatedAt", last_seen, "emailVerified")
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    last_seen = %s,
                    name = COALESCE(%s, "user".name),
                    email = COALESCE(%s, "user".email),
                    "updatedAt" = %s
                """,
                (user_id, email or "", name, plan, now, now, now, False,
                 now, name, email, now),
            )

    def get_user(self, user_id: str) -> dict | None:
        with self.conn.cursor() as cur:
            cur.execute(
                'SELECT id, email, name, plan, last_seen FROM "user" WHERE id = %s',
                (user_id,),
            )
            return cur.fetchone()

    # ------------------------------------------------------------------ #
    #  API Keys                                                            #
    # ------------------------------------------------------------------ #

    def insert_api_key(
        self, key_id: str, user_id: str, key_hash: str,
        prefix: str, name: str = "",
    ) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO api_keys "
                "(id, user_id, name, key_hash, prefix, created) "
                "VALUES (%s, %s, %s, %s, %s, NOW())",
                (key_id, user_id, name, key_hash, prefix),
            )

    def get_api_key_by_hash(self, key_hash: str) -> dict | None:
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM api_keys "
                "WHERE key_hash = %s AND revoked = FALSE",
                (key_hash,),
            )
            row = cur.fetchone()
            if row:
                cur.execute(
                    "UPDATE api_keys SET last_used = NOW() WHERE id = %s",
                    (row["id"],),
                )
            return row

    def list_api_keys(self, user_id: str) -> list[dict]:
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, prefix, created, last_used, revoked "
                "FROM api_keys WHERE user_id = %s ORDER BY created DESC",
                (user_id,),
            )
            return [dict(r) for r in cur.fetchall()]

    def revoke_api_key(self, key_id: str, user_id: str) -> bool:
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE api_keys SET revoked = TRUE "
                "WHERE id = %s AND user_id = %s",
                (key_id, user_id),
            )
            return cur.rowcount > 0

    # ------------------------------------------------------------------ #
    #  Teams                                                               #
    # ------------------------------------------------------------------ #

    def create_team(self, team_id: str, name: str, created_by: str) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO teams (id, name, created_by, created) "
                "VALUES (%s, %s, %s, %s)",
                (team_id, name, created_by, now),
            )
            cur.execute(
                "INSERT INTO team_members (team_id, user_id, role, joined) "
                "VALUES (%s, %s, 'owner', %s)",
                (team_id, created_by, now),
            )
        return {"id": team_id, "name": name, "created_by": created_by, "created": now}

    def get_team(self, team_id: str) -> dict | None:
        with self.conn.cursor() as cur:
            cur.execute("SELECT * FROM teams WHERE id = %s", (team_id,))
            return cur.fetchone()

    def list_user_teams(self, user_id: str) -> list[dict]:
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT t.*, tm.role FROM teams t "
                "JOIN team_members tm ON t.id = tm.team_id "
                "WHERE tm.user_id = %s ORDER BY t.created DESC",
                (user_id,),
            )
            return [dict(r) for r in cur.fetchall()]

    def add_team_member(
        self, team_id: str, user_id: str, role: str = "member",
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO team_members (team_id, user_id, role, joined) "
                "VALUES (%s, %s, %s, %s) "
                "ON CONFLICT (team_id, user_id) DO UPDATE SET role = %s, joined = %s",
                (team_id, user_id, role, now, role, now),
            )

    def remove_team_member(self, team_id: str, user_id: str) -> bool:
        with self.conn.cursor() as cur:
            cur.execute(
                "DELETE FROM team_members WHERE team_id = %s AND user_id = %s",
                (team_id, user_id),
            )
            return cur.rowcount > 0

    def list_team_members(self, team_id: str) -> list[dict]:
        with self.conn.cursor() as cur:
            cur.execute(
                'SELECT tm.user_id, tm.role, tm.joined, u.email, u.name '
                'FROM team_members tm '
                'LEFT JOIN "user" u ON tm.user_id = u.id '
                "WHERE tm.team_id = %s ORDER BY tm.joined",
                (team_id,),
            )
            return [dict(r) for r in cur.fetchall()]

    def is_team_member(self, team_id: str, user_id: str) -> bool:
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM team_members WHERE team_id = %s AND user_id = %s",
                (team_id, user_id),
            )
            return cur.fetchone() is not None

    def get_member_role(self, team_id: str, user_id: str) -> str | None:
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT role FROM team_members WHERE team_id = %s AND user_id = %s",
                (team_id, user_id),
            )
            row = cur.fetchone()
            return row["role"] if row else None

    def delete_team(self, team_id: str) -> bool:
        with self.conn.cursor() as cur:
            cur.execute(
                "DELETE FROM team_members WHERE team_id = %s", (team_id,)
            )
            cur.execute(
                "DELETE FROM teams WHERE id = %s", (team_id,)
            )
            return cur.rowcount > 0
