<p align="center">
  <img src="dashboard/cmk-logo-512.png" alt="CMK" width="120" />
</p>

<h1 align="center">claude-memory-kit</h1>

<p align="center">
  Cloud-synced, multi-tenant memory for Claude Code.<br>
  Hybrid search. Privacy controls. 4 tools. Zero config.
</p>

<p align="center">
  <a href="https://pypi.org/project/claude-memory-kit/"><img src="https://img.shields.io/pypi/v/claude-memory-kit" alt="PyPI"></a>
  <a href="https://pypi.org/project/claude-memory-kit/"><img src="https://img.shields.io/pypi/pyversions/claude-memory-kit" alt="Python"></a>
  <a href="https://github.com/thierrypdamiba/claude-memory-kit/blob/main/LICENSE"><img src="https://img.shields.io/github/license/thierrypdamiba/claude-memory-kit" alt="License"></a>
</p>

## why this one

There are dozens of memory MCP servers. Most store everything in local SQLite with no sync, no privacy controls, and 20+ tools that bloat your context window.

CMK is different:

- **Cloud-native sync**: memories live in Qdrant Cloud, not local files. Switch devices, start a new session, your memory is already there.
- **Team memory**: share knowledge across your team. Private by default, opt-in shared. Combined recall searches both personal and team memories. No other memory MCP does this.
- **Multi-tenant**: `user_id` with `is_tenant=true` at the Qdrant engine level. One cluster, many users, full data isolation.
- **Privacy-first**: automatic sensitivity classification (safe/sensitive/critical) and PII scanning for API keys, SSNs, JWTs, credit cards. Most tools just dump everything with zero awareness.
- **4 tools, not 24**: Claude works better with fewer tools. Less context pollution, less decision paralysis. Every tool earns its place.
- **Hybrid search**: dense vectors + sparse vectors (BM25) + full-text fallback, fused with Reciprocal Rank Fusion. Not just keyword matching, not just embeddings.

## install

```bash
uv tool install claude-memory-kit
```

Or with pip:

```bash
pip install claude-memory-kit
```

## setup

Add to your Claude Code MCP config (`~/.claude/mcp.json`):

```json
{
  "mcpServers": {
    "claude-memory-kit": {
      "command": "cmk"
    }
  }
}
```

Set your environment variables:

```bash
# required for cloud sync
QDRANT_URL=<your-cluster-url>
QDRANT_API_KEY=<your-key>

# required for LLM features (classification, consolidation, identity)
ANTHROPIC_API_KEY=<your-api-key>
```

That's it. Claude will automatically save and recall memories across sessions.

## tools

4 tools exposed to Claude:

| Tool | What it does |
|---|---|
| `remember_this` | Store something worth remembering. Gate, person, project, and sensitivity are auto-classified. Set `visibility="team"` to share with your team. |
| `recall_memories` | Hybrid search across memories (semantic + keyword + graph traversal). |
| `forget_memory` | Remove a memory by ID with a reason. |
| `save_checkpoint` | Snapshot current session context for continuity across sessions. |

Claude calls `remember_this` proactively when it learns something worth keeping (preferences, corrections, commitments, facts about people). No manual intervention needed.

## features

### search

- **Dense + sparse vectors**: FastEmbed embeddings + BM25 sparse vectors, combined with Reciprocal Rank Fusion
- **Full-text fallback**: Qdrant text index search kicks in when vector search returns nothing
- **Graph traversal**: CONTRADICTS and FOLLOWS edges between memories, traversed at recall time

### classification

- **Write gates**: behavioral, relational, epistemic, promissory, correction (auto-classified per memory)
- **Sensitivity classification**: Opus-powered privacy detection (safe/sensitive/critical)
- **PII scanning**: regex-based detection for API keys, SSNs, credit cards, JWTs, and more

### lifecycle

- **Memory decay**: configurable half-life per gate type (30d/90d/180d/never), automatic cleanup on reflect
- **Journal consolidation**: old session entries compressed into weekly digests via LLM
- **Identity card**: auto-generated summary of who Claude is working with, regenerated on reflect
- **Session checkpoints**: structured snapshots loaded at session start for continuity

### team memory

- **Private by default**: all memories are private unless you explicitly set `visibility="team"`
- **Combined recall**: searches both your private memories and your team's shared memories in a single query
- **Team rules**: admins can set team-wide rules that apply to all members
- **Permission model**: owner, admin, member roles. Only admins+ can create team rules or invite members.
- **CLI management**: `cmk team create`, `cmk team join`, `cmk team leave`, `cmk team members`, `cmk team info`

