# claude-memory-kit

Persistent memory for Claude. MCP server with hybrid search (dense + sparse vectors, RRF fusion), cloud sync via Qdrant, and automatic sensitivity classification.

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
    "memory": {
      "command": "cmk"
    }
  }
}
```

That's it. Claude will automatically save and recall memories across sessions.

## how it works

4 tools exposed to Claude:

- **remember_this**: store something worth remembering. Gate, person, project, and sensitivity are auto-classified.
- **recall_memories**: hybrid search across memories (semantic + keyword + graph traversal).
- **forget_memory**: remove a memory by ID with a reason.
- **save_checkpoint**: snapshot current session context for continuity across sessions.

Claude calls `remember_this` proactively when it learns something worth keeping (preferences, corrections, commitments, facts about people). No manual intervention needed.

## features

- **Cloud sync**: all memories stored in Qdrant Cloud payloads, synced across devices and sessions
- **Hybrid search**: dense vectors (fastembed/Jina) + sparse vectors (BM25) with Reciprocal Rank Fusion
- **Full-text fallback**: Qdrant text index search when vector search returns nothing
- **Write gates**: behavioral, relational, epistemic, promissory, correction (auto-classified)
- **Memory decay**: configurable half-life per gate type, automatic cleanup
- **Graph edges**: CONTRADICTS and FOLLOWS edges inlined as Qdrant payload arrays
- **Session checkpoints**: structured snapshots loaded at session start for continuity
- **Sensitivity classification**: Opus-powered privacy detection (safe/sensitive/critical)
- **PII scanning**: regex-based detection for API keys, SSNs, credit cards, JWTs, etc.
- **Identity card**: auto-generated summary of who Claude is working with
- **Journal consolidation**: automatic compression of old entries into weekly digests

## dashboard

CMK includes a web dashboard for managing memories:

```bash
cmk serve --port 7749
```

Then build and run the dashboard (Next.js):

```bash
cd dashboard
pnpm install && pnpm dev
```

Dashboard features: timeline view, search, identity management, rules, API keys, and a privacy review page.

## cli

```bash
# save and search
cmk remember "user prefers dark mode" --gate behavioral
cmk recall "dark mode"

# maintenance
cmk scan
cmk classify
cmk classify --force
cmk reflect
cmk stats
cmk serve
```

| Command | Description |
|---|---|
| `cmk remember` | Store a memory with auto-classification |
| `cmk recall` | Search memories |
| `cmk scan` | PII scan across all memories |
| `cmk classify` | Opus sensitivity classification |
| `cmk classify --force` | Re-classify all memories |
| `cmk reflect` | Consolidate old entries + run decay |
| `cmk stats` | Storage and memory statistics |
| `cmk serve` | Start the API server |

## environment

```bash
# required for cloud sync
QDRANT_URL=<your-cluster-url>
QDRANT_API_KEY=<your-key>

# required for LLM features (classification, consolidation, identity)
ANTHROPIC_API_KEY=<your-api-key>

# optional: custom storage path (for local fallback and auth DB)
MEMORY_STORE_PATH=~/.claude-memory
```

See `.env.example` for all options.

## architecture

v0.2.0 uses Qdrant as the single source of truth for all memory data. SQLite is only used for server-side auth tables (users, API keys). All point types live in one `cmk_memories` collection, discriminated by a `type` field:

- `type="memory"`: user memories with full metadata
- `type="journal"`: session journal entries and checkpoints
- `type="identity"`: identity cards
- `type="rule"`: user-defined rules

## license

MIT
