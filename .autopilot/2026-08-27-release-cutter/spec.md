# Спецификация: Release Cutter — шлюз между планированием и Autopilot

## Задача

Майк диктует задачи агентам. Часть задач попадает в Autopilot слишком толстой: универсальные платформы вместо одного адаптера, гипотетические будущие сценарии вместо проверяемого результата. Grill Me уточняет решения, но не спрашивает «нахуя это нужно вообще». Нужен обязательный read-only критик между планированием и выполнением, который доказательно находит самый дешёвый безопасный путь до проверяемого релиза и имеет право сказать «задача не нужна» — с доказательствами, а не вкусом модели.

## Решение

В репо появляется третий слой пайплайна: скилл `release-cutter` (методология), субагент `release-critic` (read-only исполнитель), команды `/release-gate` (аудит без запуска Autopilot) и `/release-task` (оркестрация: gate → grill при нужде → gate → Autopilot с заблокированным scope). release-critic заменяет briefmaker в пайплайне major/critical (решение Mike), выдаёт отчёт Release Gate с вердиктом KEEP/REUSE/SHRINK/DEFER/DROP/BLOCKED, handoff-status и машинно-читаемой строкой DISCOVERY_STATUS для Orca-парсера. Утверждённые gate-отчёты живут в docs/release-gates/ и служат Scope lock'ом для Autopilot.

## Пользовательские истории

