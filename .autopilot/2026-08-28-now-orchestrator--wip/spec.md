# Спецификация: `/now` - проектный оркестратор PROXIMA AI

## Задача

Mike не должен вручную сводить Jira, Git/PR/worktrees, Orca и repo-документы, чтобы понять, какую работу делать следующей. Оркестратор обязан восстановить фактическое состояние, показать одну конкретную задачу на каждый активный трек, не запустить конфликтующую работу и довести подтверждённую задачу до явного merge gate.

## Решение

Появится единый вызов `/now` в Codex, Claude Code и opencode. Все три клиента собирают один нормализованный snapshot, передают его одному deterministic core и показывают одинаковые карточки Track B, C, A; Track D всегда FROZEN. После команды `/now go <KEY>` существующий Orca pipeline запускает только подтверждённую задачу. Safe Jira drift исправляется через allowlist и pre-write audit; неоднозначность, пересечение зон, stale evidence или unsafe mutation останавливают цикл.

### Как позднее утверждение плана уточняет исходную диктовку

Дополнение «Implement the plan.» утверждает Scope lock Gate `RG-20260828-now-orchestrator`. Поэтому три широкие формулировки исходного brief имеют следующие операционные границы:

- «Пока не закончим, не касаемся» означает одну write-задачу внутри каждого Track и запрет любого пересечения file zones; независимые A/B/C могут идти параллельно, но integration сериализован одним lock.
- «полностью автономны агент» означает автономный цикл после `/now go <KEY>` до `MERGE_GATE`; merge, deploy и destructive actions остаются explicit gates Mike, после merge агент автономно завершает sync до Done.
- «если он видит чего-то не хватает, он также добавляет это» означает автоматический allowlisted Jira repair для однозначного gap; неоднозначный, destructive или scope-changing gap фиксируется как blocked proposal, потому что его автоматическое добавление изменило бы утверждённый scope.

Остальные детали - три client adapters, deterministic core, B > C > A, D FROZEN, Jira allowlist/ledger, file zones, integration lock, state machine, reviewer и ops worktree - являются не новыми инициативами спецификации, а решениями утверждённого плана и Gate `RG-20260828-now-orchestrator`.

## Пользовательские истории

