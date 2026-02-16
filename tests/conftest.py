"""Shared fixtures for CMK test suite."""

import os
import tempfile

import pytest

# Force local mode, no real API keys, no auth
os.environ["QDRANT_URL"] = ""
os.environ["QDRANT_API_KEY"] = ""
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["BETTER_AUTH_URL"] = ""
os.environ["BETTER_AUTH_SECRET"] = ""
os.environ["DATABASE_URL"] = ""


@pytest.fixture
def tmp_store_path(tmp_path):
    """Return a fresh temp directory for store data."""
    return str(tmp_path / "cmk-test-store")


@pytest.fixture
def db(tmp_store_path):
    """Return a fresh migrated SqliteStore (for auth tests)."""
    from claude_memory_kit.store.sqlite import SqliteStore
    store = SqliteStore(tmp_store_path)
    store.migrate()
    return store


@pytest.fixture
def qdrant_db():
    """Return a fresh in-memory QdrantStore with fake embeddings."""
    from qdrant_client import QdrantClient
    from qdrant_client.models import SparseVector
    from claude_memory_kit.store.qdrant_store import QdrantStore

    qs = QdrantStore.__new__(QdrantStore)
    qs.client = QdrantClient(":memory:")
    qs._cloud = False
    qs._disabled = False
    qs._jina_key = ""
    qs._fastembed_dense = None
    qs._fastembed_sparse = None
    qs._create_hybrid_collection()

    # Fake vector generator (no real embeddings in tests)
    def _fake_vector(content, *, query=False):
        return {
            "dense": [0.0] * 384,
            "sparse": SparseVector(indices=[0], values=[1.0]),
        }
    qs._make_vector = _fake_vector

    return qs


@pytest.fixture
def make_memory():
    """Factory for creating Memory objects."""
    from datetime import datetime, timezone
    from claude_memory_kit.types import Memory, Gate, DecayClass

    def _make(
        id="mem_test_001",
        gate=Gate.epistemic,
        content="test memory content",
        person=None,
        project=None,
        confidence=0.9,
        access_count=1,
        sensitivity=None,
        sensitivity_reason=None,
    ):
        now = datetime.now(timezone.utc)
        return Memory(
            id=id,
            created=now,
            gate=gate,
            person=person,
            project=project,
            confidence=confidence,
            last_accessed=now,
            access_count=access_count,
            decay_class=DecayClass.from_gate(gate),
            content=content,
            sensitivity=sensitivity,
            sensitivity_reason=sensitivity_reason,
        )
    return _make
