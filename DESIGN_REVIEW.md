# CMK Design Review

_Date: 2026-02-15_

## Scope

This review covers the current architecture and implementation across:

- Rust MCP server (`src/*.rs`)
- Python package, API server, and toolchain (`src/claude_memory_kit/*`)
- Dashboard client integration surface (`dashboard/src/lib/api.ts`)

Primary dimensions reviewed:

1. Product and system architecture
2. API/tool contract quality
3. Data model and storage topology
4. Reliability/performance concerns
5. Security and multi-tenant concerns
6. Operability and testing posture

---

## Executive Summary

CMK has a strong conceptual foundation (memory gates, tri-store retrieval, identity consolidation), but the implementation currently behaves like **two products in one repository** (Rust and Python) with drifting capabilities and contracts.

The most significant design risks are:

1. **Runtime/API drift between Rust and Python implementations** (different tools, gate enums, and argument semantics).
2. **A concrete API path regression in memory update re-embedding** in Python (`store.vectors.upsert(updated_mem)` call shape mismatch).
3. **String-formatted responses where structured payloads are expected**, limiting composability, ranking explainability, and client reliability.
4. **Blocking I/O patterns in async API paths** that can reduce throughput under concurrent use.
5. **Auth hardening gaps** (JWT audience/issuer constraints disabled and loose key discovery assumptions).

Recommended strategy: explicitly choose a **single canonical runtime** (likely Python today, based on breadth), define a versioned tool/API contract, and stage convergence work over 2–3 iterations.

---

## What Is Working Well

### 1) Clear product primitives

The model of `remember / recall / reflect / identity / forget / auto_extract` is coherent and easy to reason about. The memory-gate framing is also strong for behavior shaping and data quality.

### 2) Sensible hybrid retrieval direction

The FTS + vector + graph retrieval stack is directionally right for conversational memory, and both implementations preserve graceful degradation when optional systems are unavailable.

### 3) Local-first persistence and journaling semantics

Using local SQLite + markdown journaling allows inspectability and user trust. The journaling + identity regeneration concept is a product differentiator.

### 4) Practical cloud migration hooks

`claim`/`export` flow and user_id migration APIs are a good incremental bridge between local and cloud modes.

---

## Key Design Findings

## Critical

### C1. Dual runtime drift is now architectural debt, not just implementation detail

Symptoms observed:

- Rust server advertises 6 tools; Python MCP server advertises 7 (adds `prime`).
- Rust identity request type includes `person/project` but implementation ignores request fields.
- Gate models diverge (`correction` exists in Python, not Rust).
- Storage and migration behavior is significantly richer in Python.

Impact:

- Client expectations depend on runtime choice.
- Docs and behavior become nondeterministic.
- Every feature effort multiplies across stacks.

Recommendation:

- Declare one implementation as canonical.
- Put the non-canonical path in maintenance mode immediately.
- Add CI contract tests asserting tool names, request schema, and output envelope parity for any maintained runtimes.

### C2. API memory update path appears to call vector upsert with wrong signature

In the FastAPI `PATCH /api/memories/{id}` flow, `store.vectors.upsert(updated_mem)` does not match `VectorStore.upsert(memory_id, content, person, project, user_id=...)`.

Impact:

- Re-embedding on content edits likely fails at runtime.
- Search quality degrades silently after edits.

Recommendation:

- Fix call signature.
- Add a regression test covering memory update + subsequent vector recall.
- Add structured error handling around re-embed to prevent silent divergence.

## High

### H1. Contract outputs are mostly free-form strings

Tools and API endpoints return human-formatted text (e.g., recall results), not structured records.

Impact:

- Clients must parse prose.
- Ranking metadata and sources are hard to consume.
- Limits future features (faceted search, confidence display, deterministic UI rendering).

Recommendation:

- Define typed response schemas (`results[]`, `scores`, `source`, `trace`, `warnings`).
- Keep human-readable formatting as a derived presentation layer.

### H2. Async API handlers perform substantial sync DB work inline

FastAPI async endpoints call sync SQLite operations directly in many paths.

Impact:

- Event-loop blocking under concurrency.
- Reduced responsiveness when vector/graph operations are slow.

