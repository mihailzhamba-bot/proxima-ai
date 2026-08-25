# ORCHESTRATION - playbook Orca-координатора

> Документ: как PROXIMA AI работает под постоянным Orca-координатором.
> Контракт кратко - в `AGENTS.md` (раздел «Orca coordinator protocol»). Здесь - процедура.
> Updated: 2026-08-25. Status: active. Verified: нет (первый прогон pending).

## Роли

| Роль | Кто | Что делает |
|---|---|---|
| Coordinator | Orca orchestration run + opencode terminal в main worktree | intake, dispatch, ретрансляция ask→gate, `check --wait`, verify-маршрутизация, состояние. НЕ гриллит, НЕ кодит, НЕ ревьюит |
| Briefmaker | `.opencode/agents/briefmaker.md` (opencode subagent) | research репо + grill-волны 3-5 вопросов с рекомендациями → Task Brief (`DISCOVERY_STATUS`-формат) |
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
2. **Brief**: `task-create` → dispatch briefmaker. Briefmaker спрашивает через `orchestration ask`; координатор оборачивает каждый ask в decision gate для Mike (batch, не по одному). Gate закрыт → briefmaker доводит до READY.
3. **Gate brief**: Mike утверждает brief (или правит scope). Без этого воркер не стартует.
4. **Dispatch worker**: `orca worktree create --repo name:PROXIMA AI --name <task-id> --agent <codex|opencode> --prompt <brief-инъекция>`; воркеру передать: «работай под autopilot semi; brief в <path>; verify обязателен». Supervised worker через `orchestration worker-start` (не bare worktree create, когда нужен контроль worker_done).
5. **Надзор**: `check --wait --types worker_done,escalation,question --timeout-ms <n>` циклом. Timeout = checkpoint, не провал. Heartbeat = жив, не трогать.
6. **Verify**: worker_done → `make verify` в worktree воркера; major → `reviewer`; critical → cross-model review (0 blocker / 0 warning).
7. **Gate merge**: merge только после явного approve Mike (decision gate). irreversible = тот же гейт.
8. **Close**: merge → `docs/agent-system/HANDOFF.md` + `TASKS.md` обновлены → worktree rm (после release output) → `task-update` settled.

## Решения, которые всегда за Mike (gates)

- Утверждение Task Brief (scope/requirements)
- Merge в main, deploy, любые irreversible-операции
- Изменение lane (этот оркестратор ↔ `mihailzhamba-bot`)
- Всё из «Жёстких запретов» AGENTS.md

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

## Границы (fail-closed, наследуют AGENTS.md)

- Sibling-worktrees (`Опрос-v2.2`, `torgstat-collector`) - не мутировать.
- PMM-29 не стартует без lane-решения Mike.
- Jira PA - read-only для этого оркестратора.
- WB WRITE запрещён; секреты вне Git; `git add -A` запрещён.
