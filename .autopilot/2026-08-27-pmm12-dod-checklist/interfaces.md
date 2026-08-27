# Interfaces — PMM-12 DoD-чеклист

Ярус T0: один контекст, волн нет. Границ между модулями нет — файл и его guards.

## Границы, решённые в спецификации

Единственный шов — `scripts/agent/verify` (structural layer): поведение проверяется его запуском (`bash scripts/agent/verify` → PASS, включая новый required-files пункт).

## Правила проекта (нельзя вывести из тикета)

- Стек: Node 22 (collector), Python только через `uv` 3.14; для этого прогона Python не нужен, Node не нужен — только bash-правка скрипта.
- Команда верификации перед коммитом: `make verify` (канонический, fail-closed). Быстрый subset: `scripts/agent/verify`.
- Коммиты: атомарные, conventional (`docs(pmm): ...`); `git add` поимённо — в дереве чужих несвязанных правок быть не должно (worktree чистый, но правило действует).
- Branch: `mihailzhamba-bot/pmm-12-dod-verify-commit-unreleased-sourceref-7` (уже checkout); PR → main; merge без force-push.
- Jira: проект PMM, cloud `zhamba.atlassian.net`; PMM-12, PMM-30, PMM-9, PMM-10 — комментарии; статус Done — только PMM-12, после merge.
- Нельзя трогать: `docs/governance/assumptions-register.md` и `risk-register.md` (только чтение как паттерн), sibling-worktrees, `services/collector/src/contracts/` (генерируется), чужие файлы.
- Доки governance — на русском, идентификаторы английские; агентские доки (`docs/agent-system/`, AGENTS.md, RULES.md) — английские правки.
- Не выдумывать факты в аудит-таблицах: каждый вердикт с доказательством (файл/PR/коммит), добытым из репо или Jira; нет данных → UNKNOWN, не догадка.
- Отсутствующая зависимость или недоступный факт → BLOCKED с причиной, не установка/выдумывание.