Recommendation:

- Move heavy sync operations to thread executors or use an async DB strategy.
- Bound concurrency for expensive retrieval fan-out.

### H3. Auth validation is functional but not fully hardened

JWT verification uses `verify_aud=False`, and key discovery relies on environment assumptions that are easy to misconfigure.

Impact:

- Increased risk of accepting tokens outside intended audience/issuer constraints.
- Operational fragility in deployment setups.

Recommendation:

- Enforce issuer/audience checks with explicit config.
- Validate and fail fast on incomplete Clerk configuration.
- Add security-focused integration tests.

## Medium

### M1. Schema evolution lacks explicit versioning discipline

Migrations are pragmatic but ad hoc (`ALTER TABLE ...` with exception swallowing).

Impact:

- Harder long-term confidence in upgrades and rollbacks.
- Hard to reason about partially migrated states.

Recommendation:

- Introduce migration versions and idempotent scripts with recorded schema version.

### M2. Store bootstrap logic is duplicated in multiple entry points

CLI, MCP server, and API all initialize store and vectors similarly.

Impact:

- Drift risk in setup behavior and future flags.

Recommendation:

- Centralize bootstrap factory and runtime configuration object.

### M3. Explainability and ranking calibration are under-specified

Tri-store retrieval merges results but lacks explicit ranking policy and trace semantics.

Impact:

- Hard to tune relevance and debug poor recalls.

Recommendation:

- Introduce a recall pipeline contract with per-source score normalization + debug trace.

### M4. Operational observability is minimal

Logging exists but no explicit metrics/tracing around latency, failure rates, retrieval source contribution, or auth outcomes.

Recommendation:

- Add counters/histograms around tool execution, search fan-out, and external dependency errors.

---

## Proposed Target Architecture

### A. Runtime strategy

- **Canonical runtime:** Python (`claude_memory_kit`) for now.
- Rust path options:
  - freeze (maintenance-only), or
  - re-scope to performance-critical subsystems behind FFI/service boundaries.

### B. API/tool contract strategy

- Publish a versioned contract (`v1`) for MCP tools and REST endpoints.
- All mutating calls return structured `result` envelopes with machine fields + optional human summary.
- Add capability negotiation metadata for optional features (`vectors`, `graph`, `cloud`).

### C. Retrieval architecture

- Separate retrieval execution from presentation:
  - `retrieve(query) -> RetrievalBundle`
  - `rank(bundle) -> RankedResults`
  - `render(rank) -> text or JSON`
- Keep graph expansion optional and bounded by latency budgets.

### D. Data lifecycle

- Explicit lifecycle states: active → decaying → consolidated → archived.
- Schema versioning and migration ledger in SQLite.
- Background maintenance jobs for consolidation and index consistency checks.

---

## 30/60/90 Day Plan

### 0–30 days (stabilization)

1. Choose canonical runtime and document status of the other.
2. Fix memory update re-embed call mismatch.
3. Add contract tests for tool list and gate enums.
4. Add structured response model for `recall` while preserving current string output as compatibility.

### 31–60 days (contract + reliability)

1. Introduce versioned API/tool schemas.
2. Move blocking DB work off async hot paths.
3. Add auth hardening (issuer/audience enforcement).
4. Add telemetry for tool latency and search source contribution.

### 61–90 days (scalability + product clarity)

1. Implement retrieval trace and score normalization.
2. Add migration version ledger and integrity checks.
3. Consolidate initialization/config paths.
4. Publish architecture doc and operator runbook.

---

## Suggested Design KPIs

- **Contract stability:** zero unplanned breaking changes per release.
- **Recall p95 latency:** target under 400ms local / 900ms cloud.
- **Update consistency:** 99.9% successful re-embed after content edits.
- **Auth rejection quality:** 100% expected failures for invalid aud/iss test cases.
- **Observability coverage:** latency + error metrics for all tools and API endpoints.

---

## Closing

CMK already has a compelling product shape. The core challenge now is not feature ideation—it is **architectural convergence and contract discipline**. If those are prioritized next, the system can scale from a powerful prototype into a durable platform with predictable behavior across clients and deployment modes.
