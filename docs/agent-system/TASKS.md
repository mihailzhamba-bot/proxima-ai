# TASKS — PROXIMA AI

> Snapshot of task state in this repo. Full backlog lives in Jira project PA (zhamba.atlassian.net); this file mirrors only what an agent needs to resume work.

## Дневной прогон 08.09.2026 - выполнен (D32)

Epic 4 стартовал: AD-19 (#87), Stories 4.0 (#95), 4.1 (#100 + #102), 4.2 (#104), 4.3 (#106) в `main`; follow-ups 3.1/3.2/3.3 (#90, #97), проба 3.0 (#91), runbook 1.14 (#99), compose-fix блокера релиза (#103), чек-лист готовности (#93), таблица версий (#92), Jira-журнал (#94). Отчёт, инциденты и что держит релизы - `HANDOFF.md`, раздел «День 08.09.2026». Следующее: 4.4 ждёт разметку Владислава (PMM-126); релизы 1.14/2.6 - по D33 (#89, параллельная сессия) с Владиславом и словом «деплой».

## Ночной прогон 07-08.09.2026 - выполнен (D31)

Семь единиц смержены в `main`: 1.8 (#73), KF-3 (#75), 3.2 (#76), 3.1 (#78), PA-65 (#80), 3.3 (#82), гигиена M-01 (#85, Q21a); мост #81, D31 #72. `blocked` нет. Отчёт, инциденты, таблица синхронизации Jira и рекомендации - `HANDOFF.md`, раздел «Ночь 07-08.09.2026». Ждёт Mike: approve таблицы Jira; решения по открытым вопросам 3.1/3.2/3.3 (в PR); включение `codex-conductor.timer` после обновления его чекаута; следующий шаг - AD для Story 4.0.

## Snapshot 03.09.2026 (модули M-06+)

Модули приняты решением D29 и заведены в Jira: 10 эпиков PMM-63…PMM-72 и 50 задач PMM-73…PMM-122, все в `Backlog`, все с меткой `modules-run-2026-09-03`. Таблицы ключей — `docs/state/JIRA-SYNC-MODULES-2026-09-03.md`.

Реализация модулей начинается после гейта M-03 30.09. Раньше идёт эпик предпосылок PMM-63: два архитектурных решения (остатки OQ-13, ML-платформа OQ-11), живая проба финансового API (OQ-14), два READ-токена, решение по персональным данным (OQ-15) и правка SPEC.

Первый модуль к раздаче — PMM-64 (события и диагноз по SKU): задачи PMM-80…PMM-85 стартуют без единого внешнего решения, PMM-86 и PMM-87 ждут AD об остатках, PMM-88 ждёт записей решений из M-05.

## Snapshot 03.09.2026 (вечер)

Конвейер сведён в `main`: Дирижёр, мост в OpenHands, модули BMAD TEA и BAD. Шесть PR смержены за день, пять открытых остались от эпохи до 30.08 (#34, #32, #31, #26, #3) и ждут решения Mike: закрыть или доработать.

Очередь готова к запуску, три слота: 1.5 (бэкфилл), 1.7 (откат прогона), 2.3 (норма). Вне слотов - Владислав на Story 6.1 и `bmad-architecture` на PA-64 (CR к AD-6, держит мерж 3.1).

BLOCKED: 3.1 держит ротация токена (OQ-10) и PA-64; 1.14 и 2.6 держат даты деплоя в календаре Mike; 6.4 держит отсутствие роли аналитика в боевой базе; запись в Jira держит approve таблиц.

## Snapshot 02.09.2026 (вечер)

- 02.09.2026 PRD v2.2 + дельта epics + Jira sync-brief + роль Владислава: DONE (John); ждёт Mike - даты деплоя, approve брифа, доступы Владиславу, команда на коммит (см. HANDOFF 02.09 вечер).
- 03.09.2026 Документация разработки: dev-onboarding, access-provisioning, observability, incident-runbook, DATA-DICTIONARY, README под лестницу, routing-таблица на действующие требования, исправлены указатели на канон решений: DONE (John); не закоммичено; ждёт Mike - решение по трём расхождениям канона (OQ-16, PA-64) и по конвенциям расчёта (OQ-18).
- 03.09.2026 Роль Владислава v2 (теневой пересчёт цепочки, право блокировать релиз, свои зоны кода) + Epic 6 из пяти историй + PRD v2.3 + D26: DONE (John); ждёт Mike - конвенции расчёта (OQ-18), LOGIN-роль аналитика для чтения базы, approve раздела 4б брифа Jira (см. HANDOFF 03.09).

## Active main task

### BMAD + BAD с делегированием реализации в OpenHands — implementation done (2026-09-01)

Ветка `feat/bad-pipeline` (замена `feat/bmad-bad`, PR #47 закрыт как перенесённый). TEA-модуль, цели `claude-code`/`openhands`, BAD 1.2.0, мост `tools/orchestrator/bad_dev_story.sh` + 12 офлайн-тестов, решение **D28** (записано как D25 01.09, переномеровано при мерже 03.09), гейт «BAD не стартует при активном Дирижёре». Живой прогон моста пройден 01.09. Через мост забраны и отревьюены stories 1.3 (PR #48) и 2.2 (PR #46) - обе в `main`. PR #43 (Дирижёр) смержен 03.09; вендоренные деревья записаны в `provenance/import-inventory.json`. Подробности - `docs/agent-system/HANDOFF.md`.


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
6. From Mike (inputs): READ-only Analytics перевыпуск (не горит; закрывает RW-исключение), production Bogatova token, interview slots, AI-ops analyst onboarding (02.09: аналитик = Владислав, хартия `docs/agent-system/roles/analyst-vladislav.md`, доступы по чек-листу §3), COGS data; инвентаризация прочих юрлиц для ADR-0001 (Q2) и подтверждение ставок бухгалтером (Q1, Q3, Q4).
7. Онбординг Владислава: маршрут первой недели - `docs/agent-system/ONBOARDING-analyst-week1.md` (шаги хартии §8). Ручные шаги Mike: NDA, приглашения в GitHub и Jira, проверка branch protection на `main`, копия каталога фикстур. Доступ к серверу и к боевой базе не выдаётся - роль в базе заводится отдельной единицей (Story 6.4).

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
