# TOOLS — PROXIMA AI

> Per tool: purpose, access, safe operations, dangerous operations, verification.

## Make / npm workspace (build & test)

Purpose: all build, codegen, test and verify entry points.
Access: `Makefile` (root), `package.json` + `services/collector/package.json`.
Safe operations: `make verify` and any single target of its chain. The chain itself is the `verify:` line of the root `Makefile` — read it there, not here; on 2026-09-08 it is install, codegen, codegen-diff, typecheck, webapp-lint, test, contracts, migrations, pg-roundtrip, provenance, architecture, boundary, secrets, vps, business-signal, wb-client, brief, wb-async-report, funnel, funnel-csv, nm-daily, detector, signals-ranking, live-network. Outside the chain: `make agent-toolset`, `make webapp-build`, `make test-db-refresh`, `npm run typecheck`, `npm test`, `npm run build`.
`make ci-parity` is the isolated Docker/PostgreSQL manual CI analogue (D37); it is outside `verify`, supports `--dry-run`/`--only`/`--port`/`--keep`, and does not build images.
Dangerous operations: none inherent; `make install` (`npm ci`) rewrites `node_modules` and can touch `package-lock.json` — avoid while foreign dirty files exist — and its `hooks` prerequisite sets `core.hooksPath=.githooks` in the local clone, so the pre-commit hook becomes active after the first `make verify`.
Verification: exit code 0; `pg-roundtrip: SKIP` instead of `PASS` means no local PostgreSQL 16 `initdb` was found and the migrations were not replayed against a real cluster (`tools/pg_local_roundtrip.sh:17-31`); `scripts/agent/verify` for the fast subset. `PUPPETEER_SKIP_DOWNLOAD=1` before `npm ci` / `make verify`, and `TMPDIR=/tmp` when the checkout path is long (AGENTS.md).

## uv / Python 3.14 (control-plane, tools)

Purpose: Python runtime for control-plane and `tools/` verifiers/probes.
Access: `uv` on PATH; project `services/control-plane` with `--extra test`.
Safe operations: `uv run --python 3.14 ... pytest ...`, verifiers under `tools/`.
Dangerous operations: running with system Python 3.9 (forbidden); `uv sync` without `--locked` can drift the lockfile.
Verification: pytest green inside `make test` — 448 passed, 23 skipped on 2026-09-08 (the skips need a live PostgreSQL); `uv run pytest` from the repository root fails with `Failed to spawn: pytest`, always pass `--project services/control-plane --extra test`.

## PostgreSQL 16 (VPS via tunnel / MCP / container wrappers)

Purpose: normalized facts, domain releases, provenance.
Access: SSH tunnel `ssh -N proxima-db` (alias; long form `ssh -N -L 5433:localhost:5432 proxima-admin@135.106.186.210`), then `DATABASE_URI` env var (never commit values). Postgres MCP Pro (restricted, read-only) for Claude Code. On the server SQL goes through root wrappers over the production container, both sourced from the repository: `infra/bootstrap/proxima-psql-readonly` (role `proxima_diagnostics`, SQL on stdin only) and `infra/bootstrap/proxima-psql-owner` (owner psql, used by `provision-runtime-roles.sh --psql`); the release operator installs them into `/usr/local/sbin/` and the password never leaves the container.
Safe operations: read-only queries; role provisioning `infra/bootstrap/provision-runtime-roles.sh` and the read-only analyst role `infra/bootstrap/provision-analyst-role.sh` (prints secret file paths only — `docs/operations/access-provisioning.md`). Applying the ledger in a release: `docker compose --profile jobs run --rm control-plane-admin make apply-migrations ENV_FILE=infra/jobs.env` from `/srv/proxima-ai/repo` (`docs/operations/release-m01.md` §2; owner secrets live only in that service, AD-15) — the host `make apply-migrations` form reads the repo-root `.env` and is for the dev tunnel.
Dangerous operations: `drop table`, data deletion, writes to immutable evidence tables, pointing production release pointers by hand — all require explicit Mike approval.
Verification: `make migrations`, plus `make pg-roundtrip` where a local PostgreSQL 16 exists; query results carry provenance refs.

