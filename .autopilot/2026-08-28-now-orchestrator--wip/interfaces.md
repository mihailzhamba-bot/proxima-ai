# Интерфейсы `/now`

## Границы, решённые в спецификации

| Модуль | Владеет | Выставляет | Прячет |
|---|---|---|---|
| `snapshot` | нормализованное состояние Jira, Git/PR/worktrees, Orca, HANDOFF, TASKS, active ExecPlans и freshness | `load_snapshot(input) -> Snapshot` | отдельные source loaders, parsing и normalization |
| `selector` | deterministic priority rules и cards | `select(snapshot) -> NowDecision` | tie-break и conflict resolution |
| `jira_policy` | allowlist, approval boundary, ledger intents | `authorize(intent) -> JiraDecision`; `record(result)` | payload digest и audit serialization |
| `claims` | track/zone claims и integration lease | `claim(request) -> ClaimResult`; `release(token)` | Git common-dir locking и recovery proof |
| `lifecycle` | `/now go` transitions и close convergence | `advance(command, snapshot) -> ActionPlan` | state-machine guards |
| `renderer` | единый textual card format | `render(decision) -> str` | stable formatting |
| client adapters | live tool collection и approved side effects | `/now`; `/now go <KEY>` | client-specific MCP invocation |

Швы для тестов: публичные pure functions `select`, `authorize`, `advance`, `render`; filesystem seam только у `claims` и ledger. Все adapters используют одну golden fixture; card output byte-identical.

## Проектный контракт

- Python 3.14 через `uv`, только standard library для нового core; новые dependencies запрещены.
- Targeted tests: `uv run --python 3.14 --project services/control-plane --extra test pytest tools/tests/test_now_*.py -q`.
- Full gate: `make verify`.
- Основной CLI: `scripts/agent/now`; не логирует secrets и не выполняет Jira/network writes сам.
- Missing dependency/tool/schema возвращается как `BLOCKED`; ничего не устанавливать и не угадывать.
- WB WRITE, sibling-worktree mutations, automatic merge/deploy и destructive Jira operations запрещены.
- Один write-capable worker за раз. Stage только thread-owned files; `git add -A` запрещён.
- Durable task truth остаётся в Jira/Orca/Git. `.git/now/` хранит только ephemeral locks и append-only audit evidence.
- Gate: `RG-20260828-now-orchestrator`. Parent dirty checkout не мутировать.

## Jira operation classes

- AUTO: single-issue create/edit/comment/link/assign-Mike/transition внутри PA/PMM, только после pre-write ledger.
- APPROVAL_REQUIRED: delete/archive/bulk, foreign project, assignee не Mike, epic/scope replacement, multi-issue transition.
- DENY: secrets in payload, unsupported operation, missing project/key/account identity.

## Lifecycle

`SELECTED → CONFIRMED → DISPATCHED → VERIFYING → REVIEWING → MERGE_GATE → MERGED → SYNCING → DONE`.

Любой stale source, active lane conflict, zone overlap, missing evidence или failed write переводит в `BLOCKED_CONFLICT`/`BLOCKED_EXTERNAL`; no next task until reconciliation.

## Из таска 01 - R0 core

- `load_snapshot(input) -> Snapshot` - versioned normalization и mandatory source freshness.
- `select(snapshot) -> NowDecision` - hard-rule selector без LLM scoring.
- `render(decision) -> str` - byte-stable B/C/A cards и D FROZEN.
- CLI `scripts/agent/now` - read-only render entry point; Jira и network writes отсутствуют.
