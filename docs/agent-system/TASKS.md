# TASKS — PROXIMA AI

> Snapshot of task state in this repo. Full backlog lives in Jira project PA (zhamba.atlassian.net); this file mirrors only what an agent needs to resume work.

## Active main task

### Phase 3: planning complete 2026-08-25 → executing 03-01 next

CONTEXT.md + 4 плана залиты (`.planning/phases/03-postgresql-quality-atomic-releases/`): 03-01 schema foundation (B6 machine-enforced) → 03-02 promotion/quarantine/lineage → 03-03 atomic releases + LKG → 03-04 roles + adversarial matrix. Волны 1→4, autonomous, внешних входов нет. Critical phase: каждый план - cross-model review 0/0. День 2026-08-25 до этого: PA-13 closed (PR #17→#19 `51abc7f`, codex 2/3/1 all fixed), Phase 2 closed (вариант A), 02-02 cancelled, live-сбор Аналитики 1 220 строк.

Next candidate: PMM-7 (charter-pointer) per HANDOFF "Exact next action", unless Mike reorders. **PMM-11 approved 2026-08-27** (Mike, чат): exit-критерии W1-среза в `docs/exec-plans/active/w1-slice-exit-criteria.md` (Approved, codex re-review 0/0, PR #22); Jira-фиксация (описание+чек-лист, статус «В работе», R-14 в risk-register) выполнена тем же днём. **PMM-12 done 2026-08-27** (DoD-чеклист среза: `docs/governance/dod-checklist.md`, PR #23).

COLLECTOR-WB-BRANCHES (former active task, implementation landed at `1a211c9`..`8b07249`): closure still unconfirmed with Mike in Jira PA (epic PA-36) — kept below in Queue until confirmed.

## Queue

1. COLLECTOR-WB-BRANCHES closure: confirm with Mike / Jira PA (epic PA-36), then move to Done. Implementation arc `99fea05` → `dc68839` → `1a211c9` (+`8b07249`), verify green 2026-08-18.
2. PMM (M2/M3 backlog среза), Sprint 0 после PMM-2: **PMM-29** (контракты signal/diagnosis/decision-record + codegen) — **bot lane, не дублировать** (решение Mike 2026-08-18, Jira-комментарий) → **PMM-31** (LLM-доступ: проверить egress с VPS ДО выбора моделей; нужно явное одобрение Mike на VPS-операции). Исполнение PMM-задач за `mihailzhamba-bot` (решение Mike 2026-08-17); этот агент ведёт бэклог. Спайк **PMM-14** (Build vs Buy, ≤3 дня) ждёт вердикта Mike. **PMM-11 (exit-критерии): черновик готов 2026-08-27** (`docs/exec-plans/active/w1-slice-exit-criteria.md`, Draft + Jira-комментарий 10367); ждёт «утверждено» Mike в PMM-11 → затем прогон 2 (Approved, описание+чек-лист, статус «В работе», ссылки PMM-1/3, risk-register, HANDOFF/TASKS хвост). Manifest: `docs/exec-plans/active/pm2-backlog-run.manifest.yaml`; отчёт аудита: `docs/exec-plans/active/pmm-audit-2026-08-17.md`.
3. Track B PA-39: **аудит завершён 2026-08-23** - артефакты `docs/audits/pa-39-scenario-engine-audit.md` + `pa-39-import-allowlist.yaml` (27 записей: W1 18 / W2 8 / settings-adaptation 1) + `pa-39-hash-transcript.txt` (27/27 PASS); machine-верификация поймала и закрыла ошибку переноса хэша; reviewer re-check: 0 blockers после фиксов. Ключевые решения grill-сеанса: пин `53b7d604`, PMM-29 проектирует контракты с нуля (PA-41 adaptation-коммитом перепривязывает), PA-41 = W1 (не ждёт PMM-29) + W2 (после PMM-29). Следующий шаг - PA-41 W1 verbatim-import.
4. ~~Phase 2 `02-02`~~ — **cancelled by Mike 2026-08-25**; Phase 2 **закрыта** тем же днём (вариант A, descope criterion №5).
5. Phase 2 leftovers: CI pipeline green run на PR #17 (после merge); observed-XLSX parser больше не нужен (машина уезжает в Phase 4).
6. From Mike (inputs): READ-only Analytics перевыпуск (не горит; закрывает RW-исключение), production Bogatova token, interview slots, AI-ops analyst onboarding, COGS data; инвентаризация прочих юрлиц для ADR-0001 (Q2) и подтверждение ставок бухгалтером (Q1, Q3, Q4).

## Done (recent)

- 2026-08-28 PMM-5 (LLM Analyst W1) done: `proxima_control_plane.diagnosis` (fixtures-first, mock LLM, draft-схема, DATA anti-injection, fail-closed retry/timeout, rollback-флаг, JSONL-аудит, CLI run/eval) + eval 12/12; PR #29 merged `6c29398`, make verify PASS, Jira Готово (DoD PMM-12). Известные ограничения PMM-31 - в Jira-комментарии 10377. Грилль-бриф: `docs/exec-plans/active/pmm-5-llm-analyst-w1.md`.
- 2026-08-27 PMM-12 (DoD-чеклист среза) done: `docs/governance/dod-checklist.md` (7 пунктов + указатели на канон + шаблон аудита), guardrail в `scripts/agent/verify` (required-files), указатели в `AGENTS.md` §DoD и `RULES.md` §SHOULD; ретро-аудиты PMM-30/9/10 в Jira; make verify PASS.
- 2026-08-25 PA-13 rollback: revert `fd95fcb` (`make verify` PASS) + VPS deploy + полная диагностика токенов (батч 2026-08-16 мёртв по подписям, канал чист) + RW №4 установлен; Plan 02-02 cancelled решением Mike.
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