## OpenHands test database sandbox

Purpose: give the agent a complete, writable copy of production-shaped data without access to the main `proxima` database.
Access: provision creates `proxima_sandbox_uri`; copy `infra/openhands/env.task.template` to `.env.task`, set the provisioned tenant id, and keep the URI in `/etc/proxima-ai/secrets/proxima_sandbox_uri` (0600). The hook loads `DATABASE_URI` from that file and rejects a configured URI that does not target `proxima_test`.
Safe operations: `PROXIMA_TENANT_ID=<tenant> make test-db-refresh`; reads and writes through `DATABASE_URI` affect only `proxima_test`.
Dangerous operations: refresh terminates sessions and drops/recreates `proxima_test`; never override `PROXIMA_TEST_DATABASE` with `proxima` and never grant `proxima_sandbox` CONNECT to the main database. The script rejects identical main/test names.
Verification: `PROXIMA_TENANT_ID=<tenant> make test-db-refresh` ends with `test-db-refresh: PASS (proxima_test refreshed; sandbox granted only on copy)` (`tools/test_db_refresh.sh:60`); credentials come from the ordinary libpq environment, never from the script. The target is **not** part of the `make verify` chain — run it separately. The zone stop hook `.openhands/hooks/verify-gate.sh` runs `make verify` and, when `.env.task` exists, denies a `DATABASE_URI` that does not target `proxima_test`.

## Wildberries API (official, READ-only)

Purpose: official evidence intake (statistics, analytics, finance, prices, promotion).
Access: split read-only personal tokens as files in `/etc/proxima-ai/secrets/` (mode 0600, owner `1010:1010` after the release). The naming scheme is `<tenant>_wb_<category>_token` (AD-13) — the form `infra/compose.yaml` and `infra/jobs.env` expect (`amirova-test_wb_statistics_token`, `amirova-test_wb_analytics_token`), delivered into containers as `/run/secrets/<name>` through compose `secrets:`. On the server the files still carry the pre-AD-13 names and there are three of them (`wb_analytics_token`, `wb_finance_token`, `wb_statistics_token` — `docs/state/RELEASE-READINESS-1.14.md` §5, 08.09.2026); the rename happens on release day in `docs/operations/release-m01.md` §1.2. `wb_prices_token` and `wb_promotion_token` do not exist on the VPS (`docs/state/INVENTORY.md:217`, PA-15), so `make probe-wb-api`, which requires all five Day-1 categories (`tools/wb_api_probe.py`), cannot run there. Probes: `make probe-wb-api`, `make collect-wb-analytics`.
Safe operations: READ endpoints via the documented probes; rate-limit headers persisted as raw evidence.
Dangerous operations: ANY WB WRITE endpoint (forbidden); printing token values; putting tokens in `.env` values, shell history or Git.
Verification: probe receipts + SHA-256 content-addressed responses under `PROXIMA_RAW_DIR` — `/srv/proxima-ai/raw` in the release contour (`infra/compose.yaml`, `infra/jobs.env`, runbook §1.3, `0700` owned by `1010`); the old Day-1 host path `/srv/proxima-ai/data/day1-wb-api` survives only in `infra/runtime.env.template` and is dropped by runbook §1.1 because CAS needs a `0700` directory the container user can enter. Live WB calls additionally need `WB_ALLOW_LIVE_NETWORK=1`, set only on the `collector` job service (AD-4; gate `make live-network`).

## Staging VPS (Selectel, 135.106.186.210)

