# Deep Code Review Findings

Date: 2026-02-15
Scope reviewed: Python API/auth/store core paths and supporting runtime checks.

## Executive Summary

I reviewed the core cloud/local backend paths (`api`, `auth`, `store`) and found **4 high-impact issues**:

1. **Full-text search index drift after updates** (stale search results).
2. **Auth can be enabled while JWT verification is impossible** (all JWT auth fails).
3. **Pinned state is write-only and never returned to clients** (feature appears broken).
4. **Local-data claim migration omits rules** (behavioral data loss after claim).

## Findings

### 1) Missing FTS update trigger causes stale search results
- **Severity:** High
- **Where:** `src/claude_memory_kit/store/sqlite.py`
- **Why it matters:** The FTS virtual table is maintained on `INSERT` and `DELETE`, but not `UPDATE`. Updating memory content leaves `memories_fts` stale, so recall/search can return outdated hits.
- **Code evidence:** `_ensure_fts()` defines `memories_ai` and `memories_ad` triggers only; no `AFTER UPDATE` trigger.
- **Runtime repro:**
  - Insert memory with content `hello world`.
  - Update same memory content to `goodbye moon`.
  - `search_fts('hello')` still returns memory; `search_fts('goodbye')` returns none.

### 2) Auth enablement can result in guaranteed JWT failure
- **Severity:** High
- **Where:** `src/claude_memory_kit/auth.py`
- **Why it matters:** `is_auth_enabled()` turns auth on when `CLERK_SECRET_KEY` is present, but `_get_jwks_url()` ignores that secret key and may return empty URL unless separate frontend env vars are set. In that state, JWT verification cannot start and every request requiring auth fails.
- **Code evidence:** `is_auth_enabled()` depends on `secret_key`; `_get_jwks_url()` only checks `CLERK_FRONTEND_API` or `CLERK_INSTANCE_ID`.
- **Runtime repro:** with only `CLERK_SECRET_KEY` set, `is_auth_enabled() == True` and `_get_jwks_url() == ''`.

### 3) Pin/unpin API state is not represented in returned models
- **Severity:** Medium
- **Where:** `src/claude_memory_kit/api/app.py`, `src/claude_memory_kit/store/sqlite.py`, `src/claude_memory_kit/types.py`
- **Why it matters:** API exposes pin/unpin endpoints and database writes to `pinned`, but `Memory` model lacks a `pinned` field and row mapping drops it. Clients cannot observe pinned state from memory reads/lists.
- **Code evidence:** `set_pinned()` writes DB column; `_row_to_memory()` omits `pinned`; `Memory` model has no `pinned`.
- **Runtime repro:** after calling `set_pinned(..., True)`, `get_memory(...).model_dump()` has no `pinned` key.

### 4) Local claim migration does not migrate rules
- **Severity:** Medium
- **Where:** `src/claude_memory_kit/store/sqlite.py`, `src/claude_memory_kit/api/app.py`
- **Why it matters:** `/api/claim-local` uses `migrate_user_data('local', uid)`, but migration updates only memories/journal/edges/archive/identity/onboarding. `rules` rows keep `user_id='local'`, so users lose access to their local rules after claim.
- **Code evidence:** `migrate_user_data()` table list excludes `rules`.
- **Runtime repro:** insert a local rule, run `migrate_user_data('local','u1')`; rule remains under local user.

## Recommendations

1. Add an `AFTER UPDATE` trigger for `memories_fts` (or rebuild/re-sync strategy) in `_ensure_fts()`.
2. Align auth gating with JWT configuration requirements:
   - either derive Clerk domain reliably from configured key(s), or
   - disable JWT mode unless required JWKS inputs are present, with explicit startup log/error.
3. Make pinning end-to-end:
   - add `pinned: bool = False` to `Memory`,
   - include column in row mapping and list/get responses,
   - migrate schema deterministically in `migrate()` instead of lazy `ALTER TABLE` in request path.
4. Extend local claim migration to include `rules` (and evaluate whether API keys or vector payload data also need explicit ownership migration semantics).
