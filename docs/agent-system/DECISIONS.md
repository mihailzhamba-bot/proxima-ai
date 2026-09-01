# DECISIONS — PROXIMA AI

> Agent-relevant engineering decisions. The canonical, complete decision log (product + process, Russian) lives in `STATE.md` (корень) — this file only records decisions an agent must not reopen or accidentally revert, with pointers.

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
Status: accepted; superseded by DEC-006 (2026-08-17) in the LLM-runtime / client-facing-UI part only — every other clause remains in force

### Context
M1 is a provenance-safe data foundation; write operations and fragile browser automation are out of scope.

### Decision
WB access is READ-endpoints only; Torgstat adapter stays structurally unwired; LLM runtime, Ozon, WB Advertising and client-facing UI are deferred beyond M1.

### Consequences
Any mutating WB operation or Torgstat session automation = architectural violation (revert).

## DEC-006 — LLM runtime and client-facing UI permitted outside the M1 contour

Date: 2026-08-17 (Mike; audit finding 2026-08-17, Jira PMM-30)
Status: accepted

### Context
DEC-005 deferred LLM runtime, Ozon, WB Advertising and client-facing UI beyond M1. The whole W1 slice is exactly that (PMM-5, PMM-25 = LLM runtime; PMM-24, PMM-27 = client-facing UI), so executing W1 under DEC-005 as written would be an architectural violation subject to revert. Mike resolved the conflict on 2026-08-17 by a new decision on top of DEC-005, not by rewording DEC-005.

### Decision
LLM runtime and client-facing web-UI are allowed outside the M1 contour. This supersedes DEC-005 in the LLM-runtime and client-facing-UI part only, and applies when all three conditions hold simultaneously:

1. only staging data of the pilot cabinet is used;
2. every output carries the mandatory trust marker `unreleased`;
3. the production release pointer does not move.

WB Advertising API is not opened by this decision: it is required by W2 (SCN-007), not W1, and remains deferred.

Everything else DEC-005 prohibits stays in force unchanged: any WB WRITE, Ozon, Torgstat live session automation.

### Consequences
DEC-005 is superseded in the LLM/UI part only; do not widen this decision to anything else. Reviewer must not qualify W1 LLM-runtime / client-facing-UI work (PMM-5, PMM-24, PMM-25, PMM-27) as an architectural violation while the three conditions above hold; any WB WRITE, Ozon or Torgstat session automation remains an architectural violation (revert). Opening WB WRITE requires its own gates after a stable M2 (PRODUCT-VISION §4).

## DEC-007 — tax_regime is a legal-entity attribute; contribution formula branches on it

Date: 2026-08-17 (Jira PMM-2, SPIKE AIOS-FIN-001)
Status: draft (full ADR `docs/adr/0001-tax-regime-contribution.md`; becomes accepted after legal-entity inventory from Mike and accountant confirmation of rates)

### Context
Portfolio of 4+ legal entities (source: Mike, Jira PMM-2 description, 2026-08-17; exact count UNKNOWN until inventory) with mixed tax regimes (USN income / USN income-expenses / OSNO). Contribution formulas differ fundamentally per regime; `tax_regime: mixed` would defer the decision until unit economics is already written for one scenario. Since 2025, USN entities above 60M RUB/year also pay VAT, so regime and VAT status are two independent dimensions.

### Decision
`tax_regime` (usn_income | usn_income_expenses | osno | unknown) is an attribute of `legal_entity` in the canonical model; each WB cabinet maps to exactly one legal entity; the contribution calculation selects the formula by this attribute. Default is `unknown` (never `mixed`); while unknown, profit estimates are UNKNOWN (fail-closed) and revenue estimates (PMM-22 v1) still work. `vat_status` is a separate legal-entity attribute. Full formulas per regime, inventory table (to be filled by Mike), revisit conditions and open questions Q1-Q4: see the ADR.

### Consequences
Do not implement profit-based ₽-estimates against a guessed regime; do not introduce `tax_regime: mixed` anywhere. Profit v2 of PMM-22 starts only after the ADR reaches `accepted`. Elimination of inter-company resale is explicitly out of scope (per-entity calculation only in W1).

---

Numbering: increment, never reuse. Supersede instead of deleting. Product/strategy decisions (web-first, pricing, tracks, gates V1-V3) → see `STATE.md` (корень) and `docs/archive/planning-m1/PRODUCT-VISION.md`; do not duplicate them here.
