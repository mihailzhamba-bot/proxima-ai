# MEMORY — PROXIMA AI

> Stable, useful, project-specific knowledge only. Every entry: date + evidence.

## Project specifics

- Monorepo: npm workspace `@proxima/collector` (TypeScript, Node >=22 <23) + uv-managed Python 3.14 control-plane; canonical JSON Schemas in `contracts/*.schema.json`; migration ledger in `db/` (evidence: repo layout, 2026-08-16).
- Test layout: TS tests in `services/collector/tests/`; Python tests in `services/control-plane/tests` + `tools/tests` (evidence: Makefile `test` target).
- Jira PA is the task tracker; epics PA-34 (Track D, frozen until V3), PA-35 (Track C), PA-36 (Track A / M1), PA-37 (Track B) (evidence: `.planning/STATE.md`, 2026-08-16).

## Commands that unexpectedly matter

- `make verify` — the single canonical gate (install + codegen + typecheck + tests + contracts + migrations + provenance + architecture + boundary + secrets + vps + business-signal).
- `make codegen` — regenerates TS contract types; required after any `contracts/*.schema.json` change.
- `make collect-wb-analytics` — async WB report probe against the prepared VPS runtime (`--tenant-id amirova-test --period latest-closed-week`).
- `make probe-wb-api` — Day-1 API proof with the five split read-only tokens.
- `make apply-migrations` — applies the migration ledger via `.env` (VPS/tunnel).

## Constraints & pitfalls

- No local Docker: DB dev via SSH tunnel `ssh -N -L 5433:localhost:5432 proxima-admin@135.106.186.210` (Mike decision 2026-08-16, AGENTS.md).
- Python: always `uv` (3.14); system Python is 3.9 and must not be used (AGENTS.md toolchain table).
- Selectel VPS filters default `api.telegram.org`; the host pins it to `149.154.167.220` in `/etc/hosts` (backup `/etc/hosts.bak-2026-08-15`). If Telegram delivery fails, re-test the pin first (README.md, 2026-08-15).
- WB test Analytics token may be read-write; while so, the documented `--allow-analytics-read-write` flag must be passed (README.md).
- Official WB XLSX bytes stay outside Git; tests use synthetic structural fixtures only (STATE.md todos).
- `package-lock.json` / `Makefile` / `README.md` etc. carry foreign uncommitted changes as of 2026-08-16 — never stage blindly (HANDOFF "Dirty-tree note").

## User preferences (stable)

- Communication and `.planning/` docs in Russian; code identifiers in English (AGENTS.md).
- Atomic descriptive conventional commits; clean implementation commit per vertical slice (AGENTS.md).
- Weekly product sync with Mike across tracks (decision #49, STATE.md).

## Recurring agent mistakes

- None recorded yet (file created 2026-08-16). Add an entry + a guardrail each time a mistake repeats.
