# RULES — PROXIMA AI

English distillation of the binding rules. Canonical Russian source: `AGENTS.md` sections «Жёсткие запреты», «Конвенции кода», «Рабочий ритм`.

## MUST (violation = revert)

- No secrets in Git, configs, logs, alerts, prompts. Tokens live on the VPS (`/etc/proxima-ai/secrets/`, mode 0600); `.env` stays outside Git (path-only).
- WB WRITE is forbidden. READ endpoints only; any mutating WB operation is an architectural violation.
- Torgstat live session automation is forbidden (adapter structurally unwired; no runtime flag can enable it).
- Never mutate sibling worktrees `Опрос-v2.2` (baseline `9cca25d1`) and `torgstat-collector` (baseline `610169a6`). Import only via allowlist with SHA-256.
- No fabricated data: no fictional cabinet IDs, SKU, prices, thresholds. Tests use structural fixtures with anonymized values.
- LLM never computes metrics (M2 code): numbers come from deterministic code; every fact carries a SourceRef; reviewers BLOCK unsupported claims.
- Destructive ops (`rm -rf`, `git push --force`, `drop table`, `reset --hard`) require explicit Mike confirmation.
- Migrations: ordered, immutable, additive-only (STATE.md B6 doctrine); ledger in `db/`.
- Generated TS contract types (`services/collector/src/contracts/`) are never hand-edited — regenerate via `make codegen`.
- Python runs via `uv` (3.14), never the system Python 3.9.
- Every vertical slice ends with a clean implementation commit that passed `make verify`. Critical phases 3, 4, 7 additionally require independent cross-model review with 0 blocker / 0 warning.
- Never `git add -A` / `git add .` — stage explicitly. Never push without instruction. The tree carries foreign dirty files (see HANDOFF).

## SHOULD (default behavior)

- Startup sequence and routing table from `AGENTS.md` before any non-trivial task.
- One main active task per repo; new main task only after previous is DONE / BLOCKED / re-prioritized by Mike.
- Atomic, descriptive conventional commits (`fix: WB diagnostic YoY margin calc`, not `update`).
- Update `docs/agent-system/HANDOFF.md` + `TASKS.md` at every state change of the active task.
- Unknown fact → write `UNKNOWN`; never guess metrics, dates, Jira keys.
- Read a file before changing it; route to `.planning/STATE.md` instead of duplicating its content.
- Raw evidence stays immutable, content-addressed, outside Git.

## MAY (allowed variants)

- Communication/docs in Russian (project default); agent-system docs in English.
- Fast gate (`scripts/agent/verify`) for agent-level verification vs full `make verify` gate — both are legitimate; full gate is canonical for slice completion.
- Local DB access either via SSH tunnel to staging VPS or restricted Postgres MCP (both read-oriented).

---

Covers: secrets handling, production changes, migrations, dependency changes, git workflow (no force push, explicit staging), testing requirements, review/release procedure (phase gates, Data GO / Live Deploy GO as separate Mike decisions).
