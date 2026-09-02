# TASKS — PROXIMA AI

> Snapshot of task state in this repo. Full backlog lives in Jira project PA (zhamba.atlassian.net); this file mirrors only what an agent needs to resume work.

## Active main task

### BMAD + BAD с делегированием реализации в OpenHands — implementation done (2026-09-01)

Ветка `feat/bmad-bad` (от `origin/feat/orchestrator-conductor`). TEA-модуль, цели `claude-code`/`openhands`, BAD 1.2.0, мост `tools/orchestrator/bad_dev_story.sh` + 12 офлайн-тестов, решение D25, гейт «BAD не стартует при активном Дирижёре». Живой прогон моста пройден 01.09, `gh auth login` выполнен. 02.09 через мост забраны и отревьюены stories 1.3 (PR #48, с фикс-раундом) и 2.2 (PR #46). Открыто: мерж #43 → #47 → #48 → #46; до него BAD не стартует (его Phase 0 требует `main`). Подробности — `docs/agent-system/HANDOFF.md`.


### PA-41 W1 + SCN-008 adapter slice — implementation done (2026-08-27)

Главная цель: V1-сигнал. PA-41 W1 импортирован из source pin `53b7d604` строго по 18-файловому allowlist; destination SHA-256 совпадает 18/18. `pydantic==2.13.4` добавлен в control-plane и `uv.lock` обновлён.

Проверка: `make verify` PASS (131 тест, 1 skip); W1 evidence приведён к фактическому срезу без claims о неимпортированных W2/DB поверхностях. SCN-008 adapter slice на импортированном fixture завершён и покрыт e2e-тестом; W2 остаётся за PMM-29.

COLLECTOR-WB-BRANCHES (former active task, implementation landed at `1a211c9`..`8b07249`): closure still unconfirmed with Mike in Jira PA (epic PA-36) — kept below in Queue until confirmed.

## Queue

1. COLLECTOR-WB-BRANCHES closure: confirm with Mike / Jira PA (epic PA-36), then move to Done. Implementation arc `99fea05` → `dc68839` → `1a211c9` (+`8b07249`), verify green 2026-08-18.
2. PMM (M2/M3 backlog среза): **PMM-29** остаётся за `mihailzhamba-bot`; не дублировать. После успешного PA-41 W1 - PMM-11, PMM-8, PMM-12.
3. Track B PA-39: **аудит завершён 2026-08-23** - артефакты `docs/audits/pa-39-scenario-engine-audit.md` + `pa-39-import-allowlist.yaml` (27 записей: W1 18 / W2 8 / settings-adaptation 1) + `pa-39-hash-transcript.txt` (27/27 PASS); machine-верификация поймала и закрыла ошибку переноса хэша; reviewer re-check: 0 blockers после фиксов. Ключевые решения grill-сеанса: пин `53b7d604`, PMM-29 проектирует контракты с нуля (PA-41 adaptation-коммитом перепривязывает), PA-41 = W1 (не ждёт PMM-29) + W2 (после PMM-29). W1 verbatim импортирован и SCN-008 adapter slice завершён 2026-08-27; W2 ждёт PMM-29.
4. ~~Phase 2 `02-02`~~ — **cancelled by Mike 2026-08-25**; выбран вариант A: закрыть Phase 2 с descope criterion №5 и перенести visible facts в Phase 3/6. Документальный синк и Jira-переход ещё не выполнены.
5. Phase 2 leftovers: CI pipeline green run on the cancellation/revert PRs; observed-XLSX parser больше не нужен (02-02 отменён; машина уезжает в Phase 4).
6. From Mike (inputs): READ-only Analytics перевыпуск (не горит; закрывает RW-исключение), production Bogatova token, interview slots, AI-ops analyst onboarding, COGS data; инвентаризация прочих юрлиц для ADR-0001 (Q2) и подтверждение ставок бухгалтером (Q1, Q3, Q4).

## Done (recent)
- 2026-08-28 PMM-5 (LLM Analyst W1) done: `proxima_control_plane.diagnosis` (fixtures-first, mock LLM, draft-схема, DATA anti-injection, fail-closed retry/timeout, rollback-флаг, JSONL-аудит, CLI run/eval) + eval 12/12; PR #29 merged `6c29398`, make verify PASS, Jira Готово (DoD PMM-12). Известные ограничения PMM-31 - в Jira-комментарии 10377. Грилль-бриф: `docs/exec-plans/active/pmm-5-llm-analyst-w1.md`.

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
