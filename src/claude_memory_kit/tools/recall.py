import asyncio
import logging

from ..store import Store

log = logging.getLogger("cmk")


async def do_recall(
    store: Store, query: str, user_id: str = "local",
    team_id: str | None = None,
) -> str:
    results = []
    seen_ids: set[str] = set()

    def _source_tag(mem) -> str:
        """Return [team] or [private] prefix for team-enabled recall."""
        if not team_id:
            return ""
        if getattr(mem, "visibility", "private") == "team":
            return "[team] "
        return "[private] "

    def _get_memory(mem_id):
        """Look up memory by id, trying private then team namespace."""
        mem = store.qdrant.get_memory(mem_id, user_id=user_id)
        if mem is None and team_id:
            mem = store.qdrant.get_memory(mem_id, user_id=f"team:{team_id}")
        return mem

    # 1. Hybrid search (dense + sparse with RRF fusion) via Qdrant
    try:
        vec_results = await asyncio.to_thread(
            store.qdrant.search, query, 10, user_id, team_id
        )
        for mem_id, score in vec_results:
            if mem_id not in seen_ids:
                seen_ids.add(mem_id)
                full = _get_memory(mem_id)
                if full:
                    store.qdrant.touch_memory(mem_id, user_id=user_id)
                    person = full.person or "?"
                    tag = _source_tag(full)
                    results.append(
                        f"{tag}[{full.gate.value}, score={score:.2f}] "
                        f"({full.created:%Y-%m-%d}, {person}) "
                        f"{full.content}\n  id: {full.id}"
                    )
    except Exception as e:
        log.warning("hybrid search failed: %s", e)

    # 2. Text search fallback when hybrid returned nothing
    if not results and not store.qdrant._disabled:
        try:
            text_results = await asyncio.to_thread(
                store.qdrant.search_text, query, 5, user_id, team_id
            )
            for mem_id, score in text_results:
                if mem_id not in seen_ids:
                    seen_ids.add(mem_id)
                    full = _get_memory(mem_id)
                    if full:
                        store.qdrant.touch_memory(mem_id, user_id=user_id)
                        person = full.person or "?"
                        tag = _source_tag(full)
                        results.append(
                            f"{tag}[{full.gate.value}, text] "
                            f"({full.created:%Y-%m-%d}, {person}) "
                            f"{full.content}\n  id: {full.id}"
                        )
        except Exception as e:
            log.warning("text search failed: %s", e)

    # 3. Graph traversal for sparse results
    if len(results) < 3:
        for mid in list(seen_ids)[:2]:
            related = store.qdrant.find_related(
                mid, depth=2, user_id=user_id
            )
            for rel in related:
                rid = rel["id"]
                if rid not in seen_ids:
                    seen_ids.add(rid)
                    preview = rel.get("content", "")[:80]
                    results.append(
                        f"[graph: {rel['relation']}] "
                        f"{preview} (id: {rid})"
                    )

    if not results:
        return "No memories found matching that query."

    return f"Found {len(results)} memories:\n\n" + "\n\n".join(results)
