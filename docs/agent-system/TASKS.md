# TASKS — PROXIMA AI

> Snapshot of task state in this repo. Full backlog lives in Jira project PA (zhamba.atlassian.net); this file mirrors only what an agent needs to resume work.

## Active main task

### COLLECTOR-WB-BRANCHES — WB run cancellation / detached branch handling (Phase 2 collector hardening)

Status: IN_PROGRESS (implementation thread landed at `1a211c9`, later commits `e867911..8b07249` landed on top; final integration state unconfirmed — see Next action)
Priority: P1 (Track A / M1, epic PA-36)
Type: feature/bug (collector robustness)
Tracker: UNKNOWN (specific Jira issue key not established from repo evidence; epic PA-36)
Dependencies: none open in-repo

### Why
The collector's async WB intake must never leave orphaned RUNNING state or keep detached WB report branches alive after a run is cancelled or fails. Long waits (rate limits, `WAITING`/`PROCESSING`/`RETRY` states) must be abortable so scheduled runs cannot hang indefinitely.

### Desired outcome
A cancelled/failed run reliably aborts pending waits and cancels detached WB branches; BLOCKED outcomes provably cancel the detached branches; behavior is covered by tests.

### Scope / Out of scope
In scope: `services/collector` cancellation helpers, abortable sleep, detached-branch cancellation on RUNNING leftovers, rate-limit response header persistence in raw evidence.
Out of scope: WB WRITE endpoints (forbidden), scheduler/SLA work (Phase 4), control-plane changes.

### Acceptance criteria
- Abortable sleep + run cancellation helpers exist and are used (commit `99fea05`, 2026-08-14).
- A run leaving RUNNING cancels detached WB branches (commit `dc68839`).
- Test proves BLOCKED cancels detached WB branches (commit `1a211c9`).
- `scripts/agent/verify` (typecheck + TS tests + pytest) green — confirmed 2026-08-16.

### Verification
`scripts/agent/verify` (fast gate) or `make verify` (full canonical gate).

### Next action
Confirm with Mike / Jira PA whether this thread is DONE and can be closed (then record it under Done and pull the next task from Jira PA). Per `.planning/STATE.md` (2026-08-16), the planned next main thread is Track B: scenario-engine audit in the `Опрос-v2.2` source worktree (PA-39) — which lives OUTSIDE this repo.

## Queue

1. PMM (M2/M3 backlog среза), Sprint 0 в порядке исполнения после аудита 2026-08-17: **PMM-30** — DEC-006 уже на `main` через PR #9 (`a2a7b12`), осталось прочитать формулировки и закрыть → **PMM-29** (контракты signal/diagnosis/decision-record + codegen) → **PMM-31** (LLM-доступ: проверить egress с VPS ДО выбора моделей). Исполнение PMM-задач за `mihailzhamba-bot` (решение Mike 2026-08-17); этот агент ведёт бэклог. Параллельно спайки **PMM-2** (налоговые сценарии → ADR) и **PMM-14** (Build vs Buy, ≤3 дня), оба ждут входных данных от Mike. Exit-критерии среза — PMM-11. Manifest: `docs/exec-plans/active/pm2-backlog-run.manifest.yaml`; отчёт аудита: `docs/exec-plans/active/pmm-audit-2026-08-17.md`.
2. Track B PA-39: scenario engine audit in `Опрос-v2.2` (other repo; do not mutate that worktree without allowlist — see RULES). Теперь blocks PA-41, а PA-41 blocks PMM-5/20/23 — от этой пары зависит весь W1-срез.
3. Phase 2 `02-02`: checkpointed on the official WB XLSX from Mike — blocked until the file is delivered (STATE.md, 2026-08-16).
4. Phase 2 leftovers: CI pipeline green run; observed-XLSX parser (STATE.md: "CI and the observed XLSX parser remain pending").
5. From Mike (inputs): pilot XLSX, production Bogatova token, interview slots, AI-ops analyst onboarding, COGS data (STATE.md, 2026-08-16).

## Done (recent)

- 2026-08-17 Аудит M2-бэклога: снят двойной бэклог M2 (PA-37 имел 9 детей, пять дублировали срез — PA-43/45/46/47/48 закрыты, метка `superseded-by-pmm`, откат обратим); DEC-006 снял конфликт с DEC-005; заведены PMM-29…33 под четыре блокера критического пути; сироты разведены по эпикам, достроен граф связей, проставлены метки спринтов. Отчёт: `docs/exec-plans/active/pmm-audit-2026-08-17.md`; rollback JQL `labels = "aios-fix-2026-08-17"`.
- 2026-08-17 PMM backlog-slice run: 28 issues созданы в PMM (company-managed), верифицированы, manifest в `docs/exec-plans/active/pm2-backlog-run.manifest.yaml`; rollback JQL `labels = "aios-run-2026-08-17"`. Три верификационных утверждения прогона позже опровергнуты аудитом (см. `verification_correction` в манифесте).
- 2026-08-14 `1a211c9` test(collector): prove BLOCKED cancels detached WB branches.
- 2026-08-14 `dc68839` fix(collector): cancel detached WB branches when a run leaves RUNNING.
- 2026-08-14 `99fea05` feat(collector): abortable sleep and run cancellation helpers.
- 2026-08-14 `5603f50` docs(runbook): pin warehouse mapping effective_from and service sales warehouses.
- 2026-08-14 `a4b0ed6` feat(collector): persist rate-limit response headers in raw evidence.

---

Rules: one active main task; new ideas go to the Jira backlog, not here — **M1 / Track A / Track C → PA, M2 / M3 → PMM** (split recorded in `.planning/PRODUCT-VISION.md`, section «Трекер», 2026-08-17); update this file at every state change of the active task.
