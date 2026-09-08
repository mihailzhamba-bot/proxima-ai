# MEMORY — PROXIMA AI

> Stable, useful, project-specific knowledge only. Every entry: date + evidence.

## Project specifics

- OpenHands-зона разработки изолирована на VPS; рабочие процессы выполняются под `openhands-agent` в rootless Docker с лимитами 2 CPU/4 GB (evidence: operating runbook, 2026-08-29).
- Dev-БД `proxima-dev` работает внутри зоны и доступна по адресу `172.17.0.2:5432` (evidence: zone network configuration, 2026-08-29).
- Резервные копии хранятся в S3-бакете `proxima-backups` в регионе `ru-3`: ночной `pg_dump` + age-шифрование, локальная retention 14 дней (evidence: `infra/backup/proxima-pg-backup.sh`). На сервере скрипт пока запускается из cron `/etc/cron.d/proxima-pg-backup` в 03:00 (`docs/state/INVENTORY.md:126`, проверено 08.09.2026); юниты `infra/systemd/proxima-pg-backup.{service,timer}` лежат в репозитории и ставятся вместо cron только в релизе - `docs/operations/release-m01.md` §5 «Бэкап как юнит».
- Для аварийной остановки зоны используется kill switch `stop-openhands-safe`; мониторинг зоны выполняется каждые 5 минут (evidence: operations runbook, 2026-08-29).
- Monorepo: npm workspace `@proxima/collector` (TypeScript, Node >=22 <23) + uv-managed Python 3.14 control-plane; canonical JSON Schemas in `contracts/*.schema.json`; migration ledger in `db/` (evidence: repo layout, 2026-08-16).
- Test layout: TS tests in `services/collector/tests/`; Python tests in `services/control-plane/tests` + `tools/tests` (evidence: Makefile `test` target).
- Jira PA is the task tracker; epics PA-34 (Track D, frozen until V3), PA-35 (Track C), PA-36 (Track A / M1), PA-37 (Track B) (evidence: `STATE.md` (root), 2026-08-16).
- Release paperwork (evidence: repo, 2026-09-08): runbooks `docs/operations/release-m01.md` (M-01, 15.09) and `docs/operations/release-m03.md` (2.6 / M-03, draft); one journal per release in `docs/operations/releases/` (`TEMPLATE.md`, `README.md`, `2026-09-15-m01.md`); repo-root `CHANGELOG.md` (Keep a Changelog 1.1).

## Commands that unexpectedly matter

- `make verify` — the single canonical gate. The authoritative list is the `verify:` line of the root `Makefile`, not this file; on 2026-09-08 it is install, codegen, codegen-diff, typecheck, webapp-lint, test, contracts, migrations, pg-roundtrip, provenance, architecture, boundary, secrets, vps, business-signal, wb-client, brief, wb-async-report, funnel, funnel-csv, nm-daily, detector, signals-ranking, live-network (`live-network` added 08.09, AD-4). `pg-roundtrip` exits 0 with `SKIP` when no local PostgreSQL 16 `initdb` is on PATH (`tools/pg_local_roundtrip.sh:17-31`): a green run without `pg-roundtrip: PASS` has not checked the migrations against a real cluster.
- `make codegen` — regenerates TS contract types; required after any `contracts/*.schema.json` change.
- `make collect-wb-analytics` — async WB report probe against the prepared VPS runtime (`--tenant-id amirova-test --period latest-closed-week`).
- `make probe-wb-api` — Day-1 API proof; `tools/wb_api_probe.py` requires all five split read-only categories (`DAY1_REQUIRED_CATEGORIES`: analytics, prices, promotion, statistics, finance), while the VPS holds three token files — `wb_prices_token` and `wb_promotion_token` are still absent (`docs/state/INVENTORY.md:217`, PA-15).
- `make apply-migrations` — applies the migration ledger. In a release it runs inside the owner container: `docker compose --profile jobs run --rm control-plane-admin make apply-migrations ENV_FILE=infra/jobs.env` (`docs/operations/release-m01.md` §2; owner secrets live only in that service, AD-15). The bare host form falls back to `ENV_FILE ?= .env` (`Makefile`) and is for the dev tunnel only.

## Constraints & pitfalls

