# ORCHESTRATION - playbook Orca-координатора

> Документ: как PROXIMA AI работает под постоянным Orca-координатором.
> Контракт кратко - в `AGENTS.md` (раздел «Orca coordinator protocol»). Здесь - процедура.
> Updated: 2026-08-25 (v2: placement-протокол, base path worktrees/, постоянный координатор-терминал). Status: active. Verified: первый supervised full-cycle 2026-08-25 (docsync, PASS).

## Роли

| Роль | Кто | Что делает |
|---|---|---|
| Coordinator | Orca orchestration run + opencode terminal в main worktree | intake, dispatch, ретрансляция ask→gate, `check --wait`, verify-маршрутизация, состояние. НЕ гриллит, НЕ кодит, НЕ ревьюит |
| Release-critic | `.opencode/agents/release-critic.md` (opencode subagent) | read-only аудит: research репо+Jira → Release Gate-отчёт (вердикт + handoff-status + DISCOVERY_STATUS-строка) |
| Worker (code) | worktree + `--agent codex` | реализация под autopilot semi; brief = контракт |
| Worker (docs/analytics) | worktree + `--agent opencode` | то же для доков/аналитики |
| Reviewer | `.opencode/agents/reviewer.md` (+ аналоги Claude/Codex) | read-only вердикт по EVALS.md; cross-model для critical |

## Startup sequence координатора

1. `AGENTS.md` (этот репо) + этот файл
2. `docs/agent-system/HANDOFF.md` → точное следующее действие
3. `docs/agent-system/TASKS.md` → snapshot задач
4. `git status` + последние коммиты (dirty-tree правила!)
5. Jira PA - read-only lane-check: не выполняет ли `mihailzhamba-bot` пересекающуюся работу
6. `orca orchestration task-list --json` + `run-show` - незакрытые dispatch'и с прошлого run

## Цикл задачи (major/critical)

1. **Intake**: классификация по таблице в AGENTS.md. Trivial → inline (в сессии Mike, без Orca). Medium → QUICK-brief, решение об autopilot по размеру.
2. **Release Gate**: `task-create` → dispatch release-critic (через `/release-gate` или task tool, read-only). Release-critic делает research репо+Jira и возвращает Release Gate-отчёт; вопросы и решения, меняющие scope, идут через оркестраторский decision gate для Mike (batch, не по одному).
3. **Gate brief**: Mike утверждает gate/Scope lock (или правит scope). Без этого воркер не стартует.
4. **Dispatch worker**: `orca worktree create --repo name:PROXIMA AI --name <task-id> --agent <codex|opencode> --prompt <brief-инъекция>`; воркеру передать: «работаю под autopilot semi; brief в <path>; verify обязателен». Supervised worker через `orchestration worker-start` (не bare worktree create, когда нужен контроль worker_done). Нюансы из практики: селектор `name:` с пробелами НЕ работает - используй `path:<repo-root>`; при `agent_prompt_stalled` - `task-update --status ready` + `dispatch` + ручная `terminal send` с полным заданием и worker_done.
5. **Надзор**: `check --wait --types worker_done,escalation,question --timeout-ms <n>` циклом. Timeout = checkpoint, не провал. Heartbeat = жив, не трогать.
6. **Verify**: worker_done → `make verify` в worktree воркера; major → `reviewer`; critical → cross-model review (0 blocker / 0 warning).
7. **Gate merge**: merge только после явного approve Mike (decision gate). irreversible = тот же гейт.
8. **Close**: merge → `docs/agent-system/HANDOFF.md` + `TASKS.md` обновлены → worktree rm (после release output) → `task-update` settled.

Словарь DISCOVERY_STATUS (последняя строка gate-отчёта, контракт Orca-парсера): READY | NEEDS_APPROVAL | NEEDS_INPUT | NOT_NEEDED | BLOCKED (NEEDS_APPROVAL добавлен 2026-08-27, решение «Двойной формат»).

## Решения, которые всегда за Mike (gates)

- Утверждение Release Gate / Scope lock (scope/requirements)
- Merge в main, deploy, любые irreversible-операции
- Изменение lane (этот оркестратор ↔ `mihailzhamba-bot`)
- Всё из «Жёстких запретов» AGENTS.md

## Расположение и уборка (протокол placement, обновлено 2026-08-25)

