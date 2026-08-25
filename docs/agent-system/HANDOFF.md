# HANDOFF — PROXIMA AI

> If the current agent disappears right now, what must the next one know? Update after every meaningful stage.

## Current objective

Ship M1 — a production-ready read-only data foundation for one pilot WB cabinet (Bogatova Belle Robe) with SHA-256 provenance from official WB evidence to PostgreSQL domain releases (Phase 2 of 8 in progress).

## Current task

Ops-docsync 2026-08-25 (Orca run `run_7d2d26245488`, ops-режим, supervised task `task_66a84044e4ed`, ветка `mihailzhamba-bot/pa-ops-docsync-20260825`): сверка этого файла и TASKS.md с фактом репозитория/Jira/PR. Снимок факта: PA-39 закрыт полностью (merge PR #16, `70441dc`, 2026-08-23; Jira PA-39 = Готово); Orca coordinator protocol закоммичен в локальный `main` (`0faacb5`, 2026-08-25: AGENTS.md-раздел + `.opencode/agents/briefmaker.md` + `docs/agent-system/ORCHESTRATION.md` + routing row в README) — origin/main ещё на `70441dc`, push за gate'ом Mike; PA-49 (web-кабинет v0 1/5) в работе в main worktree; открытые PR #17/#5/#3 ждут решений Mike; PMM-29 lane = `mihailzhamba-bot` (решение Mike 2026-08-18, Jira-комментарий; задача Backlog, не начата) — строка «PMM-29 awaits lane decision» в TASKS была doc-drift, устранена этой сверкой. Правки только двух док-файлов.

## Current state

- Phase 2 (Vertical Slice: Immutable Intake to Visible Facts) in progress; plans 02-01 and 02-01A implemented; 02-02 в main числится checkpointed на официальном WB XLSX (не доставлен), но открытый PR #17 везёт отмену Plan 02-02 (решение Mike 2026-08-25) — до мержа статус в main не менялся. Progress 13%, requirements 6/32 (source: `.planning/STATE.md`, 2026-08-14/16).
- **PA-49 web-кабинет v0 (1/5)** «Каркас webapp - Next.js 16 + Better Auth + деплой Docker/Caddy на VPS» — Jira В работе, blocks PA-50 и PA-54. Поток живёт в main worktree (незакоммиченные `Makefile`, `package.json`, `package-lock.json`, `.gitignore` + untracked `services/webapp/`, `infra/Caddyfile`, `infra/webapp.compose.yaml`, `.autopilot/`, `proxima-project-map-2026-08-22.html`) и на локальной ветке `feat/pa-49-webapp-skeleton` (`89e02e9`: DESIGN.md дизайн-система + spec-before-UI routing в AGENTS.md; там же вариант Orca-коммита `493eeeb`). Чужой поток — не стейджить, не коммитить, не трогать (проверено `git status` main worktree 2026-08-25).
- **Локальный `main` опережает origin**: worktree `!Proxima/PROXIMA AI` стоит на `0faacb5` (Orca protocol), origin/main = `70441dc`. Один непушенный коммит; push — только по явному approve Mike. Всегда `git fetch` + смотреть локальные ветки, не считать origin истиной.
- M2 track opened in Jira PMM (sprint-0/1 backlog); PMM-30 (DEC-006) done; PMM-2 spike merged as above.
- Staging VPS Selectel `135.106.186.210` bootstrapped; host monitor live since 2026-08-15 (Telegram delivery tested, `/etc/hosts` pin for `api.telegram.org` in place). Business data blocked until the backup guardrail (Phase 7).
- 2026-08-16 planning session: PRODUCT-VISION.md approved, Jira PA epics PA-34/35/36/37 created (source: `.planning/STATE.md`).
- Note: local `main` is checked out by the sibling worktree `!Proxima/PROXIMA AI`; this worktree works on feature branches rebased onto `origin/main`.

## Completed

- 2026-08-25: **Orca coordinator protocol в local main** (`0faacb5`; в origin/main НЕ пушен): AGENTS.md §«Orca coordinator protocol (supervised orchestration)» — тонкий оркестратор с 7 обязанностями, quality pipeline major/critical с гейтами (brief → worker_done → merge); проектный subagent `.opencode/agents/briefmaker.md` (research репо + grill-волны → Task Brief, формат DISCOVERY_STATUS); playbook `docs/agent-system/ORCHESTRATION.md`; routing row в `docs/agent-system/README.md`. Первый supervised-цикл под протоколом — этот docsync (run `run_7d2d26245488`, ops-режим).
- 2026-08-23: **PR #16 merged** (`70441dc`): артефакты аудита PA-39 в main (`docs/audits/pa-39-scenario-engine-audit.md`, `pa-39-import-allowlist.yaml`, `pa-39-hash-transcript.txt`; всего 603 строки, 5 файлов); Jira PA-39 = Готово.
- 2026-08-23: **PA-39 audit of scenario engine in Опрос-v2.2 - DONE** (this agent, worktree `PA-39`, branch `mihailzhamba-bot/PA-39`). Artifacts: `docs/audits/pa-39-scenario-engine-audit.md` (module map deep/card zones, scenario-to-wave mapping SCN-001..008 + greenfield 009/010/011, dependency graph, consumed-surface map of 18 symbols from `ai/contracts.py` as PMM-29 input, analytics_reader interface spec, PA-41 estimate) + `pa-39-import-allowlist.yaml` (27 entries: W1 deterministic core 18 files incl. evals/evidence data, W2 LLM-slice 8 files, settings adaptation base) + `pa-39-hash-transcript.txt` (27/27 machine PASS). Provenance pinned to `53b7d604` (baseline `9cca25d1` ancestor; delta = 10 docs files only). Key grill decisions: destination `services/control-plane/src/proxima/` (verbatim imports resolve); two-commit import scheme (verbatim -> adaptation onto PMM-29 contracts); PA-41 W1 can start immediately, W2 waits for PMM-29 (Jira link created: PMM-29 blocks PA-41). Verification: machine hash-transcript caught one real transcription error (wrong hash for test_model_adapter.py) - fixed; independent reviewer 2 passes: final state 0 blockers (3 numeric fixes + YAML note sync). Source worktree untouched (git status identical before/after). Jira PA-39: В работе -> На проверке with PR link.
- 2026-08-22: **Tracker-vs-repo reconciliation (both Jira projects).** Counts taken live, not from docs: PA 47 issues — 14 Done, 1 In Progress (PA-13), 32 To Do; PMM 33 — 4 Done (PMM-7/9/10/30), 1 In Progress (PMM-2), 28 Backlog; PMM sprint-0 is 14 issues with 4 closed. **PA "Done" overstates progress:** PA-43/45/46/47/48 carry `superseded-by-pmm` — moved to PMM by the 2026-08-17 audit, not executed; genuine PA completions are nine (PA-10/11/12 + PA-28…33). Two issues are the reverse — done but still open: PA-27 (Makefile is the working single entry point, 18 targets) and half of PA-17 (`git ls-files build/` returns zero, only the provenance review status remains). Verified directly on the VPS: `/etc/proxima-ai/secrets/` holds three of five WB tokens (statistics, analytics, finance — no prices/promotion, confirming PA-15), monitor timer active+enabled, Postgres 16.10 healthy 7 days, disk 3%. Two stale PRs: #5 (PA-12) fully duplicates merged #6 — safe to close; #3 (PA-33) is NOT a duplicate — its exact dependency-version table (TypeScript 5.8.3, Ajv 8.20.0, decimal.js 10.6.0, pg 8.16.3) is absent from main, so closing it drops content. 49 reconciliation comments posted — every unclosed issue in both projects plus epics PA-36/PA-37; count cross-checked with `project in (PA, PMM) AND updated >= startOfDay()` = 49, not self-reported. Issue statuses deliberately untouched (Mike's call). Critical path unchanged and idle: PA-39 → PA-41 → PMM-5/20/23 → PMM-32 → PMM-28, and PA-39 has no external blocker.
- 2026-08-22: **VPS SSH access restored.** Symptom was `Permission denied (publickey)` while the server was healthy the whole time. Root cause was NOT the VPN: through the active AmneziaVPN full tunnel, TCP/22 connects in 0.148 s, RTT 140 ms, and the host key still matches `known_hosts` (server never recreated). The real cause was three-layered: (1) no VPS entry in `~/.ssh/config`, so ssh only offered `id_rsa`/`id_ed25519`, neither of which is in `authorized_keys`; (2) the key the server *does* accept — `~/.ssh/id_ed25519_proxima_selectel_20260813`, proven by `Server accepts key` in `ssh -vv` — is passphrase-protected, and without `UseKeychain yes` ssh never reads the passphrase from the macOS Keychain; (3) attempts as `root`, which is locked by design (`PermitRootLogin no`, `AllowUsers proxima-admin`, `passwd --lock root`). Fix: `proxima` / `proxima-db` aliases in `~/.ssh/config` (backup `~/.ssh/config.bak-2026-08-22`) with `IdentitiesOnly yes` (server `MaxAuthTries 3`) + `UseKeychain yes`, plus new read-only diagnostic `infra/ssh-doctor`. Verified end to end: `ssh proxima` → `claudette`, tunnel `ssh -N proxima-db` → Postgres 16.10 answers on `localhost:5433`, and `proxima-psql-readonly` returns `proxima|proxima_diagnostics`. The 2026-08-14 memory claim that "AmneziaVPN cuts port 22" is retracted; the supported way to take the host out of the tunnel is Amnezia's own `ExceptSites` list, not a manual `sudo route add`.
- 2026-08-17: M2/M3 backlog-slice run complete — new company-managed Jira project **PMM** «Proxima M2-M3» (id 10043) populated with 28 issues (25 FULL / 3 STUB, labels `aios-run-2026-08-17` + `wbs-aios-*`), 11 blocks-links, 4 Relates PMM→PA (37/38/39/41). PA untouched (link-only). Manifest + living plan: `docs/exec-plans/active/pm2-backlog-run.*`. Capacity decision: 1 FTE → vertical slice (growth beyond = separate gate PMM-4). Rollback JQL: `labels = "aios-run-2026-08-17"`.
- 2026-08-14: collector cancellation thread (see above); runbook warehouse-mapping pin (`5603f50`); contract repository path fix (`453ffe0`).
- 2026-08-16: agent operating system layer deployed (this directory, AGENTS.md extension, `scripts/agent/verify`).
- 2026-08-16: reviewer subagent deployed in three tool formats (`.opencode/agents/reviewer.md`, `.claude/agents/reviewer.md`, `.codex/agents/reviewer.toml`) + AGENTS.md "Delegation protocol" section (task-class → orchestration mapping, cross-model review gate 0/0 for phases 3/4/7). Not yet committed; needs live smoke test after session restart (agent dirs created mid-session are not discovered by already-running sessions).
- Earlier: Phase 1 complete (3/3 plans, 3/3 cross-model reviews 0/0); Day-1 WB API proof (5 split read-only tokens); async Analytics CSV proof with quota reservation.

## In progress

- **PA-49 webapp skeleton** — чужой поток в main worktree (детали и dirty-набор в Current state); не дублировать, не стейджить.
- **PR pipeline — решения Mike:** #17 «Revert PA-13 enforcement: restore temporary Analytics RW opt-in» (Mike decision 2026-08-25; автор `mihailzhamba-bot`; везёт также отмену Plan 02-02 и собственные правки HANDOFF/TASKS/STATE/ROADMAP — после мержа записи #17 в части PA-13/02-02 приоритетны над этой сверкой; в теле PR заявлены `make verify` PASS на `fd95fcb` и деплой на VPS 2026-08-25; мёртвые RW-токены батча 2026-08-16 заменены свежим, READ-only перевыпуск остался хвостом); #5 — дубликат смерженного #6, безопасно закрыть (вывод сверки 2026-08-22, перепроверено 2026-08-25 — PR не менялся); #3 — НЕ дубликат: таблица версий (TypeScript 5.8.3, Ajv 8.20.0, decimal.js 10.6.0, pg 8.16.3) по-прежнему отсутствует в main (grep 2026-08-25: версии есть только как пины в `services/collector/package.json`), закрытие теряет контент.
- **Этот docsync** (ветка `mihailzhamba-bot/pa-ops-docsync-20260825`) — после verify уходит в commit; merge за gate'ом Mike.
- Прежний dirty-набор записи от 2026-08-16 (`README.md`, `.planning/STATE.md`, `tools/verify_runtime_boundary.py`, `.mcp.json`, `opencode.json`, `.codex/` и др.) в main worktree 2026-08-25 больше не виден: `git status` показывает только PA-49-набор (см. Current state). AGENTS/CLAUDE и reviewer-файлы закоммичены ранее.

## Blockers

- Official WB XLSX export for Phase 2 `02-02` — в main всё ещё числится ожиданием Mike (STATE.md F4); отмену плана везёт открытый PR #17 (решение Mike 2026-08-25, не смержен). После мержа пункт снимается, судьба Phase 2 (close/hold) — за Mike.
- First approved data release blocked on Phase 8 Data GO; live deployment blocked on separate Live Deploy GO (STATE.md).
- No local Docker — DB dev goes through SSH tunnel to staging VPS (Mike decision 2026-08-16).

## Important discoveries

- Jira site: ALL projects were team-managed; PMM (2026-08-17) is the first company-managed. MCP has NO endpoints for creating components/versions — `comp-*` / `rel-*` labels are the working substitute; if native components appear (UI), they can be backfilled via editJiraIssue.
- Python must run via `uv` (3.14), never the system 3.9 (AGENTS.md toolchain table).
- `services/collector/src/contracts/` TS types are generated by `make codegen` — never hand-edit.
- Local fast verification works without full `make verify`: typecheck + TS tests + pytest all pass (run 2026-08-16: 48 passed, 1 skipped).
- Sibling worktrees `Опрос-v2.2` (baseline `9cca25d1`) and `torgstat-collector` (baseline `610169a6`) must never be mutated; import only via allowlist + SHA-256.

## Files changed

- 2026-08-25 (ops-docsync, ветка `mihailzhamba-bot/pa-ops-docsync-20260825`): `docs/agent-system/HANDOFF.md` (этот апдейт) + `docs/agent-system/TASKS.md` — сверка с фактом на 2026-08-25; других файлов ветка не трогает.
- 2026-08-16 (AI-OS deploy): `AGENTS.md` (extended), `CLAUDE.md` (symlink → adapter file), `docs/agent-system/*`, `docs/exec-plans/{active,completed}/.gitkeep`, `scripts/agent/verify`.
- 2026-08-16 (reviewer deploy): `AGENTS.md` (+18 lines: delegation protocol, routing row), `docs/agent-system/HANDOFF.md` (this update); new `.opencode/agents/reviewer.md`, `.claude/agents/reviewer.md`, `.codex/agents/reviewer.toml`.

## Verification status

- 2026-08-25 (ops-docsync): `scripts/agent/verify` — PASS на этой ветке (`0faacb5` + докправки; для чистого worktree потребовался `npm install` в `services/collector` — известная ловушка свежих worktree).
- Последний известный полный `make verify` PASS — на `fd95fcb` (2026-08-25, ветка PR #17; заявление тела PR, сам этот агент прогон не делал). До этого: `scripts/agent/verify` PASS на `682560b`/`91d54c4` (2026-08-18, post-merge review PR #10; npm typecheck + npm test + pytest: 51 passed / 1 skipped, identical on both refs).
- Reviewer read-only runtime proof (2026-08-16, canary-file edit test, canary hash unchanged in all runs): opencode — delegation confirmed (child session), edit tool absent from reviewer pool, bash denied except git-read (agent quoted its own deny rules); Claude Code — write blocked, no retry/workaround; Codex — `operation not permitted` via read-only sandbox (note: that run executed in main thread; reviewer spawn proven separately by REVIEWER-CODEX-OK smoke test; whether the TOML `sandbox_mode` applies when the parent session is non-read-only was NOT isolated — for critical phases prefer launching the reviewer with an explicit read-only sandbox). Caveat for all CLI (`-p`/`run`/`exec`) modes: `@reviewer` mention does NOT force delegation — phrase tasks as review-matching descriptions or explicitly instruct "use the task tool to delegate".

## Exact next action

**Снимок 2026-08-25 (ops-docsync), по приоритету:**

1. **Mike, merge gate:** ревью/мерж PR #17 (PA-13 RW opt-in revert + отмена Plan 02-02; включает собственные правки HANDOFF/TASKS/STATE/ROADMAP — после мержа проверить, что записи #17 в части PA-13/02-02 не потерялись на конфликте с этой сверкой).
2. **Mike, stale-PR решения:** #5 закрыть (дубликат смерженного #6); #3 не закрывать как дубликат — таблица версий всё ещё не в main (перепроверено 2026-08-25), контент перенести перед любым закрытием.
3. **Mike, push gate:** `0faacb5` (Orca protocol) существует только в локальном main — пуш в origin только по явному approve.
4. **PA-41 W1 verbatim-import** — следующий исполняемый шаг Track A: worktree `pa-41-w1-import` (ветка `mihailzhamba-bot/PA-41-W1` на `70441dc`) подготовлен, коммитов нет; W1 не ждёт PMM-29, W2 — после PMM-29. Разблокирует PMM-5/20/23.
5. **PA-49 webapp** — чужой поток в main worktree, не дублировать и не трогать dirty-файлы (см. Current state).
6. **PMM-29 = bot lane** (решение Mike 2026-08-18, Jira-комментарий; статус Backlog, не начата; сверка 2026-08-25: контрактов signal/diagnosis/decision-record в `contracts/` нет) — Proxima-агент не стартует.

Sprint 0 progress: PMM-30 done (DEC-006, PR #9); PMM-2 spike merged (PR #10: ADR-0001 + DEC-007, LE-1 pilot entity filled, stays Draft until accountant Q1-Q4 + remaining entities); PMM-9 + PMM-10 done (PR #12: `docs/governance/assumptions-register.md` 11 entries, `risk-register.md` 13 risks, both Jira Done). Remaining sprint-0 candidates for the Proxima agent: PMM-7 (charter-pointer), PMM-8 (glossary + KPI tree), PMM-11 (exit criteria), PMM-12 (DoD checklist) — pick PMM-7 next unless Mike reorders. PMM-31 needs explicit Mike approval (VPS operations). PMM-2 closes only at ADR Accepted.

**Coordination note (2026-08-17, updated 2026-08-18).** This repo has a second executor: `mihailzhamba-bot` opens PRs against Jira PMM issues (PR #9 was the first). Mike's lane split, resolved 2026-08-18: **PMM-29 (contracts) = bot lane**, claimed in the PMM-29 Jira comment; the Proxima agent does NOT start it. Proxima agent completed PMM-9 + PMM-10 (governance registers, PR #12, merge `4a6b23a`, both Jira issues Done). Always `git fetch` before assuming local `main` is current; never run the same PMM task on both lanes.

Track A: confirm closure of COLLECTOR-WB-BRANCHES with Mike in Jira PA (epic PA-36); if DONE, move it to TASKS "Done". PA-39 закрыт (audit 2026-08-23 + merge PR #16 `70441dc`, Jira Готово); следующий на треке — PA-41 W1 (см. Exact next action, п.4).

От Mike всё ещё ждут (ручные шаги без изменений): четыре Jira-компонента в PMM UI (`governance`, `w1-slice`, `delivery`, `finance`) — MCP не умеет их создавать (проверено 2026-08-17). Pilot XLSX для 02-02 снимается с ожидания после мержа PR #17 (план отменяется).

## Backlog audit 2026-08-17

The M2 backlog was audited against primary sources (JQL counters + repo files). Three verification claims of run `aios-run-2026-08-17` did not hold, and four critical-path blockers had no issue at all. Full write-up: `docs/exec-plans/active/pmm-audit-2026-08-17.md`; corrections recorded in the run manifest under `verification_correction`.

Headline: M2 existed twice. Epic PA-37 had nine children; five duplicated the PMM slice one-for-one, because phase B1 built its existing-map from PA-37…PA-42 while PA-43…PA-48 had been created a day earlier. Mike's decision: PMM is the single home of M2/M3. PA-43/45/46/47/48 closed (label `superseded-by-pmm`, reversible); PA-38/39/41/44 stay in PA as Track B infrastructure. New issues PMM-29…33 close the blockers. Fix label: `aios-fix-2026-08-17`.

Note for anyone touching the LLM layer: DEC-006 now permits LLM runtime and client-facing web UI outside the M1 contour under three conditions (staging data only, `unreleased` marking, release pointer unmoved). WB WRITE, Ozon, WB Advertising and Torgstat automation remain forbidden.

---

Last updated: 2026-08-25 (ops-docsync, Orca run `run_7d2d26245488`)