- No local Docker: DB dev via SSH tunnel `ssh -N proxima-db` (Mike decision 2026-08-16, AGENTS.md).
- Run provenance reaches the ledger-writing job containers from `infra/compose.yaml` itself: `PROXIMA_GIT_SHA` / `PROXIMA_IMAGE_ID` are declared with empty defaults on `collector`, `control-plane` and `control-plane-admin` (2026-09-08, AD-6 / D36 C1), so a runner no longer has to repeat `--env` on every call; empty values normalise to SQL `NULL` (`docs/operations/release-m01.md`, «Сверка 08.09.2026» п. 18).
- Live WB network is fail-closed (AD-4, `services/collector/src/wb/transport.ts`): only the `collector` job service sets `WB_ALLOW_LIVE_NETWORK: "1"`, and only in `infra/compose.yaml` — never in `infra/jobs.env`, systemd units or tests. The `live-network` step of `make verify` (`tools/verify_live_network.py`) holds that boundary.
- VPS SSH (verified 2026-08-22): admin key `~/.ssh/id_ed25519_proxima_selectel_20260813` (`SHA256:CG+iddsvx2qxzSjJXC2v8nztu5LxkOb73ekmEYDNTXM`), passphrase-protected, passphrase lives in macOS Keychain. `~/.ssh/config` must carry `IdentitiesOnly yes` (server `MaxAuthTries 3`) **and** `UseKeychain yes` — without the latter ssh never reads the Keychain and fails with `Permission denied (publickey)` while the server is perfectly healthy. Root is locked by design; `ssh root@135.106.186.210` can never work. Diagnose with `bash infra/ssh-doctor`.
- AmneziaVPN does NOT block port 22 to the VPS — the 2026-08-14 note claiming otherwise was wrong. Re-measured 2026-08-22 through the full tunnel: TCP/22 connects in 0.15 s, RTT 140 ms, host key matches. The manual `sudo route add` workaround is unnecessary; the supported way to bypass the tunnel is Amnezia's own site-exclusion list (`Conf.ExceptSites`), which survives reconnects.
- Python: always `uv` (3.14); system Python is 3.9 and must not be used (AGENTS.md toolchain table).
- Selectel VPS filters default `api.telegram.org`; the host pins it to `149.154.167.220` in `/etc/hosts` (backup `/etc/hosts.bak-2026-08-15`). If Telegram delivery fails, re-test the pin first (README.md, 2026-08-15).
- WB test Analytics token may be read-write; while so, the documented `--allow-analytics-read-write` flag must be passed (README.md).
- Official WB XLSX bytes stay outside Git; tests use synthetic structural fixtures only (STATE.md todos).
- `package-lock.json` / `Makefile` / `README.md` etc. carry foreign uncommitted changes as of 2026-08-16 — never stage blindly (HANDOFF "Dirty-tree note").
- Codex v0.150.x validates transport for **every** declared `mcp_servers.*` entry, including `enabled = false` ones. A project `.codex/config.toml` block `[mcp_servers.X] enabled = false` without `command`/`url` is fatal (`Error loading config.toml: invalid transport in mcp_servers.X`) unless X is also defined in `~/.codex/config.toml`. Caught 2026-08-27 on `granola`/`klaviyo`/`linear`/`shopify-storefront` across 7 configs; fixed by deleting those blocks. Rule: in project configs only declare servers that exist globally; disable via `enabled = false` never via transport-less stubs. Verify with `codex mcp list` in the project dir after touching `.codex/config.toml`.

## User preferences (stable)

- Communication and `docs/archive/planning-m1/` docs in Russian; code identifiers in English (AGENTS.md).
- Atomic descriptive conventional commits; clean implementation commit per vertical slice (AGENTS.md).
- Weekly product sync with Mike across tracks (decision #49, STATE.md).

## Recurring agent mistakes

- Codex fails to start in any repo worktree with `Error loading config.toml: invalid transport in mcp_servers.<name>` when the project `.codex/config.toml` has a bare `enabled = false` block for a server unknown to the global `~/.codex/config.toml` (bit PA-39, PA-41, PMM-12; codex validates project config on every launch). Guardrail: `scripts/agent/verify` runs `codex mcp list` as a fail-closed canary. Fix pattern: remove stale blocks (no global definition = nothing to disable); keep bare blocks only for names that exist globally (transport is inherited).