- **Постоянный координатор**: терминал `PA-coordinator` (opencode) в main worktree `PROXIMA AI`. НЕ закрывается никогда - это видимое присутствие оркестратора в Orca UI. Run привязан к нему (`run-use`); при пересоздании терминала - перепривязать Run заново.
- **Воркеры эфемерны**: worktree создаётся под задачу, снимается после `worker_done` + release. Уборка воркера НЕ трогает координаторский терминал.
- **Base path воркеров**: `<repo>/worktrees/` (project setup Orca; строка `worktrees/` в .gitignore). Старые сироты в `03-startups/один в коде /PROXIMA AI/` (PA-15, PA-39, PA-9) живут по старому пути - не трогать без решения Mike.
- **Запрет**: не создавать Run/coordinator-инфраструктуру из чужих worktree/терминалов - привязка уходит не туда (инцидент 2026-08-25: Run прибился к терминалу Homeresurs/MK).

## Режимы работы

- **Ops-режим** (текущий, до lane-решения по PMM-29): мониторинг, verify-прогоны, doc-задачи, брифы для бота, статус-отчёты. Полная разработка - после решения Mike.
- **Dev-режим**: полный пайплайн, воркеры в worktrees.
- **Автоматизации по расписанию** (утро/вечер): только статус репо + Jira → HANDOFF, verify-отчёты, doc-хвосты. Никаких grill/autopilot без Mike.

## Эскалация и отказы

- Worker escalation → gate Mike с контекстом, без самостоятельных решений.
- Worker молчит, терминал жив → ждать (rolling waits). Терминал мёртв → `worker-abandon`, fence, gate Mike.
- `make verify` красный → работа НЕ сделана (fail closed). Воркер чинит или задача в BLOCKED с handoff.
- Orca runtime недоступен → `orca status`; пока недоступен, работа продолжается в обычных сессиях, orchestration-provenance не создаётся - честно фиксируй это в HANDOFF.

## Provenance

Каждый supervised dispatch обязан иметь task + dispatch в Orca:
`orca orchestration task-list --json`, `dispatch-show --task <id> --json`.
Работа, выполненная вне Orca-оркестрации, не называется orchestrated - фиксируется как обычная сессия.

## BAD и Дирижёр: два конвейера, один за раз (D25, 01.09.2026)

Ниже уровня оркестратора Orca живут два **исполнительных** конвейера над одной
очередью `_bmad-output/implementation-artifacts/sprint-status.yaml`:

| | Дирижёр | BAD |
|---|---|---|
| Мозг | conversation Codex на VPS, тик по таймеру | сессия Claude Code, ручной `/bad` |
| Человек в контуре | нет (алерты + утренняя сводка) | да, на каждом батче |
| Шаги | dispatch → кросс-модельное ревью → verify → PR → automerge | Phase 0-4 BMAD/TEA: story → ATDD → dev → test-review → code-review → PR → PR-review |
| Реализация | воркер OpenHands (`launch_worker.sh`) | воркер OpenHands (`bad_dev_story.sh`) |
| Мерж | automerge через root-обёртку | только Mike (`auto_pr_merge = false`) |
| Контракт | `docs/agent-system/ORCHESTRATOR.md` (Дирижёр не имеет права его менять) | `.claude/skills/bad/SKILL.md` |

**Одновременно они работать не могут** - подерутся за истории, ветки и номера
миграций. Переключение только явное и только Mike:
`sudo systemctl disable --now codex-conductor.timer`, дождаться завершения
активных воркеров, затем `/bad`. Обратно - `enable --now`.
Гейт продублирован в двух местах: в `SKILL.md` (Startup Gate) и fail-closed
в `tools/orchestrator/bad_dev_story.sh` (exit 3), чтобы пропущенная инструкция
всё равно не привела к диспатчу.

Release Gate и решения Mike стоят **над** обоими: BAD - исполнительный конвейер
внутри уже утверждённой единицы, а не замена `/release-gate`.

## Границы (fail-closed, наследуют AGENTS.md)

- Sibling-worktrees (`Опрос-v2.2`, `torgstat-collector`) - не мутировать.
- PMM-29 не стартует без lane-решения Mike.
- Jira PA - read-only для этого оркестратора.
- WB WRITE запрещён; секреты вне Git; `git add -A` запрещён.
