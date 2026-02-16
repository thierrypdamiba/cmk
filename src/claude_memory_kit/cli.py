"""CLI entry point for Claude Memory Kit (CMK)."""

import asyncio
import json
import sys
import uuid

import click

from .cli_auth import get_user_id, get_team_id
from .config import get_store_path
from .store import Store


def _get_store() -> Store:
    store = Store(get_store_path())
    store.auth_db.migrate()
    store.qdrant.ensure_collection()
    return store


@click.group(invoke_without_command=True)
@click.pass_context
def main(ctx):
    """Claude Memory Kit. Persistent memory for Claude."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(mcp)


@main.command()
@click.argument("content")
@click.option("--gate", required=True, help="Write gate: behavioral, relational, epistemic, promissory, correction")
@click.option("--person", default=None, help="Person this memory is about")
@click.option("--project", default=None, help="Project context")
def remember(content, gate, person, project):
    """Store a new memory."""
    from .tools.remember import do_remember
    store = _get_store()
    result = asyncio.run(
        do_remember(store, content, gate, person, project, user_id=get_user_id())
    )
    click.echo(result)


@main.command()
@click.argument("query")
def recall(query):
    """Search memories."""
    from .tools.recall import do_recall
    store = _get_store()
    result = asyncio.run(do_recall(store, query, user_id=get_user_id()))
    click.echo(result)


@main.command()
def reflect():
    """Trigger memory consolidation."""
    from .tools.reflect import do_reflect
    store = _get_store()
    result = asyncio.run(do_reflect(store, user_id=get_user_id()))
    click.echo(result)


@main.command()
def identity():
    """Show identity card."""
    from .tools.identity import do_identity
    store = _get_store()
    result = asyncio.run(do_identity(store, user_id=get_user_id()))
    click.echo(result)


@main.command()
@click.argument("memory_id")
@click.option("--reason", required=True, help="Why to forget this memory")
def forget(memory_id, reason):
    """Forget a memory (archive with reason)."""
    from .tools.forget import do_forget
    store = _get_store()
    result = asyncio.run(
        do_forget(store, memory_id, reason, user_id=get_user_id())
    )
    click.echo(result)


@main.command()
def extract():
    """Extract memories from stdin transcript."""
    from .tools.auto_extract import do_auto_extract
    transcript = sys.stdin.read()
    if not transcript.strip():
        click.echo("No transcript provided on stdin.")
        return
    store = _get_store()
    result = asyncio.run(
        do_auto_extract(store, transcript, user_id=get_user_id())
    )
    click.echo(result)


@main.command()
@click.argument("message")
def prime(message):
    """Proactive recall from a message."""
    from .tools.prime import do_prime
    store = _get_store()
    result = asyncio.run(do_prime(store, message, user_id=get_user_id()))
    click.echo(result)


@main.command()
def scan():
    """Scan memories for PII and sensitive data patterns."""
    from .tools.scan import do_scan
    store = _get_store()
    result = asyncio.run(do_scan(store, user_id=get_user_id()))
    click.echo(result)


@main.command()
@click.option("--force", is_flag=True, help="Re-classify all memories, not just unclassified")
def classify(force):
    """Classify memories for sensitive content using Opus."""
    from .tools.classify import classify_memories
    store = _get_store()
    result = asyncio.run(
        classify_memories(store, user_id=get_user_id(), force=force)
    )
    click.echo(result)


@main.command()
@click.option("--port", default=7749, help="API server port")
def serve(port):
    """Start API server for dashboard."""
    import uvicorn
    uvicorn.run(
        "claude_memory_kit.api.app:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
    )


@main.command()
def mcp():
    """Start MCP server (stdio transport)."""
    from .server import run_server
    asyncio.run(run_server())


@main.command(name="flow-hook")
def flow_hook():
    """PostToolUse hook for Flow Mode. Reads stdin, compresses tool output."""
    from .flow.hook import run_flow_hook
    run_flow_hook()


@main.command()
def stats():
    """Show memory statistics."""
    store = _get_store()
    uid = get_user_id()
    total = store.qdrant.count_memories(user_id=uid)
    by_gate = store.qdrant.count_by_gate(user_id=uid)
    ident = store.qdrant.get_identity(user_id=uid)
    click.echo(f"Total memories: {total}")
    for gate, count in sorted(by_gate.items()):
        click.echo(f"  {gate}: {count}")
    if ident:
        click.echo(f"\nIdentity: {ident.person or 'unknown'}")
    else:
        click.echo("\nNo identity card yet.")


@main.command(name="init")
@click.argument("api_key")
def init_cmd(api_key):
    """Set up CMK with your API key from cmk.dev."""
    from .cli_auth import do_init
    do_init(api_key)


@main.command()
def claim():
    """Migrate local memories to your cloud account."""
    uid = get_user_id()
    if uid == "local":
        click.echo("Not logged in. Run 'cmk login' first.")
        return

    store = _get_store()
    local_counts = store.count_user_data("local")
    total = local_counts.get("total", 0)

    if total == 0:
        click.echo("No local data to claim.")
        return

    click.echo(f"Found {total} local items to migrate:")
    for table in ("memories", "journal", "edges", "archive"):
        count = local_counts.get(table, 0)
        if count > 0:
            click.echo(f"  {table}: {count}")

    if not click.confirm("Migrate all local data to your cloud account?"):
        click.echo("Cancelled.")
        return

    result = store.migrate_user_data("local", uid)
    click.echo("\nMigrated:")
    for key, count in result.items():
        if count > 0:
            click.echo(f"  {key}: {count}")
    click.echo("Done. Local data now belongs to your cloud account.")


@main.command(name="export")
def export_data():
    """Export cloud memories back to local storage."""
    uid = get_user_id()
    if uid == "local":
        click.echo("Not logged in. Nothing to export.")
        return

    store = _get_store()
    cloud_counts = store.count_user_data(uid)
    total = cloud_counts.get("total", 0)

    if total == 0:
        click.echo("No cloud data to export.")
        return

    click.echo(f"Found {total} cloud items to export to local:")
    for table in ("memories", "journal", "edges", "archive"):
        count = cloud_counts.get(table, 0)
        if count > 0:
            click.echo(f"  {table}: {count}")

    if not click.confirm("Copy all cloud data to local storage?"):
        click.echo("Cancelled.")
        return

    result = store.migrate_user_data(uid, "local")
    click.echo("\nExported:")
    for key, count in result.items():
        if count > 0:
            click.echo(f"  {key}: {count}")
    click.echo("Done. Cloud data copied to local mode.")


@main.command()
def login():
    """Sign in to CMK cloud. Opens browser for authentication."""
    from .cli_auth import do_login
    do_login()


@main.command()
def logout():
    """Sign out of CMK cloud. Removes stored credentials."""
    from .cli_auth import do_logout
    do_logout()


@main.command()
def whoami():
    """Show current authentication status."""
    from .cli_auth import do_whoami
    do_whoami()


# ---- Team commands ----

@main.group()
def team():
    """Manage team memory sharing."""
    pass


@team.command(name="create")
@click.argument("name")
def team_create(name):
    """Create a new team and become its owner."""
    uid = get_user_id()
    if uid == "local":
        click.echo("Not logged in. Run 'cmk init <api-key>' first.")
        return

    store = _get_store()
    team_id = f"team_{uuid.uuid4().hex[:8]}"
    team_info = store.auth_db.create_team(team_id, name, uid)

    # Save team_id to credentials
    from .cli_auth import load_credentials, _save_credentials
    creds = load_credentials() or {}
    creds["team_id"] = team_id
    _save_credentials(creds)

    click.echo(f"Created team '{name}' (id: {team_id})")
    click.echo(f"You are the owner. Share the team id with others to join.")
    click.echo(f"Team id saved to credentials.")


@team.command(name="join")
@click.argument("team_id")
def team_join(team_id):
    """Join an existing team."""
    uid = get_user_id()
    if uid == "local":
        click.echo("Not logged in. Run 'cmk init <api-key>' first.")
        return

    store = _get_store()
    team_info = store.auth_db.get_team(team_id)
    if not team_info:
        click.echo(f"Team '{team_id}' not found.")
        return

    if store.auth_db.is_team_member(team_id, uid):
        click.echo(f"Already a member of '{team_info['name']}'.")
    else:
        store.auth_db.add_team_member(team_id, uid, "member")
        click.echo(f"Joined team '{team_info['name']}'.")

    # Save team_id to credentials
    from .cli_auth import load_credentials, _save_credentials
    creds = load_credentials() or {}
    creds["team_id"] = team_id
    _save_credentials(creds)
    click.echo("Team id saved to credentials.")


@team.command(name="leave")
def team_leave():
    """Leave the current team."""
    uid = get_user_id()
    tid = get_team_id()
    if not tid:
        click.echo("Not in a team. Nothing to leave.")
        return

    store = _get_store()
    role = store.auth_db.get_member_role(tid, uid)
    if role == "owner":
        click.echo("You are the owner. Transfer ownership or delete the team instead.")
        return

    store.auth_db.remove_team_member(tid, uid)

    # Clear team_id from credentials
    from .cli_auth import load_credentials, _save_credentials
    creds = load_credentials() or {}
    creds.pop("team_id", None)
    _save_credentials(creds)

    click.echo("Left the team. Team id cleared from credentials.")


@team.command(name="members")
def team_members():
    """List members of the current team."""
    tid = get_team_id()
    if not tid:
        click.echo("Not in a team. Run 'cmk team join <id>' first.")
        return

    store = _get_store()
    team_info = store.auth_db.get_team(tid)
    if not team_info:
        click.echo(f"Team '{tid}' not found.")
        return

    members = store.auth_db.list_team_members(tid)
    click.echo(f"Team: {team_info['name']} ({tid})")
    click.echo(f"Members ({len(members)}):")
    for m in members:
        click.echo(f"  {m['user_id']} ({m['role']})")


@team.command(name="info")
def team_info():
    """Show current team details."""
    tid = get_team_id()
    if not tid:
        click.echo("Not in a team. Run 'cmk team join <id>' first.")
        return

    store = _get_store()
    info = store.auth_db.get_team(tid)
    if not info:
        click.echo(f"Team '{tid}' not found.")
        return

    members = store.auth_db.list_team_members(tid)
    mem_count = store.qdrant.count_memories(user_id=f"team:{tid}")

    click.echo(f"Team: {info['name']}")
    click.echo(f"ID: {tid}")
    click.echo(f"Created by: {info['created_by']}")
    click.echo(f"Members: {len(members)}")
    click.echo(f"Shared memories: {mem_count}")
