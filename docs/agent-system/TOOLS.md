# TOOLS — PROXIMA AI

> Per tool: purpose, access, safe operations, dangerous operations, verification.

## Make / npm workspace (build & test)

Purpose: all build, codegen, test and verify entry points.
Access: `Makefile` (root), `package.json` + `services/collector/package.json`.
Safe operations: `make verify`, `make codegen`, `make typecheck`, `make test`, `make contracts`, `make migrations`, `make provenance`, `make architecture`, `make boundary`, `make secrets`, `make vps`, `make business-signal`, `npm run typecheck`, `npm test`, `npm run build`.
Dangerous operations: none inherent; `make install` (`npm ci`) rewrites `node_modules` and can touch `package-lock.json` — avoid while foreign dirty files exist.
Verification: exit code 0; `scripts/agent/verify` for the fast subset.

## uv / Python 3.14 (control-plane, tools)

Purpose: Python runtime for control-plane and `tools/` verifiers/probes.
Access: `uv` on PATH; project `services/control-plane` with `--extra test`.
Safe operations: `uv run --python 3.14 ... pytest ...`, verifiers under `tools/`.
Dangerous operations: running with system Python 3.9 (forbidden); `uv sync` without `--locked` can drift the lockfile.
Verification: pytest green (48 passed, 1 skipped @ 2026-08-16).

## PostgreSQL 16 (staging VPS via tunnel / MCP)

Purpose: normalized facts, domain releases, provenance.
Access: SSH tunnel `ssh -N proxima-db` (alias; long form `ssh -N -L 5433:localhost:5432 proxima-admin@135.106.186.210`), then `DATABASE_URI` env var (never commit values). Postgres MCP Pro (restricted, read-only) for Claude Code.
Safe operations: read-only queries; `make apply-migrations` on staging per runbook.
Dangerous operations: `drop table`, data deletion, writes to immutable evidence tables, pointing production release pointers by hand — all require explicit Mike approval.
Verification: `make migrations`; query results carry provenance refs.

## Wildberries API (official, READ-only)

Purpose: official evidence intake (statistics, analytics, finance, prices, promotion).
Access: five split read-only personal tokens on the VPS at `/etc/proxima-ai/secrets/wb_*_token` (mode 0600); probes via `make probe-wb-api`, `make collect-wb-analytics`.
Safe operations: READ endpoints via the documented probes; rate-limit headers persisted as raw evidence.
Dangerous operations: ANY WB WRITE endpoint (forbidden); printing token values; putting tokens in `.env` values, shell history or Git.
Verification: probe receipts + SHA-256 content-addressed responses under `/srv/proxima-ai/data/`.

## Staging VPS (Selectel, 135.106.186.210)

Purpose: single-VPS M1 deployment boundary; Postgres + monitor.
Access: SSH alias `proxima` (user `proxima-admin`, key `~/.ssh/id_ed25519_proxima_selectel_20260813`, passphrase in macOS Keychain); bootstrap via `infra/bootstrap/bootstrap-vps.sh` (already executed). Root login is permanently disabled — `ssh root@…` can never work. `IdentitiesOnly yes` is mandatory (server `MaxAuthTries 3`).
Safe operations: reading state (`/var/lib/proxima-ai-monitor/state.json`), monitor timer checks, `bash infra/ssh-doctor` (read-only access diagnostics).
Dangerous operations: resize/paid changes (monitor never does them automatically), firewall changes beyond TCP/22, secrets rotation — require explicit Mike approval. Re-running `bootstrap-vps.sh` OVERWRITES `authorized_keys` (`bootstrap-vps.sh:109`) — never use it to "repair" access.
Verification: `make vps`; `bash infra/ssh-doctor`; Telegram delivery test (note `/etc/hosts` pin, see MEMORY).

## Jira PA (tracker)

Purpose: primary task tracker (epics PA-34/35/36/37).
Access: zhamba.atlassian.net via jira MCP.
Safe operations: read/browse; comment/transitions per normal workflow.
Dangerous operations: none code-level; do not create parallel tracking outside PA.
Verification: task keys referenced in TASKS.md exist.

## Sibling source worktrees (Опрос-v2.2, torgstat-collector)

Purpose: import sources only.
Access: paths recorded in `.planning/STATE.md` "Source Boundaries" with pinned baselines.
Safe operations: read; import via explicit allowlist + relative path + SHA-256.
Dangerous operations: any mutation, stash, clean or commit inside those worktrees — forbidden.
Verification: baseline hashes `9cca25d1` / `610169a6` unchanged.

---

Rules: never log or commit credentials; rate limits and quotas are real costs; prefer read-only access until a change is approved.
