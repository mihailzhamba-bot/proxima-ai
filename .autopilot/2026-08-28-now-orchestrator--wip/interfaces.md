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

## Из таска 02 - Jira safe repair

- `authorize(intent) -> JiraDecision` - pure policy для `AUTO`, `APPROVAL_REQUIRED` и `DENY` до remote write.
- Append-only ledger в Git common-dir хранит safe intent digest до write и outcome только для ранее авторизованного intent.
- Jira adapter seam выполняет audit-before-write; live Jira mutation не запускалась без designated throwaway issue.
- CLI `scripts/agent/now` поддерживает Jira authorize/record flow; три facade используют один policy contract.
- Executable Jira mutation требует полный execution contract: Mike owner identity, lane, blockers, AC, DoD, Gate ID, evidence locators и file zones.
- Ledger сам повторно авторизует intent и связывает outcome с intent digest; forged caller decision не является authority.
- Повторный outcome допустим только после failed outcome и отдельного evidence-backed reconciliation event; success требует remote evidence ID.

## Из таска 03 - claims и lifecycle

- `claim(request) -> ClaimResult` и owner-token release управляют atomic track/zone claims в Git common-dir.
- Один global integration lease сериализует integration; stale recovery требует отдельного audit evidence.
- `advance(command, snapshot) -> ActionPlan` fail closed проводит lifecycle и запрещает `DONE` без merge + source convergence.
- `/now go <KEY>` во всех трёх facade возвращает один deterministic `ActionPlan`; фактический Orca dispatch остаётся T04.
- Resume разрешён только при exact immutable identity: key, owner, track, zones, run/task/worker provenance и snapshot identity.
- Stale recovery и `DONE` принимают typed evidence с locators; caller booleans и free text не являются доказательством.
- T03 `/now go` заканчивается `CONFIRMED` с `should_dispatch`; переход `DISPATCHED` выполняет только T04 после фактического worker dispatch.
- Claim связывается с canonical SHA-256 полного normalized snapshot; одинаковые timestamps не разрешают resume изменённого content.
- `ClaimRequest.snapshot_digest` обязателен, canonical lower 64-hex и входит в token material; synthetic default отсутствует.
- Stale lease recovery использует bounded typed liveness evidence и write-ahead intent/outcome audit вокруг удаления.

## Из таска 04 - integration и close

- `ReleaseGateReport.read(repo_root, report_path, gate_id, task_key, snapshot_digest)` читает approved Markdown, требует единственный READY header + READY tail и связывает SHA-256 Scope lock с task/snapshot; caller booleans отсутствуют.
- `IntegrationCoordinator.dispatch(DispatchInput)` повторно читает exact persisted claim, ведёт append-only WAL intent/outcome, reconcile-ит Orca task + dispatch + worker и принимает только exact `result.messages[]` worker_done. Integration lease имеет одноразовый fencing token и снимается в `finally` на каждом terminal error.
- `ReviewerCoordinator.verify_and_review(ReviewInput)` независимо читает Orca placement, Git common-dir + reviewed HEAD, запускает captured `make verify` и reviewer в exact worker cwd и выдаёт durable digest-bound receipt; caller 0/0 не авторитетен.
- `CloseCoordinator.close(CloseInput)` перечитывает review/Mike/merged-ops receipts через trusted ports; gh связывает repo/base/head/merge ancestry, Jira - issue/transition/payload digest и readback-first retry, Orca - exact released identity, repo convergence - blob SHA канонических HANDOFF/TASKS/active ExecPlan из ops commit. Codex без port возвращает `BLOCKED_EXTERNAL`; Claude/opencode CLI выдаёт только side-effect plan.
- `OpsRepoSync.sync(OpsSyncInput)` требует independent Mike approval, ведёт WAL по worktree/write/stage/commit/push/PR, reconciles retry before effect и пишет через dirfd/no-follow. `git add -A`, automatic merge и path escape отсутствуют.
- `claude_entry`, `codex_entry`, `opencode_entry` вызывают один `_entry` core; CLI routes `facade <client>` проверяются на byte-identical full stdout.
