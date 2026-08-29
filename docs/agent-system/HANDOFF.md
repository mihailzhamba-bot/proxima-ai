# HANDOFF — PROXIMA AI

> If the current agent disappears right now, what must the next one know? Update after every meaningful stage.

## Current objective

Ship M1 — a production-ready read-only data foundation for one pilot WB cabinet (Bogatova Belle Robe) with SHA-256 provenance from official WB evidence to PostgreSQL domain releases (Phase 2 of 8 in progress).

## Current task

**PA-13 enforcement rollback оставлен по решению Mike 2026-08-25;** live Jira всё ещё «В работе» и требует ручной актуализации: исходная цель superseded, successor = READ-only Analytics token → повторный revert. **Plan 02-02 cancelled; выбран Phase 2 вариант A (close with descope), Jira-переход ещё не выполнен.**

**PA-41 W1 verbatim import и SCN-008 adapter slice выполнены 2026-08-27.** 18/18 allowlist SHA-256 совпали с source pin `53b7d604`; добавлены `src/proxima` и `pydantic==2.13.4`, обновлён `services/control-plane/uv.lock`. `make verify` PASS: 131 passed, 1 skipped. W2 остаётся после PMM-29.

**PMM-5 DONE 2026-08-28 (this worktree, autopilot full):** LLM-диагноз SCN-008/001/005 fixtures-first - пакет `proxima_control_plane.diagnosis` (draft-схема внутри control-plane, вендор-агностичный LLMClient+Mock, DATA-промпт anti-injection, retry ×2 fail-closed, timeout, rollback-флаг `llm_enabled`, JSONL-аудит, CLI run/eval) + eval 12 кейсов 12/12 (гейт ≥80%). PR #29 merged `6c29398`; `make verify` PASS; Jira PMM-5 Готово (DoD PMM-12, комментарий 10377). Грилль-бриф 10/10: `docs/exec-plans/active/pmm-5-llm-analyst-w1.md`; autopilot-прогон `.autopilot/2026-08-27-pmm-5-llm-analyst-w1` (сдан). Известные ограничения перед PMM-31 (real provider hardening) - в Jira-комментарии. Следующие по спринту: PMM-31 (нужно одобрение Mike на VPS-операции), PMM-25, PMM-32, PMM-33.