| # | Метка | История | Приёмка |
|---:|---|---|---|
| 1 | R01 | Как Mike, я вызываю одного оркестратора из любого поддержанного агента | `/now` доступен в трёх клиентах и использует один core |
| 2 | R01.1 | Как Mike, при первом запуске без runtime state я получаю диагностический результат | показаны missing sources и команда восстановления, ничего не мутировано |
| 3 | R02 | Как Mike, я получаю одну рекомендуемую задачу сейчас | ответ содержит ровно одну рекомендацию и evidence timestamp |
| 4 | R02.1 | Как Mike, при пустом ready backlog я вижу `BLOCKED` или `WAITING_FOR_DECISION` | задача не выдумывается |
| 5 | R03 | Как Mike, я вижу целостную последовательность от выбора до Done | карточка показывает текущий state и следующий gate |
| 6 | R03.1 | Как Mike, при расхождении источников я вижу conflict, а не ложную рекомендацию | conflict содержит источники и прекращает write path |
| 7 | R04 | Как Mike, я вижу отдельную карточку для Track B, C и A | порядок вывода B, C, A; по одной карточке на трек |
| 8 | R04.1 | Как Mike, я всегда вижу Track D как `FROZEN` | D не имеет start action до отдельного решения Mike |
| 9 | R05 | Как Mike, я не запускаю вторую write-задачу в том же треке | same-track claim отклонён до terminal state первой задачи |
| 10 | R05.1 | Как Mike, я не запускаю две задачи с пересекающимися file zones | overlap детерминированно найден до worker-start |
| 11 | R06 | Как Mike, я подтверждаю конкретный Jira key командой `/now go <KEY>` | без точного key dispatch не создаётся |
| 12 | R06.1 | Как Mike, повторная команда после interruption безопасно resumes run | дубль task/worker не создаётся |
| 13 | R07 | Как Mike, я получаю verify и независимый review до merge gate | green evidence и reviewer verdict обязательны |
| 14 | R07.1 | Как Mike, failed verify оставляет задачу `BLOCKED`, не Done | failure location, cause и recovery записаны |
| 15 | R08 | Как Mike, результат закрепляется после явного merge gate и автономного sync | Done невозможен до Git, Jira, Orca и repo mirrors convergence |
| 16 | R08.1 | Как Mike, merge остаётся моим явным gate | core никогда не выполняет merge автоматически |
| 17 | R09 | Как Mike, я получаю глубокое объяснение выбора | карточка содержит owner, blockers, AC, DoD, sources и decision rule |
| 18 | R10 | Как Mike, оркестратор сначала ищет уже готовую или начатую работу | lifecycle closure выше новой ready-задачи |
| 19 | R10.1 | Как Mike, чужой lane не дублируется | active owner/worktree/PR блокирует второй start |
| 20 | R11 | Как Mike, я получаю решение, а не список идей | рекомендации не содержат больше одного next action на трек |
| 21 | R12 | Как Mike, после подтверждения цикл автономен до merge gate и после merge автономно закрывает sync | обычные repair/verify/review/sync переходы не требуют новых команд |
| 22 | R12.1 | Как Mike, deploy и destructive actions не входят в автономность | требуется отдельный explicit approval |
| 23 | R13 | Как Mike, я могу спросить «что делаем сейчас» без знания внутреннего pipeline | facade сам выполняет recovery и reconciliation |
| 24 | R14 | Как Mike, я вижу конкретный Jira key и причину выбора | generic recommendation без key запрещена |
| 25 | R15 | Как Mike, обнаруженный gap становится управляемой Jira-работой | in-scope blocker linked к current; остальное создаётся/обновляется в backlog |
| 26 | R15.1 | Как Mike, неоднозначный gap не мутирует Jira | возвращается proposed repair с approval reason |
| 27 | R16 | Как Mike, safe Jira create/edit/comment/link/assign/transition выполняются автоматически | только PA/PMM, allowlist и audit-before-write |
| 28 | R16.1 | Как Mike, delete/archive/bulk никогда не выполняются автоматически | policy возвращает `APPROVAL_REQUIRED` |
| 29 | R17 | Как Mike, Jira issue получает развёрнутый execution contract | owner, lane, blockers, AC, DoD, Gate ID, evidence locators и zones заполнены |
| 30 | R18 | Как Mike, новая task назначается на меня | assignee Mike; неизвестный account id блокирует mutation |
| 31 | G01 | Как Mike, реализация идёт под Autopilot | brief, manifest, spec, tickets, review и final evidence сохраняются |
| 32 | G02 | Как Mike, утверждённый план реализуется без повторного scope-интервью | Gate `RG-20260828-now-orchestrator` является Scope lock |
| 33 | G02.1 | Как Mike, repo state синхронизируется отдельным ops worktree/PR | parent dirty tree не стейджится и не мутируется |
| 34 | G02.2 | Как Mike, одновременно возможна одна write-задача на A/B/C | разные треки разрешены только при непересекающихся zones |
| 35 | G02.3 | Как Mike, integration выполняется через один глобальный lock | lock atomic, observable, recoverable и release documented |

## Deep-pass: состояния и края

Обозначения: `FR` first run, `E` empty, `W` wrong input, `F` failure, `I` interruption, `G` growth, `B` boundaries, `A` aftermath.

