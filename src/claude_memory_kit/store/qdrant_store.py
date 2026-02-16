"""Cloud-only store backed entirely by Qdrant.

All memory metadata, journal entries, identity cards, and rules are stored
as Qdrant point payloads with a `type` discriminator field. Graph edges
are stored inline as payload arrays on memory points.
"""

from __future__ import annotations

import hashlib
import logging
import os
import struct
import time
from datetime import datetime, timezone

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    Document,
    FieldCondition,
    Filter,
    FilterSelector,
    Fusion,
    FusionQuery,
    HnswConfigDiff,
    IsNullCondition,
    KeywordIndexParams,
    KeywordIndexType,
    MatchText,
    MatchValue,
    Modifier,
    OrderBy,
    PayloadField,
    PointStruct,
    Prefetch,
    Range,
    SparseVector,
    SparseVectorParams,
    TextIndexParams,
    TokenizerType,
    VectorParams,
)

from ..config import get_qdrant_config
from ..types import DecayClass, Gate, IdentityCard, JournalEntry, Memory, Visibility

log = logging.getLogger("cmk")

COLLECTION = "cmk_memories"
JINA_MODEL = "jinaai/jina-embeddings-v3"
JINA_DIM = 1024
LOCAL_MODEL = "BAAI/bge-small-en-v1.5"
LOCAL_DIM = 384
SPARSE_MODEL = "Qdrant/bm25"
BM25_CLOUD_MODEL = "Qdrant/bm25"


def _stable_id(key: str) -> int:
    """Deterministic point ID from a string key."""
    digest = hashlib.sha256(key.encode()).digest()
    return struct.unpack(">Q", digest[:8])[0] >> 1


def _memory_from_payload(payload: dict) -> Memory:
    """Reconstruct a Memory object from a Qdrant point payload."""
    created_ts = payload.get("created", 0)
    accessed_ts = payload.get("last_accessed", created_ts)
    vis_str = payload.get("visibility", "private")
    try:
        vis = Visibility(vis_str)
    except ValueError:
        vis = Visibility.private
    return Memory(
        id=payload.get("memory_id", ""),
        created=datetime.fromtimestamp(created_ts, tz=timezone.utc),
        gate=Gate(payload.get("gate", "epistemic")),
        person=payload.get("person") or None,
        project=payload.get("project") or None,
        confidence=payload.get("confidence", 0.9),
        last_accessed=datetime.fromtimestamp(accessed_ts, tz=timezone.utc),
        access_count=payload.get("access_count", 1),
        decay_class=DecayClass(payload.get("decay_class", "moderate")),
        content=payload.get("content", ""),
        pinned=payload.get("pinned", False),
        sensitivity=payload.get("sensitivity"),
        sensitivity_reason=payload.get("sensitivity_reason"),
        visibility=vis,
        team_id=payload.get("team_id") or None,
        created_by=payload.get("created_by") or None,
    )


