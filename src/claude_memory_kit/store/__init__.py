import os

from .qdrant_store import QdrantStore
from .sqlite import SqliteStore


def _make_auth_db(path: str):
    """Create auth DB backend: Postgres if DATABASE_URL set, else SQLite."""
    dsn = os.getenv("DATABASE_URL", "")
    if dsn and not dsn.startswith("<"):
        from .postgres import PostgresStore
        return PostgresStore(dsn)
    return SqliteStore(path)


class Store:
    """Cloud-only store: Qdrant for memories, Postgres or SQLite for auth."""

    def __init__(self, path: str):
        self.path = path
        self.qdrant = QdrantStore(path)
        self.auth_db = _make_auth_db(path)

    async def init(self) -> None:
        # Only run SQLite migrations; Postgres schema is managed externally
        if not os.getenv("DATABASE_URL", "").strip():
            self.auth_db.migrate()
        self.qdrant.ensure_collection()

    def count_user_data(self, user_id: str) -> dict:
        count = self.qdrant.count_memories(user_id=user_id)
        return {"memories": count, "total": count}

    def migrate_user_data(self, from_id: str, to_id: str) -> dict:
        count = self.qdrant.migrate_user_id(from_id, to_id)
        return {"memories": count, "total": count}