**PA-49 Warm Precision сдан 2026-08-26 (autopilot interview deep polish, этот worktree, ветка `feat/pa-49-warm-precision`, коммиты 0dbfa71..12651e4 + gitignore-хвост; в main НЕ мержено - ждёт Mike: новый PR или прямой merge; №17 занят rollback-PR PA-13).** Редизайн webapp по DESIGN.md: тёплые токены обеих тем, Inter+IBM Plex Mono, метрическая полоса 5 карточек (GYR/выручка/заказы/OOS/свежесть) с FX-бейджами на демо-цифрах, редакционный /brief (вердикт-строка, critical-строки 36px, ₽ mono, CountUp+reduced-motion), спроектированные скелеты inbox/dashboard/admin с per-секционными error-boundaries, стайлгайд-эталон; staging-контейнер proxima-webapp-staging на VPS (только 127.0.0.1:3000; смотреть: `ssh -N proxima-app` → http://localhost:3000); фикс Dockerfile PUPPETEER_SKIP_DOWNLOAD (ADR-0006/D01); ADR 0002-0006; память AGENTS.md между autopilot-маркерами; Jira PA-49 комментарий 10334 (статус не менялся). Verify: make verify PASS end-to-end, vitest 26, lint 0, build зелёный. G4 слепая приёмка 16/18 (2 процессных); доводка 1 круг: 6 найдено, 5 закрыто, 1 отклонено (violet-подложка активного пункта - буква R04). Запись: `.autopilot/2026-08-25-pa49-warm-precision/`. После решения по ветке: PA-50 (контракт сигнала - PMM-29 bot lane); PA-49 закрывается деплой-сессией 2 (домен + 80/443).

## Current state

- Состояние на 2026-08-29: разработка мигрирована на VPS `135.106.186.210` в изолированную зону OpenHands под пользователем `openhands-agent`; используется rootless Docker с лимитами 2 CPU/4 GB. Исходящий LLM-трафик идёт через SOCKS/HTTP-прокси на NL-сервер. Git-flow: агент коммитит в ветки `ai/*`, а push и merge выполняет человек с хоста.
- Phase 2 (Vertical Slice: Immutable Intake to Visible Facts): выбран close with descope 2026-08-27; criterion visible facts переносится в Phase 3/6, документальный и Jira-синк pending.
- M2 track opened in Jira PMM (sprint-0/1 backlog); PMM-30 (DEC-006) done; PMM-2 spike merged as above.
- Staging VPS Selectel `135.106.186.210` bootstrapped; host monitor live since 2026-08-15 (Telegram delivery tested, `/etc/hosts` pin for `api.telegram.org` in place). Business data blocked until the backup guardrail (Phase 7).
- 2026-08-16 planning session: PRODUCT-VISION.md approved, Jira PA epics PA-34/35/36/37 created (source: `.planning/STATE.md`).
- Note: local `main` is checked out by the sibling worktree `!Proxima/PROXIMA AI`; this worktree works on feature branches rebased onto `origin/main`.

## Completed

- 2026-08-26: **PA-49 Warm Precision autopilot-прогон сдан** (см. Current task). 7 тасков в 5 волнах + волна ремонта (R15) + 3 доводочных таска; G2 независимая сверка поймала 4 пробела спеки (закрыты); G4 16/18; 12+ коммитов на feat/pa-49-warm-precision. Stage-дашборд прогона заморожен (`.autopilot/dashboard.html`).
- 2026-08-25: **PA-13 rollback deployed** (this agent, branch `mihailzhamba-bot/PA-13-rw-optin`, worktree PA-9). Revert `267cc3c` → `fd95fcb` restores the temporary `--allow-analytics-read-write` exception across collector, CLIs, installer, Python tools, tests and runbook; `make verify` PASS; VPS deployed via bundle (dump `000577e0…`, detached `fd95fcb`, build green; fixed root-owned `docs/agent-system`/`scripts/agent` that broke checkout). Diagnostics proved: fail-closed default intact flagless; both Aug-16 RW tokens dead at WB with `crypto/ecdsa: verification error` (broken copies at the cabinet owner); paste channel clean (Statistics/Finance byte-identical). RW token №4 (Mike-approved) installed `0600 proxima-admin`; local+VPS temp token files removed. Same session: **Plan 02-02 cancelled** by Mike (XLSX `c6dce3b4…` profiled into EVIDENCE, no parser code).
- 2026-08-23: **PA-39 audit of scenario engine in Опрос-v2.2 - DONE** (this agent, worktree `PA-39`, branch `mihailzhamba-bot/PA-39`). Artifacts: `docs/audits/pa-39-scenario-engine-audit.md` (module map deep/card zones, scenario-to-wave mapping SCN-001..008 + greenfield 009/010/011, dependency graph, consumed-surface map of 18 symbols from `ai/contracts.py` as PMM-29 input, analytics_reader interface spec, PA-41 estimate) + `pa-39-import-allowlist.yaml` (27 entries: W1 deterministic core 18 files incl. evals/evidence data, W2 LLM-slice 8 files, settings adaptation base) + `pa-39-hash-transcript.txt` (27/27 machine PASS). Provenance pinned to `53b7d604` (baseline `9cca25d1` ancestor; delta = 10 docs files only). Key grill decisions: destination `services/control-plane/src/proxima/` (verbatim imports resolve); two-commit import scheme (verbatim -> adaptation onto PMM-29 contracts); PA-41 W1 can start immediately, W2 waits for PMM-29 (Jira link created: PMM-29 blocks PA-41). Verification: machine hash-transcript caught one real transcription error (wrong hash for test_model_adapter.py) - fixed; independent reviewer 2 passes: final state 0 blockers (3 numeric fixes + YAML note sync). Source worktree untouched (git status identical before/after). Jira PA-39: В работе -> На проверке with PR link.
- 2026-08-22: **Tracker-vs-repo reconciliation (both Jira projects).** Counts taken live, not from docs: PA 47 issues — 14 Done, 1 In Progress (PA-13), 32 To Do; PMM 33 — 4 Done (PMM-7/9/10/30), 1 In Progress (PMM-2), 28 Backlog; PMM sprint-0 is 14 issues with 4 closed. **PA "Done" overstates progress:** PA-43/45/46/47/48 carry `superseded-by-pmm` — moved to PMM by the 2026-08-17 audit, not executed; genuine PA completions are nine (PA-10/11/12 + PA-28…33). Two issues are the reverse — done but still open: PA-27 (Makefile is the working single entry point, 18 targets) and half of PA-17 (`git ls-files build/` returns zero, only the provenance review status remains). Verified directly on the VPS: `/etc/proxima-ai/secrets/` holds three of five WB tokens (statistics, analytics, finance — no prices/promotion, confirming PA-15), monitor timer active+enabled, Postgres 16.10 healthy 7 days, disk 3%. Two stale PRs: #5 (PA-12) fully duplicates merged #6 — safe to close; #3 (PA-33) is NOT a duplicate — its exact dependency-version table (TypeScript 5.8.3, Ajv 8.20.0, decimal.js 10.6.0, pg 8.16.3) is absent from main, so closing it drops content. 49 reconciliation comments posted — every unclosed issue in both projects plus epics PA-36/PA-37; count cross-checked with `project in (PA, PMM) AND updated >= startOfDay()` = 49, not self-reported. Issue statuses deliberately untouched (Mike's call). Critical path unchanged and idle: PA-39 → PA-41 → PMM-5/20/23 → PMM-32 → PMM-28, and PA-39 has no external blocker.
- 2026-08-22: **VPS SSH access restored.** Symptom was `Permission denied (publickey)` while the server was healthy the whole time. Root cause was NOT the VPN: through the active AmneziaVPN full tunnel, TCP/22 connects in 0.148 s, RTT 140 ms, and the host key still matches `known_hosts` (server never recreated). The real cause was three-layered: (1) no VPS entry in `~/.ssh/config`, so ssh only offered `id_rsa`/`id_ed25519`, neither of which is in `authorized_keys`; (2) the key the server *does* accept — `~/.ssh/id_ed25519_proxima_selectel_20260813`, proven by `Server accepts key` in `ssh -vv` — is passphrase-protected, and without `UseKeychain yes` ssh never reads the passphrase from the macOS Keychain; (3) attempts as `root`, which is locked by design (`PermitRootLogin no`, `AllowUsers proxima-admin`, `passwd --lock root`). Fix: `proxima` / `proxima-db` aliases in `~/.ssh/config` (backup `~/.ssh/config.bak-2026-08-22`) with `IdentitiesOnly yes` (server `MaxAuthTries 3`) + `UseKeychain yes`, plus new read-only diagnostic `infra/ssh-doctor`. Verified end to end: `ssh proxima` → `claudette`, tunnel `ssh -N proxima-db` → Postgres 16.10 answers on `localhost:5433`, and `proxima-psql-readonly` returns `proxima|proxima_diagnostics`. The 2026-08-14 memory claim that "AmneziaVPN cuts port 22" is retracted; the supported way to take the host out of the tunnel is Amnezia's own `ExceptSites` list, not a manual `sudo route add`.
- 2026-08-17: M2/M3 backlog-slice run complete — new company-managed Jira project **PMM** «Proxima M2-M3» (id 10043) populated with 28 issues (25 FULL / 3 STUB, labels `aios-run-2026-08-17` + `wbs-aios-*`), 11 blocks-links, 4 Relates PMM→PA (37/38/39/41). PA untouched (link-only). Manifest + living plan: `docs/exec-plans/active/pm2-backlog-run.*`. Capacity decision: 1 FTE → vertical slice (growth beyond = separate gate PMM-4). Rollback JQL: `labels = "aios-run-2026-08-17"`.
- 2026-08-14: collector cancellation thread (see above); runbook warehouse-mapping pin (`5603f50`); contract repository path fix (`453ffe0`).
- 2026-08-16: agent operating system layer deployed (this directory, AGENTS.md extension, `scripts/agent/verify`).
- 2026-08-16: reviewer subagent deployed in three tool formats (`.opencode/agents/reviewer.md`, `.claude/agents/reviewer.md`, `.codex/agents/reviewer.toml`) + AGENTS.md "Delegation protocol" section (task-class → orchestration mapping, cross-model review gate 0/0 for phases 3/4/7). Not yet committed; needs live smoke test after session restart (agent dirs created mid-session are not discovered by already-running sessions).
- Earlier: Phase 1 complete (3/3 plans, 3/3 cross-model reviews 0/0); Day-1 WB API proof (5 split read-only tokens); async Analytics CSV proof with quota reservation.

## In progress

- None committed as open by the current agent. Pre-existing dirty tree (other threads, do not stage/commit blindly): `Makefile`, `README.md`, `package.json`, `package-lock.json`, `.planning/STATE.md`, `tools/verify_runtime_boundary.py` (modified); untracked `.mcp.json`, `opencode.json`, `.codex/`, `.planning/PRODUCT-VISION.md`, `.planning/research/GLOBAL-LANDSCAPE-2026-08-16.md`, `services/collector/src/contracts/`, `tools/generate_contract_types.mjs`, `AGENTS.md`, `CLAUDE.md` (AGENTS/CLAUDE now committed by the AI-OS layer). Reviewer-deploy thread (this agent, uncommitted): `AGENTS.md` modified (Delegation protocol + routing row), untracked `.opencode/agents/reviewer.md`, `.claude/agents/reviewer.md`, `.codex/agents/reviewer.toml`.

## Blockers

- ~~No live WB Analytics token~~ снято 2026-08-25: live-сбор прошёл. READ-only перевыпуск → вернуть enforcement остаётся successor, не текущая инженерная очередь.
- Jira write operations are unavailable in the current MCP session; live status/links need a Chrome session or manual Mike action.
- First approved data release blocked on Phase 8 Data GO; live deployment blocked on separate Live Deploy GO (STATE.md).
- No local Docker — DB dev goes through SSH tunnel to staging VPS (Mike decision 2026-08-16).

## Important discoveries

- Jira site: ALL projects were team-managed; PMM (2026-08-17) is the first company-managed. MCP has NO endpoints for creating components/versions — `comp-*` / `rel-*` labels are the working substitute; if native components appear (UI), they can be backfilled via editJiraIssue.
- Python must run via `uv` (3.14), never the system 3.9 (AGENTS.md toolchain table).
- `services/collector/src/contracts/` TS types are generated by `make codegen` — never hand-edit.
- Local fast verification works without full `make verify`: typecheck + TS tests + pytest all pass (run 2026-08-16: 48 passed, 1 skipped).
- Sibling worktrees `Опрос-v2.2` (baseline `9cca25d1`) and `torgstat-collector` (baseline `610169a6`) must never be mutated; import only via allowlist + SHA-256.

## Files changed

- 2026-08-25 (PA-13 rollback): revert commit `fd95fcb` (13 files, restores `--allow-analytics-read-write` everywhere); docs: `.planning/STATE.md`, `.planning/ROADMAP.md`, `.planning/phases/02-vertical-slice-immutable-intake/EVIDENCE.md`, `docs/agent-system/HANDOFF.md` (this update), `docs/agent-system/TASKS.md`. VPS: secrets `wb_analytics_token` replaced (RW №4, Mike-approved), `/srv/proxima-ai/backups/pre-pa13rw-20260825.dump`, ownership fix on `docs/agent-system` + `scripts/agent`.
- 2026-08-16 (AI-OS deploy): `AGENTS.md` (extended), `CLAUDE.md` (symlink → adapter file), `docs/agent-system/*`, `docs/exec-plans/{active,completed}/.gitkeep`, `scripts/agent/verify`.
- 2026-08-16 (reviewer deploy): `AGENTS.md` (+18 lines: delegation protocol, routing row), `docs/agent-system/HANDOFF.md` (this update); new `.opencode/agents/reviewer.md`, `.claude/agents/reviewer.md`, `.codex/agents/reviewer.toml`.

## Verification status

- Last full `make verify` run by this agent: **PASS on `fd95fcb` (2026-08-25, PA-13 rollback worktree)** — install + codegen + typecheck + TS tests (incl. build) + 51 pytest passed / 1 Docker-dependent skip + contracts + migrations + provenance + 4 Mermaid renders + boundary + secrets scan + VPS contract + business-signal. Note: this worktree needed `npm ci` inside `services/collector` for the first run.
- Reviewer read-only runtime proof (2026-08-16, canary-file edit test, canary hash unchanged in all runs): opencode — delegation confirmed (child session), edit tool absent from reviewer pool, bash denied except git-read (agent quoted its own deny rules); Claude Code — write blocked, no retry/workaround; Codex — `operation not permitted` via read-only sandbox (note: that run executed in main thread; reviewer spawn proven separately by REVIEWER-CODEX-OK smoke test; whether the TOML `sandbox_mode` applies when the parent session is non-read-only was NOT isolated — for critical phases prefer launching the reviewer with an explicit read-only sandbox). Caveat for all CLI (`-p`/`run`/`exec`) modes: `@reviewer` mention does NOT force delegation — phrase tasks as review-matching descriptions or explicitly instruct "use the task tool to delegate".
- Last full `make verify` run by this agent: not run (performs `npm ci`, codegen, renders; pre-existing dirty `package-lock.json` belongs to another thread). UNKNOWN when it last ran green end-to-end.

## Exact next action

1. Reconcile Jira status/links in Chrome for PA-13, PA-15, PA-17, PA-38, PA-41, PA-49, PA-50, PA-55, PMM-2 and PMM-29.
2. Keep PA-41 W2 blocked until PMM-29 contracts are accepted; then import only the approved W2 allowlist.

Sprint 0 progress: PMM-30 done (DEC-006, PR #9); PMM-2 spike merged (PR #10: ADR-0001 + DEC-007, LE-1 pilot entity filled, stays Draft until accountant Q1-Q4 + remaining entities); PMM-9 + PMM-10 done (PR #12: `docs/governance/assumptions-register.md` 11 entries, `risk-register.md` 13 risks, both Jira Done). **PMM-29 = bot lane (claimed, do not duplicate).** Proxima engineering lane: PA-41 W1 + SCN-008 adapter slice done; after Jira sync, queue PMM-11, PMM-8, PMM-12 unless Mike reorders. PMM-31 needs explicit Mike approval (VPS operations). PMM-2 closes only at ADR Accepted.

**Coordination note (2026-08-17, updated 2026-08-18).** This repo has a second executor: `mihailzhamba-bot` opens PRs against Jira PMM issues (PR #9 was the first). Mike's lane split, resolved 2026-08-18: **PMM-29 (contracts) = bot lane**, claimed in the PMM-29 Jira comment; the Proxima agent does NOT start it. Proxima agent completed PMM-9 + PMM-10 (governance registers, PR #12, merge `4a6b23a`, both Jira issues Done). Always `git fetch` before assuming local `main` is current; never run the same PMM task on both lanes.

In parallel on Track A: confirm closure of COLLECTOR-WB-BRANCHES with Mike in Jira PA (epic PA-36); if DONE, move it to TASKS "Done". **PA-39 audit complete (2026-08-23, see Completed); PA-41 W1 verbatim-import + SCN-008 slice done** (does not wait for PMM-29), which unblocks PMM-5/20/23 after Jira sync.

Two things need Mike before they can move: the pilot XLSX (Phase 2 plan 02-02) and four Jira components in the PMM UI (`governance`, `w1-slice`, `delivery`, `finance`) — the MCP has no endpoint for creating them.

## Backlog audit 2026-08-17

The M2 backlog was audited against primary sources (JQL counters + repo files). Three verification claims of run `aios-run-2026-08-17` did not hold, and four critical-path blockers had no issue at all. Full write-up: `docs/exec-plans/active/pmm-audit-2026-08-17.md`; corrections recorded in the run manifest under `verification_correction`.

Headline: M2 existed twice. Epic PA-37 had nine children; five duplicated the PMM slice one-for-one, because phase B1 built its existing-map from PA-37…PA-42 while PA-43…PA-48 had been created a day earlier. Mike's decision: PMM is the single home of M2/M3. PA-43/45/46/47/48 closed (label `superseded-by-pmm`, reversible); PA-38/39/41/44 stay in PA as Track B infrastructure. New issues PMM-29…33 close the blockers. Fix label: `aios-fix-2026-08-17`.

Note for anyone touching the LLM layer: DEC-006 now permits LLM runtime and client-facing web UI outside the M1 contour under three conditions (staging data only, `unreleased` marking, release pointer unmoved). WB WRITE, Ozon, WB Advertising and Torgstat automation remain forbidden.

---

Last updated: 2026-08-29