class QdrantStore:
    """Cloud-only store. Everything lives in Qdrant payloads."""

    def __init__(self, store_path: str):
        self._disabled = False
        self._cloud = False
        self._jina_key = ""
        self._fastembed_dense = None
        self._fastembed_sparse = None
        cfg = get_qdrant_config()

        if cfg["mode"] == "cloud":
            self._cloud = True
            self._jina_key = cfg.get("jina_api_key", "")
            log.info("connecting to qdrant cloud (QCI + jina)")
            try:
                self.client = QdrantClient(
                    url=cfg["url"],
                    api_key=cfg.get("api_key", ""),
                    cloud_inference=True,
                    timeout=30,
                )
            except Exception as e:
                log.warning("qdrant cloud failed: %s. store disabled.", e)
                self.client = None
                self._disabled = True
                return
        else:
            qdrant_path = os.path.join(store_path, "qdrant")
            os.makedirs(qdrant_path, exist_ok=True)
            try:
                self.client = QdrantClient(path=qdrant_path)
            except RuntimeError as e:
                if "already accessed" in str(e):
                    log.debug("qdrant locked. store disabled.")
                    self.client = None
                    self._disabled = True
                else:
                    raise

    # ------------------------------------------------------------------ #
    #  Embedding helpers                                                   #
    # ------------------------------------------------------------------ #

    @property
    def _local_dense_model(self):
        if self._fastembed_dense is None:
            from fastembed import TextEmbedding
            self._fastembed_dense = TextEmbedding(LOCAL_MODEL)
        return self._fastembed_dense

    @property
    def _local_sparse_model(self):
        if self._fastembed_sparse is None:
            from fastembed import SparseTextEmbedding
            self._fastembed_sparse = SparseTextEmbedding(SPARSE_MODEL)
        return self._fastembed_sparse

    def _embed_local(self, text: str) -> list[float]:
        return list(self._local_dense_model.embed([text]))[0].tolist()

    def _embed_sparse_local(self, text: str) -> SparseVector:
        emb = list(self._local_sparse_model.embed([text]))[0]
        return SparseVector(indices=emb.indices.tolist(), values=emb.values.tolist())

    def _query_sparse_local(self, text: str) -> SparseVector:
        emb = list(self._local_sparse_model.query_embed(text))[0]
        return SparseVector(indices=emb.indices.tolist(), values=emb.values.tolist())

    def _jina_doc(self, text: str, task: str = "retrieval.passage"):
        return Document(
            text=text,
            model=JINA_MODEL,
            options={"jina-api-key": self._jina_key, "dimensions": JINA_DIM, "task": task},
        )

    def _sparse_doc(self, text: str):
        return Document(text=text, model=BM25_CLOUD_MODEL)

    def _make_vector(self, content: str, *, query: bool = False) -> dict:
        if self._cloud:
            task = "retrieval.query" if query else "retrieval.passage"
            return {
                "dense": self._jina_doc(content, task=task),
                "sparse": self._sparse_doc(content),
            }
        if query:
            return {
                "dense": self._embed_local(content),
                "sparse": self._query_sparse_local(content),
            }
        return {
            "dense": self._embed_local(content),
            "sparse": self._embed_sparse_local(content),
        }

    # ------------------------------------------------------------------ #
    #  Collection management                                               #
    # ------------------------------------------------------------------ #

    def _create_hybrid_collection(self) -> None:
        dim = JINA_DIM if self._cloud else LOCAL_DIM
        kwargs = {}
        if self._cloud:
            kwargs["hnsw_config"] = HnswConfigDiff(payload_m=16, m=0)

        self.client.create_collection(
            collection_name=COLLECTION,
            vectors_config={"dense": VectorParams(size=dim, distance=Distance.COSINE)},
            sparse_vectors_config={"sparse": SparseVectorParams(modifier=Modifier.IDF)},
            **kwargs,
        )

        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        """Idempotently create all required payload indexes.

        Safe to call on existing collections. Each call is wrapped in
        try/except so already-existing indexes don't cause failures.
        """
        # Full-text index on content
        try:
            self.client.create_payload_index(
                collection_name=COLLECTION,
                field_name="content",
                field_schema=TextIndexParams(
                    type="text", tokenizer=TokenizerType.WORD,
                    min_token_len=2, lowercase=True,
                ),
            )
        except Exception:
            pass

        # Keyword indexes for metadata queries
        for field in ("type", "gate", "sensitivity", "person", "project",
                       "memory_id", "date", "rule_id", "team_id", "visibility"):
            try:
                self.client.create_payload_index(
                    collection_name=COLLECTION,
                    field_name=field,
                    field_schema=KeywordIndexParams(type=KeywordIndexType.KEYWORD),
                )
            except Exception:
                pass

        # Tenant index for user_id (cloud only)
        if self._cloud:
            try:
                self.client.create_payload_index(
                    collection_name=COLLECTION,
                    field_name="user_id",
                    field_schema=KeywordIndexParams(
                        type=KeywordIndexType.KEYWORD, is_tenant=True,
                    ),
                )
            except Exception:
                pass

    def ensure_collection(self) -> None:
        if self._disabled:
            return
        try:
            names = [c.name for c in self.client.get_collections().collections]
            if COLLECTION not in names:
                self._create_hybrid_collection()
                log.info("created collection: %s (cloud=%s)", COLLECTION, self._cloud)
            else:
                self._ensure_indexes()
        except Exception as e:
            log.warning("collection setup failed: %s. store disabled.", e)
            self.client = None
            self._disabled = True

    # ------------------------------------------------------------------ #
    #  Scroll helper                                                       #
    # ------------------------------------------------------------------ #

    def _scroll_all(
        self,
        conditions: list,
        limit: int = 100,
        order_by: str | None = None,
        order_direction: str = "desc",
    ) -> list:
        """Scroll with filter, return all matching points up to limit."""
        if self._disabled:
            return []
        kwargs: dict = {
            "collection_name": COLLECTION,
            "scroll_filter": Filter(must=conditions),
            "limit": limit,
            "with_payload": True,
            "with_vectors": False,
        }
        if order_by:
            kwargs["order_by"] = OrderBy(key=order_by, direction=order_direction)
        results, _ = self.client.scroll(**kwargs)
        return results

    # ------------------------------------------------------------------ #
    #  Memory CRUD                                                         #
    # ------------------------------------------------------------------ #

    def _memory_payload(self, memory: Memory, user_id: str) -> dict:
        return {
            "type": "memory",
            "memory_id": memory.id,
            "content": memory.content,
            "person": memory.person or "",
            "project": memory.project or "",
            "user_id": user_id,
            "gate": memory.gate.value,
            "confidence": memory.confidence,
            "created": memory.created.timestamp(),
            "last_accessed": memory.last_accessed.timestamp(),
            "access_count": memory.access_count,
            "decay_class": memory.decay_class.value,
            "pinned": memory.pinned,
            "sensitivity": memory.sensitivity,
            "sensitivity_reason": memory.sensitivity_reason,
            "visibility": memory.visibility.value,
            "team_id": memory.team_id or "",
            "created_by": memory.created_by or "",
            "edges": [],
        }

    def insert_memory(
        self,
        memory: Memory,
        user_id: str = "local",
        visibility: str | None = None,
        team_id: str | None = None,
        created_by: str | None = None,
    ) -> None:
        if self._disabled:
            return
        # Apply team overrides to a copy of the memory
        if visibility or team_id or created_by:
            updates = {}
            if visibility:
                updates["visibility"] = Visibility(visibility)
            if team_id:
                updates["team_id"] = team_id
            if created_by:
                updates["created_by"] = created_by
            memory = memory.model_copy(update=updates)
        point_id = _stable_id(memory.id)
        payload = self._memory_payload(memory, user_id)
        vector = self._make_vector(memory.content)
        self.client.upsert(
            collection_name=COLLECTION,
            points=[PointStruct(id=point_id, vector=vector, payload=payload)],
        )

    def get_memory(self, memory_id: str, user_id: str = "local") -> Memory | None:
        if self._disabled:
            return None
        points = self._scroll_all([
            FieldCondition(key="type", match=MatchValue(value="memory")),
            FieldCondition(key="memory_id", match=MatchValue(value=memory_id)),
            FieldCondition(key="user_id", match=MatchValue(value=user_id)),
        ], limit=1)
        if not points:
            return None
        return _memory_from_payload(points[0].payload)

    def list_memories(
        self,
        limit: int = 50,
        offset: int = 0,
        user_id: str = "local",
        gate: str | None = None,
        person: str | None = None,
        project: str | None = None,
        team_id: str | None = None,
        visibility: str | None = None,
    ) -> list[Memory]:
        if self._disabled:
            return []

        if team_id and not visibility:
            # Combined view: private + team
            base_filter = self._build_memory_filter(user_id=user_id, team_id=team_id)
            extra_must = []
            if gate:
                extra_must.append(FieldCondition(key="gate", match=MatchValue(value=gate)))
            if person:
                extra_must.append(FieldCondition(key="person", match=MatchValue(value=person)))
            if project:
                extra_must.append(FieldCondition(key="project", match=MatchValue(value=project)))
            combined_must = list(base_filter.must or []) + extra_must
            scroll_filter = Filter(must=combined_must, should=base_filter.should)
            fetch_limit = offset + limit
            results, _ = self.client.scroll(
                collection_name=COLLECTION,
                scroll_filter=scroll_filter,
                limit=fetch_limit,
                with_payload=True,
                with_vectors=False,
                order_by=OrderBy(key="created", direction="desc"),
            )
            return [_memory_from_payload(p.payload) for p in results[offset:]]

        conditions = [
            FieldCondition(key="type", match=MatchValue(value="memory")),
            FieldCondition(key="user_id", match=MatchValue(value=user_id)),
        ]
        if gate:
            conditions.append(FieldCondition(key="gate", match=MatchValue(value=gate)))
        if person:
            conditions.append(FieldCondition(key="person", match=MatchValue(value=person)))
        if project:
            conditions.append(FieldCondition(key="project", match=MatchValue(value=project)))
        if visibility:
            conditions.append(FieldCondition(key="visibility", match=MatchValue(value=visibility)))
        if team_id:
            conditions.append(FieldCondition(key="team_id", match=MatchValue(value=team_id)))

        # Fetch offset + limit, then skip offset on client side
        fetch_limit = offset + limit
        points = self._scroll_all(conditions, limit=fetch_limit, order_by="created")
        return [_memory_from_payload(p.payload) for p in points[offset:]]

    def delete_memory(self, memory_id: str, user_id: str = "local") -> Memory | None:
        mem = self.get_memory(memory_id, user_id)
        if mem is None:
            return None
        self.client.delete(
            collection_name=COLLECTION,
            points_selector=FilterSelector(filter=Filter(must=[
                FieldCondition(key="memory_id", match=MatchValue(value=memory_id)),
                FieldCondition(key="user_id", match=MatchValue(value=user_id)),
            ])),
        )
        return mem

    def touch_memory(self, memory_id: str, user_id: str = "local") -> None:
        if self._disabled:
            return
        points = self._scroll_all([
            FieldCondition(key="type", match=MatchValue(value="memory")),
            FieldCondition(key="memory_id", match=MatchValue(value=memory_id)),
            FieldCondition(key="user_id", match=MatchValue(value=user_id)),
        ], limit=1)
        if not points:
            return
        pt = points[0]
        now = time.time()
        count = (pt.payload.get("access_count") or 0) + 1
        self.client.set_payload(
            collection_name=COLLECTION,
            payload={"last_accessed": now, "access_count": count},
            points=[pt.id],
        )

    def update_memory(self, memory_id: str, user_id: str = "local", **kwargs) -> None:
        if self._disabled:
            return
        points = self._scroll_all([
            FieldCondition(key="type", match=MatchValue(value="memory")),
            FieldCondition(key="memory_id", match=MatchValue(value=memory_id)),
            FieldCondition(key="user_id", match=MatchValue(value=user_id)),
        ], limit=1)
        if not points:
            return
        pt = points[0]
        payload_update = {}
        for field in ("content", "gate", "person", "project"):
            if field in kwargs:
                payload_update[field] = kwargs[field]

        if payload_update:
            self.client.set_payload(
                collection_name=COLLECTION,
                payload=payload_update,
                points=[pt.id],
            )

        # Re-embed if content changed
        if "content" in kwargs:
            new_content = kwargs["content"]
            vector = self._make_vector(new_content)
            self.client.upsert(
                collection_name=COLLECTION,
                points=[PointStruct(id=pt.id, vector=vector, payload={**pt.payload, **payload_update})],
            )

    def set_pinned(self, memory_id: str, pinned: bool, user_id: str = "local") -> None:
        if self._disabled:
            return
        points = self._scroll_all([
            FieldCondition(key="type", match=MatchValue(value="memory")),
            FieldCondition(key="memory_id", match=MatchValue(value=memory_id)),
            FieldCondition(key="user_id", match=MatchValue(value=user_id)),
        ], limit=1)
        if points:
            self.client.set_payload(
                collection_name=COLLECTION,
                payload={"pinned": pinned},
                points=[points[0].id],
            )

    def count_memories(self, user_id: str = "local") -> int:
        if self._disabled:
            return 0
        result = self.client.count(
            collection_name=COLLECTION,
            count_filter=Filter(must=[
                FieldCondition(key="type", match=MatchValue(value="memory")),
                FieldCondition(key="user_id", match=MatchValue(value=user_id)),
            ]),
            exact=True,
        )
        return result.count

    def count_by_gate(self, user_id: str = "local") -> dict[str, int]:
        if self._disabled:
            return {}
        counts = {}
        for gate in ("behavioral", "relational", "epistemic", "promissory", "correction"):
            result = self.client.count(
                collection_name=COLLECTION,
                count_filter=Filter(must=[
                    FieldCondition(key="type", match=MatchValue(value="memory")),
                    FieldCondition(key="user_id", match=MatchValue(value=user_id)),
                    FieldCondition(key="gate", match=MatchValue(value=gate)),
                ]),
                exact=True,
            )
            if result.count > 0:
                counts[gate] = result.count
        return counts

    def update_sensitivity(
        self, memory_id: str, sensitivity: str, reason: str | None, user_id: str = "local",
    ) -> None:
        if self._disabled:
            return
        points = self._scroll_all([
            FieldCondition(key="type", match=MatchValue(value="memory")),
            FieldCondition(key="memory_id", match=MatchValue(value=memory_id)),
            FieldCondition(key="user_id", match=MatchValue(value=user_id)),
        ], limit=1)
        if points:
            self.client.set_payload(
                collection_name=COLLECTION,
                payload={"sensitivity": sensitivity, "sensitivity_reason": reason},
                points=[points[0].id],
            )

    def list_memories_by_sensitivity(
        self, sensitivity: str | None, limit: int = 50, offset: int = 0, user_id: str = "local",
    ) -> list[Memory]:
        if self._disabled:
            return []
        conditions: list = [
            FieldCondition(key="type", match=MatchValue(value="memory")),
            FieldCondition(key="user_id", match=MatchValue(value=user_id)),
        ]
        if sensitivity is None:
            conditions.append(
                IsNullCondition(is_null=PayloadField(key="sensitivity"))
            )
        else:
            conditions.append(
                FieldCondition(key="sensitivity", match=MatchValue(value=sensitivity))
            )
        fetch_limit = offset + limit
        points = self._scroll_all(conditions, limit=fetch_limit, order_by="created")
        return [_memory_from_payload(p.payload) for p in points[offset:]]

    def count_by_sensitivity(self, user_id: str = "local") -> dict[str, int]:
        if self._disabled:
            return {}
        counts = {}
        for level in ("safe", "sensitive", "critical"):
            result = self.client.count(
                collection_name=COLLECTION,
                count_filter=Filter(must=[
                    FieldCondition(key="type", match=MatchValue(value="memory")),
                    FieldCondition(key="user_id", match=MatchValue(value=user_id)),
                    FieldCondition(key="sensitivity", match=MatchValue(value=level)),
                ]),
                exact=True,
            )
            if result.count > 0:
                counts[level] = result.count
        return counts

    def update_confidence(self, memory_id: str, confidence: float, user_id: str = "local") -> None:
        if self._disabled:
            return
        points = self._scroll_all([
            FieldCondition(key="type", match=MatchValue(value="memory")),
            FieldCondition(key="memory_id", match=MatchValue(value=memory_id)),
            FieldCondition(key="user_id", match=MatchValue(value=user_id)),
        ], limit=1)
        if points:
            self.client.set_payload(
                collection_name=COLLECTION,
                payload={"confidence": confidence},
                points=[points[0].id],
            )

    # ------------------------------------------------------------------ #
    #  Search                                                              #
    # ------------------------------------------------------------------ #

    def _build_memory_filter(
        self, user_id: str | None = None, team_id: str | None = None,
    ) -> Filter:
        """Build a filter for memory queries, optionally combining private + team."""
        must = [FieldCondition(key="type", match=MatchValue(value="memory"))]

        if user_id and team_id:
            # Combined: my private memories OR my team's shared memories
            return Filter(
                must=must,
                should=[
                    Filter(must=[
                        FieldCondition(key="user_id", match=MatchValue(value=user_id)),
                        FieldCondition(key="visibility", match=MatchValue(value="private")),
                    ]),
                    Filter(must=[
                        FieldCondition(key="team_id", match=MatchValue(value=team_id)),
                        FieldCondition(key="visibility", match=MatchValue(value="team")),
                    ]),
                ],
            )
        if user_id:
            must.append(FieldCondition(key="user_id", match=MatchValue(value=user_id)))
        return Filter(must=must)

    def search(
        self, query: str, limit: int = 5, user_id: str | None = None,
        team_id: str | None = None,
    ) -> list[tuple[str, float]]:
        if self._disabled:
            return []

        query_filter = self._build_memory_filter(user_id=user_id, team_id=team_id)

        if self._cloud:
            dense_query = self._jina_doc(query, task="retrieval.query")
            sparse_query = self._sparse_doc(query)
        else:
            dense_query = self._embed_local(query)
            sparse_query = self._query_sparse_local(query)

        prefetch_limit = max(limit * 4, 20)

        results = self.client.query_points(
            collection_name=COLLECTION,
            prefetch=[
                Prefetch(query=dense_query, using="dense", limit=prefetch_limit, filter=query_filter),
                Prefetch(query=sparse_query, using="sparse", limit=prefetch_limit, filter=query_filter),
            ],
            query=FusionQuery(fusion=Fusion.RRF),
            limit=limit,
            with_payload=True,
        )

        return [(p.payload.get("memory_id", ""), p.score) for p in results.points]

    def search_text(
        self, query: str, limit: int = 5, user_id: str | None = None,
        team_id: str | None = None,
    ) -> list[tuple[str, float]]:
        if self._disabled:
            return []
        base_filter = self._build_memory_filter(user_id=user_id, team_id=team_id)
        # Add text match to the must conditions
        text_cond = FieldCondition(key="content", match=MatchText(text=query))
        combined_must = list(base_filter.must or []) + [text_cond]
        scroll_filter = Filter(must=combined_must, should=base_filter.should)
        results, _ = self.client.scroll(
            collection_name=COLLECTION,
            scroll_filter=scroll_filter,
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )
        return [(p.payload.get("memory_id", ""), 1.0) for p in results]

    def search_fts(
        self, query: str, limit: int = 10, user_id: str = "local",
        team_id: str | None = None,
    ) -> list[Memory]:
        """Full-text search returning Memory objects (replaces SQLite FTS5)."""
        hits = self.search_text(query, limit=limit, user_id=user_id, team_id=team_id)
        results = []
        for mid, _ in hits:
            mem = self.get_memory(mid, user_id)
            if mem is None and team_id:
                # Try team lookup if private lookup failed
                mem = self.get_memory(mid, user_id=f"team:{team_id}")
            if mem:
                results.append(mem)
        return results

    def find_recent_in_context(
        self,
        exclude_id: str,
        cutoff: str,
        person: str | None,
        project: str | None,
        user_id: str = "local",
    ) -> str | None:
        """Find the most recent memory matching person/project since cutoff."""
        if self._disabled:
            return None
        conditions = [
            FieldCondition(key="type", match=MatchValue(value="memory")),
            FieldCondition(key="user_id", match=MatchValue(value=user_id)),
        ]
        if person:
            conditions.append(FieldCondition(key="person", match=MatchValue(value=person)))
        if project:
            conditions.append(FieldCondition(key="project", match=MatchValue(value=project)))

        # Parse ISO cutoff to timestamp
        try:
            cutoff_ts = datetime.fromisoformat(cutoff).timestamp()
            conditions.append(
                FieldCondition(key="created", range=Range(gte=cutoff_ts))
            )
        except (ValueError, TypeError):
            pass

        points = self._scroll_all(conditions, limit=10, order_by="created")
        for pt in points:
            mid = pt.payload.get("memory_id", "")
            if mid and mid != exclude_id:
                return mid
        return None

    # ------------------------------------------------------------------ #
    #  User migration                                                      #
    # ------------------------------------------------------------------ #

    def migrate_user_id(self, from_id: str, to_id: str) -> int:
        if self._disabled:
            return 0
        migrated = 0
        offset = None
        while True:
            results, offset = self.client.scroll(
                collection_name=COLLECTION,
                scroll_filter=Filter(must=[
                    FieldCondition(key="user_id", match=MatchValue(value=from_id))
                ]),
                limit=100,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            if not results:
                break
            point_ids = [p.id for p in results]
            self.client.set_payload(
                collection_name=COLLECTION,
                payload={"user_id": to_id},
                points=point_ids,
            )
            migrated += len(results)
            if offset is None:
                break
        return migrated

    # ------------------------------------------------------------------ #
    #  Delete (by filter)                                                  #
    # ------------------------------------------------------------------ #

    def delete(self, memory_id: str, user_id: str | None = None) -> None:
        if self._disabled:
            return
        conditions = [
            FieldCondition(key="memory_id", match=MatchValue(value=memory_id))
        ]
        if user_id:
            conditions.append(FieldCondition(key="user_id", match=MatchValue(value=user_id)))
        self.client.delete(
            collection_name=COLLECTION,
            points_selector=FilterSelector(filter=Filter(must=conditions)),
        )

    # ------------------------------------------------------------------ #
    #  Graph edges (inline payload arrays)                                 #
    # ------------------------------------------------------------------ #

    def add_edge(
        self, from_id: str, to_id: str, relation: str, user_id: str = "local",
    ) -> None:
        """Append an edge to the from_id memory's edges payload array."""
        if self._disabled:
            return
        points = self._scroll_all([
            FieldCondition(key="type", match=MatchValue(value="memory")),
            FieldCondition(key="memory_id", match=MatchValue(value=from_id)),
            FieldCondition(key="user_id", match=MatchValue(value=user_id)),
        ], limit=1)
        if not points:
            return
        pt = points[0]
        edges = pt.payload.get("edges") or []
        # Avoid duplicate edges
        for e in edges:
            if e.get("to") == to_id and e.get("relation") == relation:
                return
        edges.append({"to": to_id, "relation": relation})
        self.client.set_payload(
            collection_name=COLLECTION,
            payload={"edges": edges},
            points=[pt.id],
        )

    def find_related(
        self, memory_id: str, depth: int = 2, user_id: str = "local",
    ) -> list[dict]:
        """BFS traversal of inline edges up to `depth` hops.

        Returns list of dicts with keys: id, content, gate, relation, depth.
        """
        if self._disabled:
            return []

        visited: set[str] = {memory_id}
        results: list[dict] = []
        frontier = [memory_id]

        for d in range(1, depth + 1):
            next_frontier = []
            for mid in frontier:
                points = self._scroll_all([
                    FieldCondition(key="type", match=MatchValue(value="memory")),
                    FieldCondition(key="memory_id", match=MatchValue(value=mid)),
                    FieldCondition(key="user_id", match=MatchValue(value=user_id)),
                ], limit=1)
                if not points:
                    continue
                edges = points[0].payload.get("edges") or []
                for edge in edges:
                    target = edge.get("to", "")
                    if target in visited:
                        continue
                    visited.add(target)
                    next_frontier.append(target)
                    # Fetch target memory for result
                    target_pts = self._scroll_all([
                        FieldCondition(key="type", match=MatchValue(value="memory")),
                        FieldCondition(key="memory_id", match=MatchValue(value=target)),
                        FieldCondition(key="user_id", match=MatchValue(value=user_id)),
                    ], limit=1)
                    if target_pts:
                        tp = target_pts[0].payload
                        results.append({
                            "id": target,
                            "content": tp.get("content", ""),
                            "gate": tp.get("gate", ""),
                            "relation": edge.get("relation", ""),
                            "depth": d,
                        })
            frontier = next_frontier

        return results

    def auto_link(
        self, memory_id: str, person: str | None, project: str | None,
        user_id: str = "local",
    ) -> None:
        """Simplified auto_link: only creates CONTRADICTS/FOLLOWS edges.

        RELATED_TO edges are dropped. Same-person/project memories are
        implicitly related through payload filtering.
        """
        # No-op: CONTRADICTS and FOLLOWS edges are created explicitly
        # in remember.py. This method exists for API compatibility.
        pass

    # ------------------------------------------------------------------ #
    #  Journal                                                             #
    # ------------------------------------------------------------------ #

    def _journal_point_id(self, user_id: str, timestamp: float, content: str) -> int:
        key = f"journal:{user_id}:{timestamp}:{content[:50]}"
        return _stable_id(key)

    def insert_journal(self, entry: JournalEntry, user_id: str = "local") -> None:
        if self._disabled:
            return
        ts = entry.timestamp.timestamp()
        date_str = entry.timestamp.strftime("%Y-%m-%d")
        point_id = self._journal_point_id(user_id, ts, entry.content)
        payload = {
            "type": "journal",
            "user_id": user_id,
            "gate": entry.gate.value,
            "content": entry.content,
            "person": entry.person,
            "project": entry.project,
            "timestamp": ts,
            "date": date_str,
        }
        vector = self._make_vector(entry.content)
        self.client.upsert(
            collection_name=COLLECTION,
            points=[PointStruct(id=point_id, vector=vector, payload=payload)],
        )

    def insert_journal_raw(
        self,
        date: str,
        gate: Gate,
        content: str,
        person: str | None = None,
        project: str | None = None,
        user_id: str = "local",
    ) -> None:
        if self._disabled:
            return
        ts = time.time()
        point_id = self._journal_point_id(user_id, ts, content)
        payload = {
            "type": "journal",
            "user_id": user_id,
            "gate": gate.value,
            "content": content,
            "person": person,
            "project": project,
            "timestamp": ts,
            "date": date,
        }
        vector = self._make_vector(content)
        self.client.upsert(
            collection_name=COLLECTION,
            points=[PointStruct(id=point_id, vector=vector, payload=payload)],
        )

    def recent_journal(self, days: int = 3, user_id: str = "local") -> list[dict]:
        if self._disabled:
            return []
        limit = days * 20
        points = self._scroll_all(
            [
                FieldCondition(key="type", match=MatchValue(value="journal")),
                FieldCondition(key="user_id", match=MatchValue(value=user_id)),
            ],
            limit=limit,
            order_by="timestamp",
            order_direction="desc",
        )
        return [p.payload for p in points]

    def journal_by_date(self, date: str, user_id: str = "local") -> list[dict]:
        if self._disabled:
            return []
        points = self._scroll_all([
            FieldCondition(key="type", match=MatchValue(value="journal")),
            FieldCondition(key="user_id", match=MatchValue(value=user_id)),
            FieldCondition(key="date", match=MatchValue(value=date)),
        ], limit=500)
        return [p.payload for p in points]

    def latest_checkpoint(self, user_id: str = "local") -> dict | None:
        if self._disabled:
            return None
        points = self._scroll_all(
            [
                FieldCondition(key="type", match=MatchValue(value="journal")),
                FieldCondition(key="user_id", match=MatchValue(value=user_id)),
                FieldCondition(key="gate", match=MatchValue(value="checkpoint")),
            ],
            limit=1,
            order_by="timestamp",
            order_direction="desc",
        )
        if not points:
            return None
        return points[0].payload

    def stale_journal_dates(self, max_age_days: int = 14, user_id: str = "local") -> list[str]:
        if self._disabled:
            return []
        from datetime import timedelta
        cutoff_ts = (datetime.now(timezone.utc) - timedelta(days=max_age_days)).timestamp()
        points = self._scroll_all([
            FieldCondition(key="type", match=MatchValue(value="journal")),
            FieldCondition(key="user_id", match=MatchValue(value=user_id)),
            FieldCondition(key="timestamp", range=Range(lt=cutoff_ts)),
        ], limit=1000)
        dates = sorted({p.payload.get("date", "") for p in points if p.payload.get("date")})
        return dates

    def archive_journal_date(self, date: str, user_id: str = "local") -> None:
        if self._disabled:
            return
        self.client.delete(
            collection_name=COLLECTION,
            points_selector=FilterSelector(filter=Filter(must=[
                FieldCondition(key="type", match=MatchValue(value="journal")),
                FieldCondition(key="user_id", match=MatchValue(value=user_id)),
                FieldCondition(key="date", match=MatchValue(value=date)),
            ])),
        )

    # ------------------------------------------------------------------ #
    #  Identity                                                            #
    # ------------------------------------------------------------------ #

    def _identity_point_id(self, user_id: str) -> int:
        return _stable_id(f"identity:{user_id}")

    def get_identity(self, user_id: str = "local") -> IdentityCard | None:
        if self._disabled:
            return None
        points = self._scroll_all([
            FieldCondition(key="type", match=MatchValue(value="identity")),
            FieldCondition(key="user_id", match=MatchValue(value=user_id)),
        ], limit=1)
        if not points:
            return None
        p = points[0].payload
        last_updated = p.get("last_updated", 0)
        return IdentityCard(
            person=p.get("person"),
            project=p.get("project"),
            content=p.get("content", ""),
            last_updated=datetime.fromtimestamp(last_updated, tz=timezone.utc),
        )

    def set_identity(self, card: IdentityCard, user_id: str = "local") -> None:
        if self._disabled:
            return
        point_id = self._identity_point_id(user_id)
        payload = {
            "type": "identity",
            "user_id": user_id,
            "person": card.person,
            "project": card.project,
            "content": card.content,
            "last_updated": card.last_updated.timestamp(),
        }
        vector = self._make_vector(card.content)
        self.client.upsert(
            collection_name=COLLECTION,
            points=[PointStruct(id=point_id, vector=vector, payload=payload)],
        )

    # ------------------------------------------------------------------ #
    #  Rules                                                               #
    # ------------------------------------------------------------------ #

    def _rule_point_id(self, rule_id: str, user_id: str = "local") -> int:
        return _stable_id(f"rule:{user_id}:{rule_id}")

    def list_rules(self, user_id: str = "local") -> list[dict]:
        if self._disabled:
            return []
        points = self._scroll_all([
            FieldCondition(key="type", match=MatchValue(value="rule")),
            FieldCondition(key="user_id", match=MatchValue(value=user_id)),
        ], limit=100, order_by="created", order_direction="desc")
        return [
            {
                "id": p.payload.get("rule_id"),
                "user_id": p.payload.get("user_id"),
                "scope": p.payload.get("scope"),
                "condition": p.payload.get("condition"),
                "enforcement": p.payload.get("enforcement"),
                "created": p.payload.get("created"),
                "last_triggered": p.payload.get("last_triggered"),
            }
            for p in points
        ]

    def get_rule(self, rule_id: str, user_id: str = "local") -> dict | None:
        if self._disabled:
            return None
        points = self._scroll_all([
            FieldCondition(key="type", match=MatchValue(value="rule")),
            FieldCondition(key="rule_id", match=MatchValue(value=rule_id)),
            FieldCondition(key="user_id", match=MatchValue(value=user_id)),
        ], limit=1)
        if not points:
            return None
        p = points[0].payload
        return {
            "id": p.get("rule_id"),
            "user_id": p.get("user_id"),
            "scope": p.get("scope"),
            "condition": p.get("condition"),
            "enforcement": p.get("enforcement"),
            "created": p.get("created"),
            "last_triggered": p.get("last_triggered"),
        }

    def insert_rule(
        self, rule_id: str, user_id: str, scope: str,
        condition: str, enforcement: str = "suggest",
    ) -> None:
        if self._disabled:
            return
        now = time.time()
        point_id = self._rule_point_id(rule_id, user_id)
        content = f"{scope}: {condition} ({enforcement})"
        payload = {
            "type": "rule",
            "rule_id": rule_id,
            "user_id": user_id,
            "scope": scope,
            "condition": condition,
            "enforcement": enforcement,
            "created": now,
            "last_triggered": None,
            "content": content,
        }
        vector = self._make_vector(content)
        self.client.upsert(
            collection_name=COLLECTION,
            points=[PointStruct(id=point_id, vector=vector, payload=payload)],
        )

    def update_rule(self, rule_id: str, user_id: str = "local", **kwargs) -> bool:
        if self._disabled:
            return False
        allowed = {"scope", "condition", "enforcement"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return False
        points = self._scroll_all([
            FieldCondition(key="type", match=MatchValue(value="rule")),
            FieldCondition(key="rule_id", match=MatchValue(value=rule_id)),
            FieldCondition(key="user_id", match=MatchValue(value=user_id)),
        ], limit=1)
        if not points:
            return False
        self.client.set_payload(
            collection_name=COLLECTION,
            payload=updates,
            points=[points[0].id],
        )
        return True

    def delete_rule(self, rule_id: str, user_id: str = "local") -> bool:
        if self._disabled:
            return False
        points = self._scroll_all([
            FieldCondition(key="type", match=MatchValue(value="rule")),
            FieldCondition(key="rule_id", match=MatchValue(value=rule_id)),
            FieldCondition(key="user_id", match=MatchValue(value=user_id)),
        ], limit=1)
        if not points:
            return False
        self.client.delete(
            collection_name=COLLECTION,
            points_selector=FilterSelector(filter=Filter(must=[
                FieldCondition(key="type", match=MatchValue(value="rule")),
                FieldCondition(key="rule_id", match=MatchValue(value=rule_id)),
                FieldCondition(key="user_id", match=MatchValue(value=user_id)),
            ])),
        )
        return True

    def touch_rule(self, rule_id: str, user_id: str = "local") -> None:
        if self._disabled:
            return
        points = self._scroll_all([
            FieldCondition(key="type", match=MatchValue(value="rule")),
            FieldCondition(key="rule_id", match=MatchValue(value=rule_id)),
            FieldCondition(key="user_id", match=MatchValue(value=user_id)),
        ], limit=1)
        if points:
            self.client.set_payload(
                collection_name=COLLECTION,
                payload={"last_triggered": time.time()},
                points=[points[0].id],
            )