| # | Метка | История | Приёмка |
|---|-------|---------|---------|
| 1 | R01 | Как Mike, я запускаю gate на задачу, чтобы не строить лишнего | скилл release-cutter обнаружим в .opencode/skills/, frontmatter валиден, name=dir |
| 2 | R02 | Как Mike, я хочу, чтобы критик мог сказать «задача не нужна» — но доказательно | в SKILL.md право DROP + обязанность Evidence/Assumption/Unknown |
| 3 | R03 | Как Mike, я хочу полный чек-лист сокращения до запуска Autopilot | 10 обязанностей + 11 возможностей сокращения перечислены в SKILL.md |
| 4 | R04 | Как Mike, я не хочу «генератор сомнений» | правило доказательств + S/M/L оценки в SKILL.md |
| 5 | R05 | Как Mike, я хочу build-vs-buy проверку готовых решений | чек-лист TCO + NOT VERIFIED маркер без интернета |
| 6 | R06–R11 | Как Mike, я хочу обязательный workflow из 8 шагов | шаги 1–8 в SKILL.md дословно по брифу; шаги включают: 15 источников исследования (§5), 11 критериев build-vs-buy (§6), 11 механик batch-режима (§10: dependency graph, критический путь, классификация RELEASE-BLOCKING/SUPPORTING/POST-RELEASE/DROP/NEEDS-EVIDENCE, параллельность, преждевременные платформы, дублирование, задачи-следствия сложных решений, Release 0/1/Later/Drop, без аудита каждого микротаска, один gate на epic) |
| 7 | R12, R13 | Как Mike, я хочу однозначные вердикты и статусы передачи | 6 вердиктов + 4 handoff + условия READY_AUTO/NEEDS_APPROVAL |
| 8 | R14 | Как Mike, я не хочу небезопасную поделку ради короткого diff | список запретов сокращения §8 в SKILL.md |
| 9 | R15 | Как Mike, я хочу сопоставимые отчёты | шаблон 13 секций + шапка `## Gate` — Приложение A брифа (§9, дословно); SKILL.md и release-task.md воспроизводят его полностью; критик выдаёт отчёт строго по шаблону |
| 10 | R16 | Как Mike, я даю на вход roadmap/epic — получаю batch-разбор | batch-режим с Release 0/1, один gate на epic |
| 11 | R17 | Как Mike, я не хочу бюрократию | 10 антибюрократических правил, включая KEEP/READY_AUTO |
| 12 | R18 | Как Mike, я хочу read-only критика, который ничего не ломает | subagent, temp 0.1, edit/write deny, git read-only, Jira read-only |
| 13 | R19 | Как Mike, я запускаю /release-gate PMM-7 — получаю отчёт без запуска Autopilot | команда agent: release-critic, subtask: true, $ARGUMENTS |
| 14 | R20 | Как Mike, я запускаю /release-task — и до ответа gate ничего не строится | ветвление по 4 handoff-status, включая grill-me цикл ≤1 |
| 15 | R21 | Как Mike, я хочу, чтобы Autopilot не расползался за scope | 10 правил Scope lock в SKILL.md + release-task.md; оговорка: локальный рефакторинг разрешён только когда необходим для утверждённого поведения и входит в тот же тестируемый slice |
| 16 | R22 | Как Mike, я хочу одно правило в AGENTS.md, а не гейт на каждую строчку | компактная идемпотентная секция с маркерами |
| 17 | R23 | Как участник команды, я читаю README и понимаю систему | docs/release-gates/README.md покрывает 10 тем из брифа |
| 18 | R24–R27 | Как Mike, я хочу проверенную реализацию | статическая верификация + dry-run PMM-7 → отчёт DRY-RUN |
| 19 | R27 | Как Mike, я хочу итог одним отчётом с diff | финальный отчёт §19, без commit/push |
| 20 | R28i | Как Mike, я не хочу тронутый продуктовый код | правки только в .opencode/*, docs/*, AGENTS.md, .autopilot/* |
| 21 | G01, G02 | Как Orca-координатор, я диспетчеризую release-critic вместо briefmaker | ссылки AGENTS.md/ORCHESTRATION.md/README.md перенаправлены; briefmaker.md на месте |
| 22 | G03 | Как Orca-парсер, я читаю DISCOVERY_STATUS из gate-отчёта | последняя строка отчёта DISCOVERY_STATUS: READY/NEEDS_APPROVAL/NEEDS_INPUT/NOT_NEEDED/BLOCKED |
| 23 | G04 | Как Mike, я хочу неприкосновенные решения | DECISIONS/ADR/фазовые контракты — жёсткие ограничения; пересмотр только NEEDS_APPROVAL со ссылкой |
| 24 | G05 | Как Mike, я даю PA-XX ключ — критик сам тянет задачу из Jira | read-only Jira MCP права в release-critic.md |
| 25 | G06 | Как Mike, я хочу согласованные конвенции | языки/Gate ID/dry-run/Task tool legacy — по плану |

## Решения по реализации

1. **Структура — нативная для OpenCode 1.18.23** (проверено по докам): `.opencode/skills/release-cutter/SKILL.md`, `.opencode/agents/release-critic.md`, `.opencode/commands/*.md`. Существующий плюрализм `agents/` сохраняем — в репо он уже работает (reviewer, briefmaker).
2. **Frontmatter SKILL.md** — только распознаваемые поля: name, description, compatibility: opencode, metadata (string-to-string): role=release-gate, mode=read-only-analysis. Поле license не добавляем — бриф не задавал, frontmatter минимальный.
3. **Permissions release-critic** — паттерн briefmaker (deny-all + точечные allow): read (кроме секретов), glob/grep/list, skill, webfetch, websearch; bash granular: `*` deny + git status/log/show/diff/branch --show-current/rev-parse allow; Jira MCP: `jira-atlassian_*` deny + read-инструменты allow (getJiraIssue, searchJiraIssuesUsingJql, getVisibleJiraProjects, getJiraProjectIssueTypesMetadata, getTransitionsForJiraIssue, fetch, getAccessibleAtlassianResources, atlassianUserInfo, lookupJiraAccountId, search); edit/write/bash-mutations/task/todowrite/question/external_directory — deny. Порядок правил: last-match-wins, deny-заглушки первыми.
4. **Двойной выходной контракт**: отчёт каноничен; строка `DISCOVERY_STATUS: …` стоит и в шапке (блок `## Gate`), и последней строкой отчёта. Отображение: READY_AUTO→READY, DROP/DEFER→NOT_NEEDED, NEEDS_APPROVAL/NEEDS_INPUT/BLOCKED→напрямую. Словарь DISCOVERY_STATUS расширяется значением NEEDS_APPROVAL — прямое следствие решения Mike «Двойной формат»; фиксируется в ORCHESTRATION.md вместе с перенаправлением briefmaker→release-critic (одно изменение роли, один документ).
5. **Языки**: SKILL.md-тело и команды — русские; шаблон отчёта (Приложение A, дословно из брифа) и секция AGENTS.md — английские; docs/release-gates/README.md — русский. Почему: briefmaker-прецедент + бриф даёт английские шаблоны.
6. **Gate ID**: `RG-<YYYYMMDD>-<slug>`; файл `docs/release-gates/<YYYY-MM-DD>-<slug>.md`. Дочерние задачи ссылаются на Gate ID в своём описании/Jira.
7. **/release-task при READY_AUTO**: сохраняет gate, грузит реальный скилл `autopilot` (~/.agents/skills/autopilot), передаёт только раздел 12 + поля Scope lock (Gate ID; In scope; Explicitly out of scope; Must reuse; Must not introduce; acceptance criteria; verification; rollback; stop conditions); «Разрешить начать реализацию автоматически» — реализация стартует сразу после сохранения gate, способ запуска определяется контекстом сессии. Ветвление: NEEDS_APPROVAL — показать рекомендацию, показать разницу исходного и сокращённого scope, запросить одно конкретное решение, не стартовать до ответа, после подтверждения сохранить gate и продолжить; NEEDS_INPUT — вызвать реальный grill-me (~/.claude/skills/grill-me), передать только блокирующую ветку, максимум один цикл Gate→Grill→Gate, иначе BLOCKED; BLOCKED — показать конкретную блокировку, кто/что её снимает, минимальный следующий шаг, какие задачи можно делать независимо. /release-gate никогда не стартует Autopilot.
8. **Идемпотентность AGENTS.md**: секция между `<!-- release-gate:start -->` / `<!-- release-gate:end -->`, вставка только при отсутствии маркера; перенаправление briefmaker→release-critic в 3 документах точечными правками (AGENTS.md строки протокола Orca + Quality pipeline; ORCHESTRATION.md роли и цикл; docs/agent-system/README.md role-map). briefmaker.md не трогаем; он остаётся в списке Task tool как legacy-агент без вызовов — фиксируем это как известное ограничение в финальном отчёте.
9. **Верификация**: (а) встроенные команды проверки OpenCode — проверить их существование для 1.18.23 (`opencode --help`, доки Commands/Agents/Skills); в 1.18.23 нет невзаимодействующей команды валидации discovery — подтверждение зафиксировать в финальном отчёте; (б) YAML-парс frontmatter (python3 yaml, fallback uv run --with pyyaml); (в) статические проверки структуры; (г) dry-run PMM-7 через Jira MCP с маркером DRY-RUN; если Jira MCP недоступен в сессии dry-run — синтетический пример из §18.6 брифа (универсальная платформа коннекторов), ожидаемое направление SHRINK/REUSE.
10. **Без commit/push** — финальный diff показывается, коммитит Mike (правило задачи + dirty-tree репо).
11. **Зона правок**: .opencode/*, docs/*, AGENTS.md — по брифу; `.autopilot/*` — рабочая запись самого прогона автопилота (регламент скилла autopilot), служебная документация процесса, не продуктовый код; продуктовый код не трогаем.

## Границы и швы

| Модуль | Владеет | Выставляет | Прячет |
|---|---|---|---|
| `release-cutter` SKILL.md | методологию gate: workflow, вердикты, handoff, формат отчёта, антибюрократию | себя через skill tool | ничего (документ-инструкция) |
| `release-critic` agent | исполнение аудита: research репо+Jira, генерация отчёта | subagent `release-critic` через Task tool / команду | ничего |
| `/release-gate` command | запуск критика subtask'ом | slash-команду с $ARGUMENTS/@файл | ничего |
| `/release-task` command | оркестрацию handoff-веток + сохранение gate + передачу autopilot | slash-команду | ничего |
| `docs/release-gates/` | утверждённые gate-отчёты + README | файлы-контракты Scope lock | ничего |
| AGENTS.md секция | правило «когда gate обязателен» | маркерную идемпотентную секцию | ничего |

Швы тестов (статические, единственные здесь):
1. **Frontmatter-шов**: YAML-структура всех 4 файлов .opencode/* (name=dir, mode: subagent, deny-поля, agent/subtask команды).
2. **Контракт отчёта**: 13 секций + финальная строка DISCOVERY_STATUS — проверяется на dry-run отчёте.
3. **Идемпотентность**: единственная пара маркеров release-gate в AGENTS.md.

## Вне рамок

| Требование | Почему не сейчас |
|---|---|
| npm-пакет / плагин / MCP-сервер | прямо запрещено брифом §3 |
| .claude/ и .codex/ копии release-critic | бриф просит project-local opencode-реализацию; паритет инструментов — отдельным решением |
| Автозапуск Autopilot из /release-gate | прямо запрещено брифом §12 |
| Изменение briefmaker.md | решение Mike: файл оставить, ссылки перенаправить |
| Модификация продуктового кода | прямо запрещено брифом |

## Открытые места

Нет placeholder-строк: фактов от пользователя, которых не хватает, нет.

## Покрытие манифеста

| Требование | Раздел спецификации |
|---|---|
| R01–R17 | История 1–11; Решения §2, §5; SKILL.md-структура в Решениях |
| R18 | История 12; Решение §3 |
| R19 | История 13; Решение §7 |
| R20 | История 14; Решение §7 |
| R21 | История 15; Решение §7 |
| R22 | История 16; Решение §8 |
| R23 | История 17 |
| R24 | Решение §1 (исследование проведено до спеки) |
| R25 | Решение §9; швы 1–3 |
| R26 | История 18; Решение §9 |
| R27 | История 19; Решение §10 |
| R28i | История 20; Вне рамок |
| G01, G02 | История 21; Решение §8 |
| G03 | История 22; Решение §4 |
| G04 | История 23; SKILL.md-раздел жёстких ограничений |
| G05 | История 24; Решение §3 |
| G06 | История 25; Решения §5, §6, §9 |
