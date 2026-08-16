# DECISIONS — PROXIMA AI

> Agent-relevant engineering decisions. The canonical, complete decision log (product + process, Russian) lives in `.planning/STATE.md` — this file only records decisions an agent must not reopen or accidentally revert, with pointers.

## DEC-001 — TypeScript contract types are generated, never hand-written

Date: 2026-08-16 (closed as decision A1 in STATE.md)
Status: accepted

### Context
Phase 2 needed TS types for the canonical `contracts/*.schema.json` schemas without drift.

### Decision
`make codegen` (json-schema-to-typescript) generates types into `services/collector/src/contracts/`; the runtime-boundary gate distinguishes generated vs hand-written code. Part of the `make verify` chain.

### Consequences
Never hand-edit `services/collector/src/contracts/`; schema changes require a codegen run.

## DEC-002 — Migrations are ordered, immutable, additive-only

Date: recorded in STATE.md as open item B6; doctrine referenced by AGENTS.md
Status: accepted (doctrine); full ADR due at Phase 3 planning

### Context
PostgreSQL schema evolution must never break immutable provenance history.

### Decision
Additive-only ordered migrations with a ledger in `db/`; no destructive or editing migrations.

### Consequences
Removing/changing a shipped migration is forbidden; write a new one instead.

## DEC-003 — No local Docker; DB dev via SSH tunnel to staging VPS

Date: 2026-08-16
Status: accepted

### Context
No Docker on the local machine (Mike's environment).

### Decision
Dev DB cycle goes through an SSH tunnel to the staging Selectel VPS (`135.106.186.210`, Postgres 16); Postgres MCP (restricted, read-only) uses the same `DATABASE_URI`.

### Consequences
Local full-stack runs are limited; tests are designed to run without a live DB where possible.

## DEC-004 — Independent cross-model review only for critical phases 3, 4, 7

Date: 2026-08-12 (Mike)
Status: accepted

### Context
Full 0-blocker/0-warning reviews for every phase were too expensive.

### Decision
Cross-model review `0 blocker / 0 warning` is mandatory for phases 3, 4, 7; other phases need `make verify` + CI + self-review recorded in EVIDENCE.md.

### Consequences
Do not demand or block on cross-model review for non-critical phases; do not skip it for 3/4/7.

## DEC-005 — Read-only M1 boundary: WB WRITE and Torgstat live automation excluded

Date: carried from Phase 1 architecture decisions (STATE.md)
Status: accepted

### Context
M1 is a provenance-safe data foundation; write operations and fragile browser automation are out of scope.

### Decision
WB access is READ-endpoints only; Torgstat adapter stays structurally unwired; LLM runtime, Ozon, WB Advertising and client-facing UI are deferred beyond M1.

### Consequences
Any mutating WB operation or Torgstat session automation = architectural violation (revert).

---

Numbering: increment, never reuse. Supersede instead of deleting. Product/strategy decisions (web-first, pricing, tracks, gates V1-V3) → see `.planning/STATE.md` and `.planning/PRODUCT-VISION.md`; do not duplicate them here.
