# 01 — Процессный слой Release Cutter: все файлы и перенаправления

**Требования:** R01–R25, R28i, G01–G06 (R27 частично — материалы финального отчёта)
**Blocked by:** —
**Зона:** `.opencode/` · `docs/release-gates/` · `AGENTS.md` · `docs/agent-system/`
**Волна:** 1
**Status:** ready

## Что должно заработать

В репо появляется project-local слой Release Cutter: скилл, read-only субагент, две команды, README gate-документации, идемпотентная секция AGENTS.md и перенаправление briefmaker→release-critic в трёх документах. Продуктовый код не трогается. Повторная вставка секции не дублирует её.

## Из брифа, дословно

> «Создай `.opencode/skills/release-cutter/SKILL.md`. Frontmatter должен быть валидным и минимальным. Имя должно совпадать с директорией»
> «Это должен быть `subagent` с низкой температурой и read-only permissions»
> «Команда должна запускать `release-critic` как отдельный subtask и передавать ему `$ARGUMENTS`»
> «Не переписывай существующий `AGENTS.md`. Добавь одну компактную идемпотентную секцию»
> «Не делай commit и не делай push»

## Разделы спецификации

Истории 1–21, 23–25; Решения §1–§11; Границы и швы (таблица модулей); Приложение A брифа (шаблон отчёта).

## Файлы

Создать: `.opencode/skills/release-cutter/SKILL.md`, `.opencode/agents/release-critic.md`, `.opencode/commands/release-gate.md`, `.opencode/commands/release-task.md`, `docs/release-gates/README.md`.
Изменить точечно: `AGENTS.md` (секция между маркерами `<!-- release-gate:start -->`/`<!-- release-gate:end -->` после раздела «Orca coordinator protocol»; перенаправление briefmaker→release-critic в строках протокола и Quality pipeline; строка в «Карте контекста»), `docs/agent-system/ORCHESTRATION.md` (роль Briefmaker→Release-critic, шаг 2 цикла, словарь DISCOVERY_STATUS + NEEDS_APPROVAL), `docs/agent-system/README.md` (строка role-map).

## Ключевые контракты (из спеки, не выдумывать)

- Frontmatter SKILL.md: name, description (англ., из брифа), compatibility: opencode, metadata {role: release-gate, mode: read-only-analysis}. Без license.
- release-critic: mode: subagent, temperature: 0.1, steps: 30; permission: deny-all + allow: read (кроме секретов), glob, grep, list, skill, webfetch, websearch; bash granular (`*` deny; git status/log/show/diff/branch --show-current/rev-parse allow); Jira read-only (`jira-atlassian_*` deny первыми, затем allow: getJiraIssue, searchJiraIssuesUsingJql, getVisibleJiraProjects, getJiraProjectIssueTypesMetadata, getTransitionsForJiraIssue, fetch, getAccessibleAtlassianResources, atlassianUserInfo, lookupJiraAccountId, search); edit/write/task/todowrite/question/external_directory — deny.
- Отчёт Release Gate: шапка `## Gate` с полями Gate ID/Target release/Source roadmap item/Verdict/Handoff status/Confidence + DISCOVERY_STATUS строка в шапке И последней строкой. 13 секций по Приложению A брифа, дословно.
- DISCOVERY_STATUS-мэппинг: READY_AUTO→READY; DROP/DEFER→NOT_NEEDED; NEEDS_APPROVAL/NEEDS_INPUT/BLOCKED→напрямую.
- Gate ID: `RG-<YYYYMMDD>-<slug>`; файлы `docs/release-gates/<YYYY-MM-DD>-<slug>.md`.
- /release-gate: `agent: release-critic`, `subtask: true`, $ARGUMENTS, @файл входы, НЕ запускает Autopilot.
- /release-task: без agent-поля (основной контекст); ветки READY_AUTO (сохранить gate → skill autopilot → только раздел 12 + Scope lock поля → разрешить старт), NEEDS_APPROVAL (рекомендация + diff scope + одно решение + стоп до ответа), NEEDS_INPUT (реальный grill-me `~/.claude/skills/grill-me`, только блокирующая ветка, максимум Gate→Grill→Gate → иначе BLOCKED), BLOCKED (блокировка/кто снимет/минимальный шаг/независимые задачи).
- 10 правил Scope lock + оговорка про локальный рефакторинг — в SKILL.md и в release-task.md.
- Жёсткие ограничения G04: DECISIONS.md/ADR/фазовые контракты M1 — нельзя DROP/DEFER молча; пересмотр только NEEDS_APPROVAL со ссылкой на решение.
- Языки: SKILL.md-тело и команды русские; шаблон отчёта и секция AGENTS.md английские; docs README русский.
- Секция AGENTS.md — текст §15 брифа (адаптация стиля допустима, смысл сохранить).
- Антибюрократия: 10 правил §17 брифа в SKILL.md.

## Критерии приёмки

- [ ] Все 5 новых файлов существуют, YAML-frontmatter валиден (name=dir для скилла, description непустые)
- [ ] release-critic: mode subagent, edit/write deny, git read-only granular, Jira read-only, мутирующие инструменты deny
- [ ] /release-gate: agent release-critic + subtask true + $ARGUMENTS; /release-task не запускает Autopilot до завершения gate (текст команды это прямо запрещает)
- [ ] SKILL.md содержит: 8 шагов workflow, 6 вердиктов, 4 handoff + условия, 15 источников, 11 build-vs-buy критериев, 11 batch-механик, 10 правил Scope lock + оговорку, 10 антибюрократических правил, список запретов сокращения §8, полный шаблон отчёта, DISCOVERY_STATUS-мэппинг, жёсткие ограничения G04
- [ ] AGENTS.md: секция существует ровно один раз (пара маркеров единственная), стиль соседних секций сохранён, существующий текст вне маркеров не изменён
- [ ] briefmaker.md не изменён; все 3 документа перенаправлены на release-critic
- [ ] Продуктовый код не тронут; новый npm-пакетов нет; commit/push не делаются
- [ ] python3-валидация YAML всех 4 frontmatter проходит
- [ ] Материалы для финального отчёта (diff --stat, дерево файлов) воспроизводимы из дерева
