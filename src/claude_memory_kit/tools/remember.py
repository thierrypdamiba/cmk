import logging
import uuid
from datetime import datetime, timedelta, timezone

from ..store import Store
from ..types import DecayClass, Gate, JournalEntry, Memory
from ._pii import check_pii

log = logging.getLogger("cmk")


async def do_remember(
    store: Store,
    content: str,
    gate_str: str,
    person: str | None = None,
    project: str | None = None,
    user_id: str = "local",
    visibility: str = "private",
    team_id: str | None = None,
) -> str:
    gate = Gate.from_str(gate_str)
    if gate is None:
        return (
            f"invalid gate '{gate_str}'. "
            "use: behavioral, relational, epistemic, promissory, correction"
        )

    now = datetime.now(timezone.utc)
    mem_id = f"mem_{now.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}"

    memory = Memory(
        id=mem_id,
        created=now,
        gate=gate,
        person=person,
        project=project,
        confidence=0.9,
        last_accessed=now,
        access_count=1,
        decay_class=DecayClass.from_gate(gate),
        content=content,
    )

    # 1. Journal entry
    entry = JournalEntry(
        timestamp=now,
        gate=gate,
        content=content,
        person=person,
        project=project,
    )
    store.qdrant.insert_journal(entry, user_id=user_id)

    # 2. Insert memory (full metadata in Qdrant payload)
    if visibility == "team" and not team_id:
        return "Cannot save team memory: no team configured. Run 'cmk team join <id>' first."
    store.qdrant.insert_memory(
        memory, user_id=user_id,
        visibility=visibility if visibility != "private" else None,
        team_id=team_id if visibility == "team" else None,
        created_by=user_id if visibility == "team" else None,
    )

    # 3. Auto-link (no-op in cloud-only mode)
    store.qdrant.auto_link(mem_id, person, project, user_id=user_id)

    # 4. Contradiction check via vectors
    warning = ""
    try:
        similar = store.qdrant.search(content, limit=3, user_id=user_id, team_id=team_id)
        for sid, score in similar:
            if sid != mem_id and score > 0.85:
                existing = store.qdrant.get_memory(sid, user_id=user_id)
                if existing and existing.content != content:
                    warning = (
                        f"\n\nwarning: high similarity (score={score:.2f}) "
                        f"with existing memory [{sid}]. "
                        "possible contradiction or duplicate."
                    )
                    break
    except Exception as e:
        log.warning("contradiction check failed: %s", e)

    # 5. Correction gate: create CONTRADICTS edge, downgrade old
    if gate == Gate.correction:
        try:
            similar = store.qdrant.search(content, limit=1, user_id=user_id)
            for sid, score in similar:
                if sid != mem_id and score > 0.5:
                    store.qdrant.add_edge(
                        mem_id, sid, "CONTRADICTS", user_id=user_id
                    )
                    old = store.qdrant.get_memory(sid, user_id=user_id)
                    if old:
                        store.qdrant.update_confidence(
                            sid, old.confidence * 0.5, user_id=user_id
                        )
        except Exception as e:
            log.warning("correction handling failed: %s", e)

    # 6. Memory chains: FOLLOWS edge for same person+project within 24h
    if person or project:
        try:
            cutoff = (now - timedelta(hours=24)).isoformat()
            recent_id = store.qdrant.find_recent_in_context(
                exclude_id=mem_id, cutoff=cutoff,
                person=person, project=project, user_id=user_id,
            )
            if recent_id:
                store.qdrant.add_edge(
                    mem_id, recent_id, "FOLLOWS", user_id=user_id
                )
        except Exception as e:
            log.warning("memory chain failed: %s", e)

    # 7. PII detection
    pii_warning = check_pii(content)
    if pii_warning:
        warning += f"\n\nWARNING: {pii_warning}"

    # 8. Opus sensitivity classification
    try:
        from ..config import get_api_key
        api_key = get_api_key()
        if api_key:
            from .classify import classify_single
            classification = await classify_single(store, mem_id, user_id)
            level = classification.get("level", "unknown")
            if level not in ("safe", "unknown"):
                warning += (
                    f"\n\nSENSITIVITY: {level} "
                    f"({classification.get('reason', '')})"
                )
    except Exception as e:
        log.warning("sensitivity classification failed: %s", e)

    preview = content[:80] if len(content) > 80 else content
    return f"Remembered [{gate.value}]: {preview} (id: {mem_id}){warning}"
