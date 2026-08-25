# TASKS — PROXIMA AI

> Snapshot of task state in this repo. Full backlog lives in Jira project PA (zhamba.atlassian.net); this file mirrors only what an agent needs to resume work.

## Active main task

### PA-49 — Web-кабинет v0 (1/5): каркас webapp (сессия 1 done, деплой = сессия 2)

Коммит `93f0db1` на локальном `main` (не запушен; параллельная сессия переключила ветку mid-work — см. HANDOFF). Сессия 1 (2026-08-25): `services/webapp` (Next.js 16 + Better Auth + Tailwind 4, standalone), шелл с GYR-топбаром и unreleased-плашкой, скелеты /brief /inbox /dashboard /admin + /styleguide, ленивые Drizzle-клиенты (схема webapp_auth), vitest 11 тестов, Dockerfile + `infra/webapp.compose.yaml` (overlay, основной compose не тронут) + Caddyfile; `make verify` PASS целиком; smoke standalone зелёный. Living plan: `docs/exec-plans/active/pa-49-webapp-skeleton.md`.

Сессия 2 (деплой): от Mike — домен + A-запись `app.<домен>` → 135.106.186.210 и подтверждение открытия 80/443 в firewall Selectel; затем на VPS — схема webapp_auth + роли (webapp_auth_writer / webapp_readonly), сборка образа, overlay compose, первый пользователь, серверная валидация сессии вместо cookie-presence. Подзадачи PA-50..53 стартуют после каркаса.

Рядом завершён ops-docsync 2026-08-25 (Orca run `run_7d2d26245488`, ветка `mihailzhamba-bot/pa-ops-docsync-20260825`, merge в main): сверка HANDOFF/TASKS с фактом — PA-39 закрыт (PR #16 `70441dc`, Jira Готово), PMM-29 lane = `mihailzhamba-bot` с 2026-08-18 (doc-drift «awaits lane decision» устранён), Orca coordinator protocol `0faacb5`, PR pipeline #17/#5/#3 (см. Queue п.4; решения Mike «+» 2026-08-25: #17 merge, #5 close, #3 не закрывать).

Предыстория (закрыто): PMM-2 merged (2026-08-18); PMM-29 = bot lane (не дублировать). COLLECTOR-WB-BRANCHES closure всё ещё не подтверждена с Mike (см. Queue).

## Queue

1. COLLECTOR-WB-BRANCHES closure: confirm with Mike / Jira PA (epic PA-36), then move to Done. Implementation arc `99fea05` → `dc68839` → `1a211c9` (+`8b07249`), verify green 2026-08-18.
2. PMM Sprint 0: **PMM-29** (контракты signal/diagnosis/decision-record + codegen) — **lane = `mihailzhamba-bot`** (решение Mike 2026-08-18, Jira-комментарий к PMM-29; сверка 2026-08-22 подтвердила «не начата», статус Backlog). Этот агент НЕ стартует — двойное исполнение запрещено → **PMM-31** (LLM-доступ: проверить egress с VPS ДО выбора моделей). Исполнение PMM-задач за `mihailzhamba-bot` (решение Mike 2026-08-17); этот агент ведёт бэклог. Спайк **PMM-14** (Build vs Buy, ≤3 дня) ждёт вердикта Mike. Exit-критерии среза — PMM-11. Manifest: `docs/exec-plans/active/pm2-backlog-run.manifest.yaml`; отчёт аудита: `docs/exec-plans/active/pmm-audit-2026-08-17.md`.
3. Track B PA-39: **закрыт полностью** — аудит 2026-08-23 + merge PR #16 (`70441dc`, Jira Готово); артефакты в main: `docs/audits/pa-39-scenario-engine-audit.md`, `pa-39-import-allowlist.yaml` (27 записей: W1 18 / W2 8 / settings 1), `pa-39-hash-transcript.txt` (27/27 PASS). Следующий шаг — **PA-41 W1 verbatim-import** (worktree `pa-41-w1-import` на `70441dc` подготовлен, коммитов нет; W1 не ждёт PMM-29, W2 — после PMM-29).
4. PR pipeline — решения Mike: **#17** «Revert PA-13 enforcement: restore temporary Analytics RW opt-in» (решение Mike 2026-08-25; везёт отмену Plan 02-02 + собственные правки HANDOFF/TASKS) — merge gate; **#5** дубликат смерженного #6 — безопасно закрыть; **#3** НЕ дубликат — таблица версий (TypeScript 5.8.3, Ajv 8.20.0, decimal.js 10.6.0, pg 8.16.3) отсутствует в main (перепроверено 2026-08-25), закрытие теряет контент.
5. Phase 2 `02-02`: в main — checkpointed на официальном WB XLSX, blocked до доставки (STATE.md, 2026-08-16); открытый PR #17 везёт отмену плана (решение Mike 2026-08-25) — после мержа пункт снимается, судьба Phase 2 (close/hold) за Mike.
6. Phase 2 leftovers: CI pipeline green run (в теле PR #17 заявлен `make verify` PASS на `fd95fcb`); observed-XLSX parser — по PR #17 более не нужен (02-02 отменён, машина уезжает в Phase 4).
7. From Mike (inputs): READ-only Analytics перевыпуск (хвост после PR #17, не горит), production Bogatova token, interview slots, AI-ops analyst onboarding, COGS data; инвентаризация прочих юрлиц для ADR-0001 (Q2) и подтверждение ставок бухгалтером (Q1, Q3, Q4). Pilot XLSX снимается с ожидания после мержа PR #17.

## Done (recent)

- 2026-08-25 Ops-docsync (Orca run `run_7d2d26245488`, ops-режим): HANDOFF/TASKS синхронизированы с фактом — PA-39 merged, PMM-29 lane=bot (не pending), PR pipeline #17/#5/#3, PA-49 webapp-поток зафиксирован, `0faacb5` Orca protocol в local main.
- 2026-08-25 Orca coordinator protocol (`0faacb5`, локальный main, НЕ пушен): AGENTS.md-раздел, subagent `.opencode/agents/briefmaker.md`, playbook `docs/agent-system/ORCHESTRATION.md`, routing row в README.
- 2026-08-23 PA-39: merge PR #16 (`70441dc`) — аудит scenario engine + import allowlist в main (603 строки); Jira PA-39 Готово.
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
