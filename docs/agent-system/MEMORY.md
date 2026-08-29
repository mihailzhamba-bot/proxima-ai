# MEMORY — PROXIMA AI

> Stable, useful, project-specific knowledge only. Every entry: date + evidence.

## Project specifics

- OpenHands-зона разработки изолирована на VPS; рабочие процессы выполняются под `openhands-agent` в rootless Docker с лимитами 2 CPU/4 GB (evidence: operating runbook, 2026-08-29).
- Dev-БД `proxima-dev` работает внутри зоны и доступна по адресу `172.17.0.2:5432` (evidence: zone network configuration, 2026-08-29).
- Резервные копии хранятся в S3-бакете `proxima-backups` в регионе `ru-3` (evidence: backup policy, 2026-08-29).
- Для аварийной остановки зоны используется kill switch `stop-openhands-safe`; мониторинг зоны выполняется каждые 5 минут (evidence: operations runbook, 2026-08-29).
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

- No local Docker: DB dev via SSH tunnel `ssh -N proxima-db` (Mike decision 2026-08-16, AGENTS.md).
- VPS SSH (verified 2026-08-22): admin key `~/.ssh/id_ed25519_proxima_selectel_20260813` (`SHA256:CG+iddsvx2qxzSjJXC2v8nztu5LxkOb73ekmEYDNTXM`), passphrase-protected, passphrase lives in macOS Keychain. `~/.ssh/config` must carry `IdentitiesOnly yes` (server `MaxAuthTries 3`) **and** `UseKeychain yes` — without the latter ssh never reads the Keychain and fails with `Permission denied (publickey)` while the server is perfectly healthy. Root is locked by design; `ssh root@135.106.186.210` can never work. Diagnose with `bash infra/ssh-doctor`.
- AmneziaVPN does NOT block port 22 to the VPS — the 2026-08-14 note claiming otherwise was wrong. Re-measured 2026-08-22 through the full tunnel: TCP/22 connects in 0.15 s, RTT 140 ms, host key matches. The manual `sudo route add` workaround is unnecessary; the supported way to bypass the tunnel is Amnezia's own site-exclusion list (`Conf.ExceptSites`), which survives reconnects.
- Python: always `uv` (3.14); system Python is 3.9 and must not be used (AGENTS.md toolchain table).
- Selectel VPS filters default `api.telegram.org`; the host pins it to `149.154.167.220` in `/etc/hosts` (backup `/etc/hosts.bak-2026-08-15`). If Telegram delivery fails, re-test the pin first (README.md, 2026-08-15).
- WB test Analytics token may be read-write; while so, the documented `--allow-analytics-read-write` flag must be passed (README.md).
- Official WB XLSX bytes stay outside Git; tests use synthetic structural fixtures only (STATE.md todos).
- `package-lock.json` / `Makefile` / `README.md` etc. carry foreign uncommitted changes as of 2026-08-16 — never stage blindly (HANDOFF "Dirty-tree note").
- Codex v0.150.x validates transport for **every** declared `mcp_servers.*` entry, including `enabled = false` ones. A project `.codex/config.toml` block `[mcp_servers.X] enabled = false` without `command`/`url` is fatal (`Error loading config.toml: invalid transport in mcp_servers.X`) unless X is also defined in `~/.codex/config.toml`. Caught 2026-08-27 on `granola`/`klaviyo`/`linear`/`shopify-storefront` across 7 configs; fixed by deleting those blocks. Rule: in project configs only declare servers that exist globally; disable via `enabled = false` never via transport-less stubs. Verify with `codex mcp list` in the project dir after touching `.codex/config.toml`.

## User preferences (stable)

- Communication and `.planning/` docs in Russian; code identifiers in English (AGENTS.md).
- Atomic descriptive conventional commits; clean implementation commit per vertical slice (AGENTS.md).
- Weekly product sync with Mike across tracks (decision #49, STATE.md).

## Recurring agent mistakes

- None recorded yet (file created 2026-08-16). Add an entry + a guardrail each time a mistake repeats.
