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

### Status update 2026-08-17
Partially superseded by DEC-006 for LLM runtime and client-facing UI **outside the M1 contour**. Everything else in DEC-005 stands unchanged.

## DEC-006 — LLM runtime and client-facing web UI allowed outside the M1 contour

Date: 2026-08-17 (Mike)
Status: accepted; supersedes DEC-005 in part (LLM runtime, client-facing UI)
Tracker: PMM-30

### Context
The M2 slice (Jira project PMM) is built on an LLM analyst plus an independent reviewer and a web Decision Inbox — exactly what DEC-005 defers beyond M1. No PMM issue lifted that decision, so every M2 task was formally an architectural violation with a revert consequence. Found by the backlog audit 2026-08-17.

### Decision
LLM runtime and client-facing web UI are permitted outside the M1 contour when all three conditions hold at once:

1. staging data only (pilot cabinet), never production release data;
2. every client-facing output carries the `unreleased` trust marking;
3. the production release pointer does not move.

Still forbidden, unchanged from DEC-005: any WB WRITE operation, Ozon APIs, WB Advertising API, Torgstat live session automation. Advertising is needed by wave W2 and requires its own separate decision — this one does not open it.

### Consequences
Work on PMM-5, PMM-24, PMM-25, PMM-27 is no longer a DEC-005 violation. Reviewers must check the three conditions instead of blocking LLM runtime outright. If any condition is dropped, the work falls back under DEC-005 and is revertible.

---

Numbering: increment, never reuse. Supersede instead of deleting. Product/strategy decisions (web-first, pricing, tracks, gates V1-V3) → see `.planning/STATE.md` and `.planning/PRODUCT-VISION.md`; do not duplicate them here.
