# ARCHITECTURE — PROXIMA AI

Mermaid source-of-truth maps live in `docs/architecture/*.mmd` (rendered via Mermaid CLI in `make verify`). Summary:

- collector/data-plane: Node 22 + TypeScript, npm workspace `@proxima/collector` (`services/collector`); WB official API READ-only.
- control-plane: Python 3.14 (uv) in `services/control-plane` + `tools/`.
- Contracts: `contracts/*.schema.json` (canonical); TS types generated (`make codegen`) — never hand-edit generated files.
- DB: PostgreSQL 16 on staging VPS (135.106.186.210), dev via SSH tunnel 5433; migrations ordered immutable additive-only, ledger in `db/`.
- Provenance: immutable artifacts with SHA-256; imports from sibling worktrees only via allowlist with SHA-256.
- Agent layer: `docs/agent-system/` (role map in README.md); verify: `make verify` + `scripts/agent/*`.

Verify current state against `docs/archive/planning-m1/ROADMAP.md` before relying on this summary.
