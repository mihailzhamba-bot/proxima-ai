# Интерфейсы — Release Cutter

## Границы, решённые в спецификации

| Модуль | Владеет | Выставляет | Прячет |
|---|---|---|---|
| `release-cutter` SKILL.md | методологию gate: workflow, вердикты, handoff, формат отчёта, антибюрократию | себя через skill tool | ничего |
| `release-critic` agent | исполнение аудита: research репо+Jira, генерация отчёта | subagent `release-critic` через Task tool / команду | ничего |
| `/release-gate` command | запуск критика subtask'ом | slash-команду с $ARGUMENTS/@файл | ничего |
| `/release-task` command | оркестрацию handoff-веток + сохранение gate + передачу autopilot | slash-команду | ничего |
| `docs/release-gates/` | утверждённые gate-отчёты + README | файлы-контракты Scope lock | ничего |
| AGENTS.md секция | правило «когда gate обязателен» | маркерную идемпотентную секцию | ничего |

## Контракты, которые нельзя нарушать

- Отчёт: шапка `## Gate` (Gate ID `RG-<YYYYMMDD>-<slug>` / Target release / Source roadmap item / Verdict / Handoff status / Confidence) + DISCOVERY_STATUS в шапке и последней строкой; 13 секций по Приложению A брифа.
- DISCOVERY_STATUS-мэппинг: READY_AUTO→READY; DROP/DEFER→NOT_NEEDED; NEEDS_APPROVAL/NEEDS_INPUT/BLOCKED→напрямую.
- Вердикты: KEEP / REUSE / SHRINK / DEFER / DROP / BLOCKED. Handoff: READY_AUTO / NEEDS_APPROVAL / NEEDS_INPUT / BLOCKED.
- Gate-файлы: `docs/release-gates/<YYYY-MM-DD>-<slug>.md`.

## Правила проекта для субагента

- Стек: OpenCode 1.18.23; структура `.opencode/skills|agents|commands`; permissions по wildcard-паттернам, last-match-wins, deny-заглушки первыми.
- Языки: тело SKILL.md и команды — русские; шаблон отчёта и секция AGENTS.md — английские; docs/release-gates/README.md — русский. Идентификаторы английские.
- Продуктовый код, `Makefile`, `package.json`, `infra/*`, `services/*`, `.planning/*` — не трогать. Новые npm-зависимости запрещены (= BLOCKED).
- `.opencode/agents/briefmaker.md` не изменять (решение Mike).
- AGENTS.md: всё вне маркеров `<!-- autopilot:start -->`…`<!-- autopilot:end -->` и вне новой пары `<!-- release-gate:start -->`…`<!-- release-gate:end -->` не трогать; `git add -A` запрещён; commit/push не делать.
- Отсутствующая зависимость = BLOCKED с объяснением, не установка.
- Dirty-tree: в репо несвязанные незакоммиченные изменения (Makefile, README, package.json, .planning/STATE.md, untracked .mcp.json и др.) — не трогать, не revertить, не стейджить.

## Из таска 01 — процессный слой

- SKILL.md release-cutter: полное кл слово methodology (8 шагов, 6 вердиктов, 4 handoff, DISCOVERY_STATUS-мэппинг, batch, антибюрократия, G04-ограничения); шаблон отчёта = Приложение A брифа
- release-critic: subagent deny-all + read/glob/grep/list/skill/webfetch/websearch + git-readonly bash + jira read-only (15 allow после deny-заглушки: 10 из спеки + getIssueLinkTypes + 4 Confluence-чтения, все только чтение)
- /release-gate: agent release-critic subtask true; /release-task: без agent, 4 ветки handoff
- Gate ID RG-<YYYYMMDD>-<slug>; отчёты в docs/release-gates/<YYYY-MM-DD>-<slug>.md
- AGENTS.md: секция между release-gate-маркерами (после Orca-протокола); briefmaker→release-critic в 3 док-ах
- Валидация: python3 yaml-парс 4 frontmatter + grep-инварианты (1 маркер, name=dir, deny-поля)