Purpose: single-VPS M1 deployment boundary; Postgres + monitor.
Access: SSH alias `proxima` (user `proxima-admin`, key `~/.ssh/id_ed25519_proxima_selectel_20260813`, passphrase in macOS Keychain); bootstrap via `infra/bootstrap/bootstrap-vps.sh` (already executed). Root login is permanently disabled — `ssh root@…` can never work. `IdentitiesOnly yes` is mandatory (server `MaxAuthTries 3`).
Safe operations: reading state (`/var/lib/proxima-ai-monitor/state.json`), monitor timer checks, `bash infra/ssh-doctor` (read-only access diagnostics).
Dangerous operations: resize/paid changes (monitor never does them automatically), firewall changes beyond TCP/22, secrets rotation — require explicit Mike approval. Re-running `bootstrap-vps.sh` OVERWRITES `authorized_keys` (`bootstrap-vps.sh:109`) — never use it to "repair" access. Installing or replacing units — including the nightly backup pair `infra/systemd/proxima-pg-backup.{service,timer}` (03:00 Europe/Moscow, `OnFailure=proxima-alert@`), which must replace `/etc/cron.d/proxima-pg-backup` rather than run beside it — happens only after Mike says «деплой»; the procedure is `docs/operations/release-m01.md` §5 «Бэкап как юнит».
Verification: `make vps`; `bash infra/ssh-doctor`; Telegram delivery test (note `/etc/hosts` pin, see MEMORY).

## Rehearsal stack (`proxima-rehearsal`, D35)

Purpose: replay the release chain on the same VPS without touching the production contour.
Access: `infra/compose.rehearsal.yaml` + `tools/rehearsal_run.sh`, run under `proxima-admin` with `--root` outside the checkout and outside `/srv/proxima-ai*` / `/etc/proxima-ai*` (the script refuses otherwise). Own compose project, network, volume and port `127.0.0.1:5434`; secrets and raw directory live under `<root>`.
Safe operations: `bash tools/rehearsal_run.sh <init|up|backfill|tail|steps|check|down|all> --root <root>` (`all` = `up → backfill → tail → steps → check`; `init` and `down` always separate); `--dry-run` prints the commands without running them; `down -v` removes the rehearsal volume only.
Dangerous operations: `tail --live` is the one step that touches the live WB API (two read calls, the D35 exception) and it copies the production statistics token file — the value never reaches the shell. Pointing `--root` at production paths, or leaving `PROXIMA_REHEARSAL_LIVE=1` set beyond that single `compose run`.
Verification: `check` prints the ledger and the gate table against `docs/state/API-FACTS.md`; any mismatch is exit 1 and a decision for Mike, not a number to "fix" (`docs/operations/release-m01.md`, «Репетиция на VPS»).

## Jira PA (tracker)

Purpose: primary task tracker (epics PA-34/35/36/37 and the PMM product epics).
Access: zhamba.atlassian.net via jira MCP. Codex exposes three read verbs only; the server-side pipeline has no Jira access at all (`docs/agent-system/ORCHESTRATOR.md`).
Safe operations: read and browse.
Dangerous operations: any write - create, edit, comment, transition. Writes happen only after Mike approves the sync tables (PRD §10, D17/D24); the source of truth for tasks is `epics.md` plus `sprint-status.yaml`, and synchronisation runs one way, repo to Jira. Tasks are never deleted. Do not create parallel tracking outside PA/PMM.
Verification: task keys referenced in TASKS.md exist; every written task points at `epics.md#story-N-M`.

## Sibling source worktrees (Опрос-v2.2, torgstat-collector)

Purpose: import sources only.
Access: paths and pinned baselines are recorded in `AGENTS.md` («Жёсткие запреты» п. 4) — `Опрос-v2.2` baseline `9cca25d1`, `torgstat-collector` tag `baseline-lock` (rescue commit `0fba181`, 2026-08-16). `STATE.md` no longer carries a "Source Boundaries" section.
Safe operations: read; import via explicit allowlist + relative path + SHA-256.
Dangerous operations: any mutation, stash, clean or commit inside those worktrees — forbidden.
Verification: baseline `9cca25d1` unchanged; imported files stay pinned to source commit `610169a6…` in `provenance/import-inventory.json` and `provenance/torgstat-collector-610169a.attestation.json`, checked by `make provenance`.

---

Rules: never log or commit credentials; rate limits and quotas are real costs; prefer read-only access until a change is approved.