| Требование | FR | E | W | F | I | G | B | A |
|---|---|---|---|---|---|---|---|---|
| R01-R04 | diagnostics | no candidates | invalid snapshot | source unavailable | rerun idempotent | bounded snapshot | repo PA/PMM only | cards only |
| R05-R06 | no claims | no key | malformed key/zones | Orca unavailable | resume same run | 3 track claims max | Mike confirmation | worker dispatch |
| R07-R08 | no evidence | no review | invalid verdict | verify red | retry same commit | evidence references | reviewer + Mike gate | merged then sync |
| R09-R11 | source legend | unknown is explicit | stale timestamp | conflict card | stable snapshot id | compact per-track output | read-only selection | one recommendation |
| R12-R14 | no run | no task | foreign key | dispatch fails | recovery by provenance | one run per accepted key | no merge/deploy | merge gate |
| R15-R18 | no ledger | no repairs | unsafe operation | MCP write fails | reconcile before retry | append-only ledger | PA/PMM allowlist | Jira evidence |
| G01-G02 | new run artifacts | no ticket yet | scope mismatch | gate stop | resume state.js | ticket queue | Scope lock | final blind check |

Все `E/W/F/I/G/B/A` ответы выражены историями Rxx.1/G02.x или детерминированными решениями ниже. Неприменимых визуальных empty/loading states нет: `/now` - текстовый operational facade.

## Решения по реализации

### 1. Единый core и adapters

- Один Python core на стандартной библиотеке владеет моделями snapshot/card, priority rules, drift policy, Jira authorization, locks и state transitions. Причина: одинаковая логика во всех клиентах без новой runtime dependency.
- Claude Code, Codex и opencode adapters только собирают live evidence разрешёнными инструментами, вызывают core и выполняют возвращённый action plan. Причина: LLM не ранжирует и не решает safe/unsafe policy.
- Snapshot имеет version, `captured_at`, source freshness и отдельные typed sections: Jira issues; Git branches/PR/worktrees; Orca runs/tasks/workers/gates; parsed `HANDOFF`; parsed `TASKS`; список и статусы active ExecPlans. `HANDOFF`, `TASKS` и ExecPlans загружаются и сверяются при каждом initial `/now`, а не только во время close transaction. Неполный обязательный source делает snapshot degraded и запрещает mutations.

### 2. Priority policy

В каждом Track A/B/C core выбирает кандидата по жёсткому порядку:

1. `CONTINUE` незавершённую owned task.
2. `CLOSE_CURRENT` для реализованной работы с verify/review/Jira/doc хвостом.
3. `UNBLOCK` ближайший product/release gate.
4. `START` ready task по dependency critical path.
5. Jira priority, затем меньший safe slice, затем Jira key как стабильный tie-break.

Карточки сортируются B, C, A. Первая незаблокированная карточка становится recommendation. D рендерится отдельно как FROZEN и никогда не попадает в selector.

### 3. Confirmation и lifecycle

Состояния: `SELECTED → CONFIRMED → DISPATCHED → VERIFYING → REVIEWING → MERGE_GATE`; после явного merge approval и фактического merge цикл продолжается `MERGED → SYNCING → DONE` без нового подтверждения. Ошибка переводит в `BLOCKED_CONFLICT` или `BLOCKED_EXTERNAL`; retry разрешён только из того же snapshot/task provenance. `/now` read-only. `/now go <KEY>` создаёт `CONFIRMED` только если key совпадает с последним snapshot и не устарел.

### 4. Jira policy и audit

- Auto-allow: create issue, edit fields/description, comment, link, assign Mike, transition одной issue внутри PA/PMM.
- Approval-only: delete, archive, bulk, epic/scope replacement, foreign project, assignee не Mike, transition нескольких issues.
- До MCP call core записывает intent, issue/project, operation, safe payload digest, actor, timestamp и decision в append-only ledger. Значения секретов и полное тело комментария не пишутся.
- После MCP call adapter записывает outcome и remote evidence id. Неуспешный call не повторяется, пока live read не подтвердит отсутствие эффекта.

### 5. Concurrency и integration lock

