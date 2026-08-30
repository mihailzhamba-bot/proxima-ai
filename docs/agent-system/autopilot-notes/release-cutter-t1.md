# Release Gate-слой - память яруса T1

> Перенесено из `AGENTS.md` 30.08.2026 (bmad-project-context). Память автопилота на момент прогона release-cutter (27.08.2026); не текущие требования - актуальное в `/STATE.md`, `/DECISIONS.md`, блоке `bmad:context` в `AGENTS.md`.

## Release Gate-слой - память яруса T1

Прогон 2026-08-27 release-cutter сдан. Read-only шлюз между планированием и Autopilot: критик доказательно ищет самый дешёвый безопасный путь до проверяемого релиза и имеет право сказать «задача не нужна» - с доказательствами, не вкусом модели.

### Пайплайн

Три слоя: `grill-me` (что именно делаем, какие решения не приняты) → `release-cutter` (нужно ли вообще, можно ли дешевле/переиспользовать) → `autopilot` (реализует только согласованный минимум). В пайплайне Orca major/critical `release-critic` занял место briefmaker (решение Mike): research репо + Jira → отчёт Release Gate.

### Команды

- `/release-gate <задача|PA-XX|PMM-XX|@файл>` - только аудит, НИКОГДА не запускает Autopilot; ключ Jira критик сам тянет через jira-atlassian MCP read-only.
- `/release-task <задача>` - оркестрация: gate → handoff-ветки (NEEDS_INPUT → реальный скилл grill-me, максимум один цикл Gate→Grill→Gate) → сохранение gate → Autopilot получает только раздел 12 отчёта + поля Scope lock.

### Структура

- `.opencode/skills/release-cutter/SKILL.md` - методология: workflow 8 шагов, вердикты, handoff, шаблон отчёта (13 секций)
- `.opencode/agents/release-critic.md` - субагент: deny-all + read/glob/grep/list/skill/webfetch/websearch, bash только git-readonly, Jira/Confluence только чтение
- `.opencode/commands/release-gate.md`, `.opencode/commands/release-task.md` - slash-команды
- `docs/release-gates/` - утверждённые gate-отчёты + README.md (вердикты, handoff, exemption-список); живой пример: `docs/release-gates/2026-08-27-pmm-7-dry-run.md`

### Контракты

- Gate ID `RG-<YYYYMMDD>-<slug>`; файл отчёта `docs/release-gates/<YYYY-MM-DD>-<slug>.md`; дочерние задачи ссылаются на Gate ID.
- Вердикты: KEEP / REUSE / SHRINK / DEFER / DROP / BLOCKED. Handoff-status: READY_AUTO / NEEDS_APPROVAL / NEEDS_INPUT / BLOCKED.
- Строка `DISCOVERY_STATUS: ...` - в шапке `## Gate` и последней строкой отчёта, парсится Orca-координатором: READY_AUTO→READY; DROP/DEFER→NOT_NEEDED; NEEDS_APPROVAL/NEEDS_INPUT/BLOCKED→напрямую.
- Один gate на epic покрывает дочерние задачи, пока они не выходят за Scope lock.

### Подводные камни

- `.opencode/agents/briefmaker.md` - legacy, не вызывать и не изменять (решение Mike); в major/critical диспетчеризуется release-critic.
- release-critic read-only: edit/write запрещены permissions, bash только `git status|log|show|diff|branch --show-current|rev-parse`, секреты не читает.
- Языки: SKILL.md и команды - русские; шаблон отчёта и секция «Release Gate» в AGENTS.md - английские; `docs/release-gates/README.md` - русский.
- Gate не нужен (exemption): typo, форматирование, test-only, узкий bugfix без изменения поведения/контрактов/архитектуры/данных/зависимостей/security/scope.
- `docs/agent-system/DECISIONS.md`, `docs/adr/*`, утверждённые фазовые контракты M1 критик не DROP/DEFER молча - только NEEDS_APPROVAL с явной ссылкой.

### Проверка

- Frontmatter (4 файла): `python3 -c "import yaml;[yaml.safe_load(open(f).read().split('---')[1]) for f in ['.opencode/skills/release-cutter/SKILL.md','.opencode/agents/release-critic.md','.opencode/commands/release-gate.md','.opencode/commands/release-task.md']]"`
- Маркеры AGENTS.md (паттерн якорим к началу строки, иначе grep считает сам этот блок): `grep -c '^<!-- autopilot:start -->' AGENTS.md` → 1; `grep -c '^<!-- release-gate:start -->' AGENTS.md` → 1.
