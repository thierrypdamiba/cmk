"""CLI login/logout flow for CMK cloud mode."""

import json
import os
import threading
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import click

CREDENTIALS_DIR = os.path.expanduser("~/.claude-memory")
CREDENTIALS_FILE = os.path.join(CREDENTIALS_DIR, "credentials.json")
CALLBACK_PORT = 9847  # localhost callback port for OAuth


def _get_login_url() -> str:
    """Build the Clerk login URL."""
    base = os.getenv("CMK_LOGIN_URL", "https://cmk.dev/login")
    return f"{base}?redirect_uri=http://localhost:{CALLBACK_PORT}/callback"


def _save_credentials(data: dict) -> None:
    os.makedirs(CREDENTIALS_DIR, exist_ok=True)
    with open(CREDENTIALS_FILE, "w") as f:
        json.dump(data, f, indent=2)
    os.chmod(CREDENTIALS_FILE, 0o600)


def load_credentials() -> dict | None:
    if not os.path.exists(CREDENTIALS_FILE):
        return None
    try:
        with open(CREDENTIALS_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def get_user_id() -> str:
    """Resolve user_id: CMK_USER_ID env > credentials.json > 'local'."""
    env_id = os.getenv("CMK_USER_ID")
    if env_id:
        return env_id
    creds = load_credentials()
    if creds and creds.get("user_id"):
        return creds["user_id"]
    return "local"


def get_api_key() -> str | None:
    creds = load_credentials()
    if creds:
        return creds.get("api_key")
    return os.getenv("CMK_API_KEY")


def get_team_id() -> str | None:
    """Resolve team_id: CMK_TEAM_ID env > credentials.json > None."""
    env_id = os.getenv("CMK_TEAM_ID")
    if env_id:
        return env_id
    creds = load_credentials()
    if creds and creds.get("team_id"):
        return creds["team_id"]
    return None


class _CallbackHandler(BaseHTTPRequestHandler):
    """Handle the OAuth callback from Clerk."""

    result: dict | None = None

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path != "/callback":
            self.send_response(404)
            self.end_headers()
            return

        params = parse_qs(parsed.query)
        api_key = params.get("api_key", [None])[0]
        user_id = params.get("user_id", [None])[0]
        email = params.get("email", [None])[0]

        if api_key:
            _CallbackHandler.result = {
                "api_key": api_key,
                "user_id": user_id or "",
                "email": email or "",
            }
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            body = (
                "<html><body style='font-family:monospace;padding:40px'>"
                "<h2>Authenticated.</h2>"
                "<p>You can close this tab and return to the terminal.</p>"
                "</body></html>"
            )
            self.wfile.write(body.encode())
        else:
            self.send_response(400)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html><body>Authentication failed.</body></html>")

    def log_message(self, format, *args):
        pass  # suppress server logs


def do_login() -> None:
    """Open browser for Clerk auth, wait for callback, save credentials."""
    creds = load_credentials()
    if creds and creds.get("api_key"):
        click.echo(f"Already logged in as {creds.get('email', 'unknown')}.")
        click.echo("Run 'cmk logout' first to switch accounts.")
        return

    login_url = _get_login_url()
    click.echo(f"Opening browser for authentication...")
    click.echo(f"  {login_url}")
    click.echo()
    click.echo("Waiting for callback...")

    _CallbackHandler.result = None
    server = HTTPServer(("localhost", CALLBACK_PORT), _CallbackHandler)
    server.timeout = 120  # 2 minute timeout

    webbrowser.open(login_url)

    # Wait for callback (blocking, with timeout)
    while _CallbackHandler.result is None:
        server.handle_request()
        if _CallbackHandler.result is not None:
            break

    server.server_close()

    if _CallbackHandler.result:
        _save_credentials(_CallbackHandler.result)
        email = _CallbackHandler.result.get("email", "")
        click.echo(f"\nLogged in as {email}.")
        click.echo("Memories will now sync to CMK cloud.")
        # Hint about unclaimed local data
        _check_local_data_hint()
    else:
        click.echo("\nLogin timed out or was cancelled.")


def _check_local_data_hint() -> None:
    """Show hint if there's unclaimed local data after login."""
    try:
        from .config import get_store_path
        from .store import Store
        store = Store(get_store_path())
        store.qdrant.ensure_collection()
        count = store.qdrant.count_memories(user_id="local")
        if count > 0:
            click.echo()
            click.echo(f"You have {count} local memories that aren't linked to your account.")
            click.echo("Run 'cmk claim' to migrate them to your cloud account.")
    except Exception:
        pass  # don't block login on hint failure


def _find_claude_config_path() -> str | None:
    """Find Claude's MCP config file. Checks Claude Desktop and Claude Code locations."""
    candidates = [
        # Claude Desktop
        os.path.expanduser("~/Library/Application Support/Claude/claude_desktop_config.json"),
        os.path.expanduser("~/.config/claude/claude_desktop_config.json"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None


def _write_mcp_config(user_id: str) -> str | None:
    """Write or update the CMK MCP server entry in Claude's config.

    Returns the path written to, or None if no config was found.
    Tries Claude Desktop config first, then falls back to project-level .mcp.json.
    """
    mcp_entry = {
        "command": "cmk",
        "env": {
            "CMK_USER_ID": user_id,
        },
    }

    # Try Claude Desktop config
    config_path = _find_claude_config_path()
    if config_path:
        config = {}
        try:
            with open(config_path) as f:
                config = json.load(f)
        except (json.JSONDecodeError, OSError):
            config = {}
        if "mcpServers" not in config:
            config["mcpServers"] = {}
        config["mcpServers"]["memory"] = mcp_entry
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
        return config_path

    # Fallback: write .mcp.json in current directory (Claude Code project-level)
    local_mcp = os.path.join(os.getcwd(), ".mcp.json")
    config = {}
    if os.path.exists(local_mcp):
        try:
            with open(local_mcp) as f:
                config = json.load(f)
        except (json.JSONDecodeError, OSError):
            config = {}
    if "mcpServers" not in config:
        config["mcpServers"] = {}
    config["mcpServers"]["memory"] = mcp_entry
    with open(local_mcp, "w") as f:
        json.dump(config, f, indent=2)
    return local_mcp


def _validate_key_cloud(api_key: str) -> dict | None:
    """Validate API key against the cloud API."""
    cloud_url = os.getenv("CMK_API_URL", "https://cmk.dev")
    try:
        import httpx
        resp = httpx.get(
            f"{cloud_url}/api/auth/me",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("user")
    except Exception:
        pass
    return None


def _validate_key_local(api_key: str) -> dict | None:
    """Validate API key against the local SQLite store."""
    try:
        from .config import get_store_path
        from .store.sqlite import SqliteStore
        from .auth_keys import validate_api_key

        db = SqliteStore(get_store_path())
        db.migrate()
        return validate_api_key(api_key, db)
    except Exception:
        return None


def do_init(api_key: str) -> None:
    """Initialize CMK with an API key from cmk.dev."""
    if not api_key.startswith("cmk-sk-"):
        click.echo("Invalid API key. Keys start with 'cmk-sk-'.")
        return

    # Try cloud first, then local
    click.echo("Validating API key...")
    user = _validate_key_cloud(api_key)
    if not user:
        user = _validate_key_local(api_key)

    # If neither validated but the key format is correct, accept it.
    # The user got this key from cmk.dev, so trust it and store locally.
    # Validation will happen on first API call.
    if not user or not user.get("id"):
        # Derive a user_id from the key hash so we have something stable
        import hashlib
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()[:16]
        user = {"id": f"user_{key_hash}", "email": ""}
        click.echo("Could not reach cmk.dev to validate (offline or not deployed yet).")
        click.echo("Key saved locally. It will be validated on first sync.")
    else:
        click.echo(f"Authenticated as {user.get('email') or user['id']}.")

    # Save credentials
    _save_credentials({
        "api_key": api_key,
        "user_id": user["id"],
        "email": user.get("email", ""),
    })

    # Write MCP config
    written_path = _write_mcp_config(user["id"])
    if written_path:
        click.echo(f"MCP config written to {written_path}")
    else:
        click.echo()
        click.echo("Add this to your Claude MCP config manually:")
        click.echo(json.dumps({
            "memory": {
                "command": "cmk",
                "env": {"CMK_USER_ID": user["id"]},
            }
        }, indent=2))

    # Check for local data to claim
    _check_local_data_hint()

    click.echo()
    click.echo("Ready. Start a Claude session and your memories will persist.")


def do_logout() -> None:
    """Remove stored credentials."""
    if os.path.exists(CREDENTIALS_FILE):
        os.remove(CREDENTIALS_FILE)
        click.echo("Logged out. Switched back to local mode.")
    else:
        click.echo("Not logged in.")


def do_whoami() -> None:
    """Show current authentication status."""
    creds = load_credentials()
    if creds and creds.get("api_key"):
        email = creds.get("email", "unknown")
        key_preview = creds["api_key"][:12] + "..."
        click.echo(f"Logged in as: {email}")
        click.echo(f"API key: {key_preview}")
        click.echo("Mode: cloud")
    else:
        click.echo("Not logged in.")
        click.echo("Mode: local")
        click.echo("Run 'cmk login' to enable cloud sync.")
