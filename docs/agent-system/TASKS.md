# TASKS — PROXIMA AI

> Snapshot of task state in this repo. Full backlog lives in Jira project PA (zhamba.atlassian.net); this file mirrors only what an agent needs to resume work.

## Active main task

### None open — PMM-2 merged (2026-08-18), PMM-29 awaits lane decision

PMM-2 (SPIKE tax regimes) closed by merge PR #10 (`7acd0a8`): ADR-0001 `docs/adr/0001-tax-regime-contribution.md` + DEC-007; ADR stays Draft until remaining legal entities (Q2, Mike) and accountant confirmation Q1-Q4. Jira PMM-2 = In Progress until Accepted. Independent post-merge review 2026-08-18: 0 blockers / 3 warnings (doc-tails; fixes in PR `docs/pmm2-postmerge-review`).

Next candidate: **PMM-29** (contracts signal/diagnosis/decision-record + codegen) — blocked on Mike's lane decision (this agent or `mihailzhamba-bot`; see HANDOFF "Exact next action"). Do not start on both lanes simultaneously.

COLLECTOR-WB-BRANCHES (former active task, implementation landed at `1a211c9`..`8b07249`): closure still unconfirmed with Mike in Jira PA (epic PA-36) — kept below in Queue until confirmed.

## Queue

1. COLLECTOR-WB-BRANCHES closure: confirm with Mike / Jira PA (epic PA-36), then move to Done. Implementation arc `99fea05` → `dc68839` → `1a211c9` (+`8b07249`), verify green 2026-08-18.
2. PMM (M2/M3 backlog среза), Sprint 0 после PMM-2: **PMM-29** (контракты signal/diagnosis/decision-record + codegen) — ждёт решения Mike о lane (этот агент или бот; HANDOFF 2026-08-18) → **PMM-31** (LLM-доступ: проверить egress с VPS ДО выбора моделей). Исполнение PMM-задач за `mihailzhamba-bot` (решение Mike 2026-08-17); этот агент ведёт бэклог. Спайк **PMM-14** (Build vs Buy, ≤3 дня) ждёт вердикта Mike. Exit-критерии среза — PMM-11. Manifest: `docs/exec-plans/active/pm2-backlog-run.manifest.yaml`; отчёт аудита: `docs/exec-plans/active/pmm-audit-2026-08-17.md`.
3. Track B PA-39: scenario engine audit in `Опрос-v2.2` (other repo; do not mutate that worktree without allowlist — see RULES). Теперь blocks PA-41, а PA-41 blocks PMM-5/20/23 — от этой пары зависит весь W1-срез.
4. Phase 2 `02-02`: checkpointed on the official WB XLSX from Mike — blocked until the file is delivered (STATE.md, 2026-08-16).
5. Phase 2 leftovers: CI pipeline green run; observed-XLSX parser (STATE.md: "CI and the observed XLSX parser remain pending").
6. From Mike (inputs): pilot XLSX, production Bogatova token, interview slots, AI-ops analyst onboarding, COGS data (STATE.md, 2026-08-16); инвентаризация прочих юрлиц для ADR-0001 (Q2) и подтверждение ставок бухгалтером (Q1, Q3, Q4).

## Done (recent)

- 2026-08-18 PMM-2 (SPIKE tax regimes) merged PR #10 (`7acd0a8`): ADR-0001 + DEC-007, LE-1 (пилот) заполнен; ADR Draft до Q1-Q4 и инвентаризации прочих юрлиц. Post-merge review: 0 blockers / 3 warnings (doc-tails, закрыты в PR `docs/pmm2-postmerge-review`).
- 2026-08-17 Аудит M2-бэклога: снят двойной бэклог M2 (PA-37 имел 9 детей, пять дублировали срез — PA-43/45/46/47/48 закрыты, метка `superseded-by-pmm`, откат обратим); DEC-006 снял конфликт с DEC-005; заведены PMM-29…33 под четыре блокера критического пути; сироты разведены по эпикам, достроен граф связей, проставлены метки спринтов. Отчёт: `docs/exec-plans/active/pmm-audit-2026-08-17.md`; rollback JQL `labels = "aios-fix-2026-08-17"`.
- 2026-08-17 PMM backlog-slice run: 28 issues созданы в PMM (company-managed), верифицированы, manifest в `docs/exec-plans/active/pm2-backlog-run.manifest.yaml`; rollback JQL `labels = "aios-run-2026-08-17"`. Три верификационных утверждения прогона позже опровергнуты аудитом (см. `verification_correction` в манифесте).
- 2026-08-14 `1a211c9` test(collector): prove BLOCKED cancels detached WB branches.
- 2026-08-14 `dc68839` fix(collector): cancel detached WB branches when a run leaves RUNNING.
- 2026-08-14 `99fea05` feat(collector): abortable sleep and run cancellation helpers.
- 2026-08-14 `5603f50` docs(runbook): pin warehouse mapping effective_from and service sales warehouses.
- 2026-08-14 `a4b0ed6` feat(collector): persist rate-limit response headers in raw evidence.

---

Rules: one active main task; new ideas go to the Jira backlog, not here — **M1 / Track A / Track C → PA, M2 / M3 → PMM** (split recorded in `.planning/PRODUCT-VISION.md`, section «Трекер», 2026-08-17); update this file at every state change of the active task.