### flow mode (experimental)

Extend Claude Code sessions by compressing tool output in real time. When enabled, a PostToolUse hook intercepts large tool outputs (>2000 chars), compresses them to ~500 tokens using Haiku, and replaces the original in the transcript. Compressed observations are stored in Qdrant for cross-session search.

- **Opt-in**: set `CMK_FLOW_MODE=true` to enable. Zero overhead when disabled.
- **Haiku compression**: fast (2-5s per tool use), cheap ($0.02-0.05 per session)
- **Fail-open**: any error exits silently. Never breaks your session.
- **Persistent observations**: compressed outputs stored as journal entries, searchable via `recall_memories`
- **Context injection**: recent observations loaded into MCP server instructions at session start

Enable it:

```bash
export CMK_FLOW_MODE=true
```

Optional tuning:

```bash
# Change compression threshold (default: 2000 chars)
export CMK_FLOW_THRESHOLD=3000

# Skip additional tools (comma-separated, extends defaults)
export CMK_FLOW_SKIP_TOOLS=mcp__my-server__my_tool
```

### multi-tenancy

- **Qdrant-level tenant isolation**: `user_id` indexed with `is_tenant=true`, queries only touch that tenant's data segments
- **Auth stack**: Clerk JWT auth + API keys for the dashboard API
- **Per-user data**: every query is scoped to the authenticated user. No cross-tenant leakage.

## dashboard

CMK includes a web dashboard for managing memories:

```bash
cmk serve --port 7749
```

```bash
cd dashboard
pnpm install && pnpm dev
```

Timeline view, search, identity management, rules, API keys, and a privacy review page.

## cli

```bash
# save and search
cmk remember "user prefers dark mode" --gate behavioral
cmk recall "dark mode"

# teams
cmk team create "My Team"    # create team, you become owner
cmk team join team_abc123    # join existing team
cmk team members             # list team members
cmk team info                # show team details
cmk team leave               # leave current team

# maintenance
cmk scan           # PII scan across all memories
cmk classify       # Opus sensitivity classification
cmk classify --force  # re-classify all
cmk reflect        # consolidate old entries + run decay
cmk stats          # storage and memory statistics
cmk serve          # start API server for dashboard
```

## architecture

v0.3.0 uses Qdrant as the single source of truth for all memory data. SQLite is only used for server-side auth tables (users, API keys, teams).

All point types live in one `cmk_memories` collection, discriminated by a `type` field:

```
cmk_memories (Qdrant collection)
├── type="memory"    user memories with full metadata, vectors, edges
├── type="journal"   session entries and checkpoints
├── type="identity"  identity cards
└── type="rule"      user-defined rules
```

Each point carries dense + sparse vectors for hybrid search, plus a full payload with all metadata. The `user_id` field is a tenant key, so Qdrant optimizes storage and routing per user.

## roadmap

**Tiered memory architecture** (inspired by [qdrant-agentic-memory](https://github.com/thierrypdamiba/qdrant-agentic-memory) workshop patterns):

```
Working Memory ──────> Episodic Memory ──────> Semantic Memory
   (session)              (commit)            (consolidation)
                              │
                              v
                         Meta Memory
                         (reflection)
```

- **Working memory**: volatile session buffer. Current context, compressed observations, auto-expires at session end.
- **Episodic memory**: past session transcripts stored as journal entries. Time-bound, searchable by date and content.
- **Semantic memory**: durable knowledge extracted from episodes via consolidation. Facts, preferences, patterns that survive decay.
- **Meta memory**: reflections and insights about the user generated during reflect cycles.

Currently, CMK has the building blocks (journal consolidation, decay classes, identity regeneration, checkpoints). The next step is formalizing these into explicit tiers with promotion/demotion between them.

**Other planned work**:

- Migration script for v0.1.x SQLite users (`cmk migrate`)
- Background consolidation jobs (scheduled reflect cycles)
- Benchmarks: recall accuracy, search latency, token efficiency vs context-window-only baselines
- Plugin system for custom extractors and gates

## environment

```bash
# required for cloud sync
QDRANT_URL=<your-cluster-url>
QDRANT_API_KEY=<your-key>

# required for LLM features (classification, consolidation, identity)
ANTHROPIC_API_KEY=<your-api-key>

# optional: custom storage path (for auth DB)
MEMORY_STORE_PATH=~/.claude-memory

# optional: team memory
CMK_TEAM_ID=<your-team-id>
```

See `.env.example` for all options.

## license

MIT
