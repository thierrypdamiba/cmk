import logging

from ..store import Store

log = logging.getLogger("cmk")


async def do_forget(
    store: Store, memory_id: str, reason: str,
    user_id: str = "local", team_id: str | None = None,
) -> str:
    # Try private namespace first
    memory = store.qdrant.delete_memory(memory_id, user_id=user_id)

    # If not found and team_id is set, try team namespace
    if memory is None and team_id:
        # Look up the memory to check creator before deleting
        team_mem = store.qdrant.get_memory(memory_id, user_id=f"team:{team_id}")
        if team_mem:
            created_by = getattr(team_mem, "created_by", None)
            if created_by and created_by != user_id:
                # Check if caller is team admin/owner
                role = store.auth_db.get_member_role(team_id, user_id)
                if role not in ("owner", "admin"):
                    return (
                        f"Cannot delete team memory {memory_id}: "
                        "only the creator or a team admin can delete it."
                    )
            memory = store.qdrant.delete_memory(
                memory_id, user_id=f"team:{team_id}",
            )

    if memory is None:
        return f"No memory found with id: {memory_id}"

    return f"Forgotten: {memory_id} (reason: {reason})."