- Active track claims и declared file zones проверяются до создания worktree/worker.
- Zones - repo-relative path prefixes; пустая, root-wide, unresolved glob или пересечение с active zone блокируют start.
- Ephemeral claims и integration lease живут в общем Git administrative dir, а durable truth остаётся в Orca/Jira/Git. Lease создаётся atomically, содержит task/run/owner/timestamp и освобождается только owner-ом либо explicit force-release с audit reason.
- Один integration lease на repository. Leaked lease recovery сначала доказывает отсутствие живого owner/task/worker.

### 6. Execution и close transaction

- Dispatch переиспользует Release Gate, Autopilot, Orca supervised worker, `make verify` и reviewer. Новый scheduler/state engine запрещён.
- Repo mirrors обновляются только в isolated ops worktree; stage allowlist строится из thread-owned files, `git add -A` запрещён.
- Close transaction сравнивает merge commit, Orca terminal state, Jira status/evidence, HANDOFF, TASKS и active ExecPlan. `DONE` выставляется последним и только при полном convergence.
- Merge, deploy, production/config destructive operations не выполняются facade-ом.

## Границы и швы

| Модуль | Владеет | Выставляет | Прячет |
|---|---|---|---|
| `snapshot` | нормализованное состояние Jira, Git/PR/worktrees, Orca, HANDOFF, TASKS, active ExecPlans и freshness | `load_snapshot(input) -> Snapshot` | отдельные source loaders, parsing и normalization |
| `selector` | deterministic priority rules и cards | `select(snapshot) -> NowDecision` | tie-break и conflict resolution |
| `jira_policy` | allowlist, approval boundary, ledger intents | `authorize(intent) -> JiraDecision`; `record(result)` | payload digest и audit serialization |
| `claims` | track/zone claims и integration lease | `claim(request) -> ClaimResult`; `release(token)` | Git common-dir locking и recovery proof |
| `lifecycle` | `/now go` transitions и close convergence | `advance(command, snapshot) -> ActionPlan` | state-machine guards |
| `renderer` | единый textual card format | `render(decision) -> str` | stable formatting |
| client adapters | live tool collection и approved side effects | `/now`; `/now go <KEY>` | client-specific MCP invocation |

Швы для тестов: публичные pure функции `select`, `authorize`, `advance`, `render`; filesystem seam только у `claims` и ledger. Все adapters проверяются одной golden fixture, чтобы card output был byte-identical.

## Вне рамок

| Требование | Почему не сейчас |
|---|---|
| Нет отложенных требований | Все 20 строк покрыты; explicit non-goals Gate не являются требованиями brief |

Не строим scheduled unattended runs, Jira delete/archive/bulk, новый orchestration service, product code, migrations, WB writes, automatic merge/deploy и mutations sibling-worktrees.

## Открытые места

Нет placeholders. Live fire-test Jira выполняется только если Mike отдельно укажет throwaway issue; без него acceptance закрывается policy/fixture tests и config smoke без внешней mutation.

## Покрытие манифеста

| Требование | Раздел спецификации |
|---|---|
| R01 | Истории 1-2; Решения 1 |
| R02 | Истории 3-4; Решения 2 |
| R03 | Истории 5-6; Решения 2-3 |
| R04 | Истории 7-8; Решения 2 |
| R05 | Истории 9-10; Решения 5 |
| R06 | Истории 11-12; Решения 3 |
| R07 | Истории 13-14; Решения 6 |
| R08 | Истории 15-16; Решения 3, 6 |
| R09 | История 17; Решения 1-2 |
| R10 | Истории 18-19; Решения 2 |
| R11 | История 20; Решения 2 |
| R12 | Истории 21-22; Решения 3, 6 |
| R13 | История 23; Решения 1 |
| R14 | История 24; Решения 2 |
| R15 | Истории 25-26; Решения 4 |
| R16 | Истории 27-28; Решения 4 |
| R17 | История 29; Решения 4, 6 |
| R18 | История 30; Решения 4 |
| G01 | История 31; Autopilot lifecycle |
| G02 | Истории 32-35; Решения 1-6 |
