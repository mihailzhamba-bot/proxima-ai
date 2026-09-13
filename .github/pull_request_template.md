<!-- Заголовок PR: conventional-префикс + ключ Jira, например `docs(analytics): PMM-58 data-quality report`. -->

## Что и зачем

<!-- 2-3 строки: что меняется и какую задачу закрывает. -->

Задача: <!-- PMM-NNN / PA-NNN --> · Контракт: <!-- `_bmad-output/planning-artifacts/epics.md#story-N-M` или раздел хартии -->

## Проверка

- `make verify`: <!-- зелёный / какие шаги дали SKIP (без PostgreSQL 16 - `pg-roundtrip: SKIP`) -->
- Цифры в документах помечены `unreleased`, реальные cabinet ID и SKU заменены суррогатами: <!-- да / n-a -->
- Чужие зоны не тронуты (`tools/verify_*.py`, `db/migrations/`, `contracts/`, `.github/`, замороженные зоны AGENTS.md): <!-- да -->

## DoD-аудит (`docs/governance/dod-checklist.md`)

| № | Пункт | Вердикт (pass / justified / n-a) | Доказательство (файл, PR, коммит) |
|---|---|---|---|
| 1 | `make verify` до коммита | | |
| 2 | `unreleased`-маркировка | | |
| 3 | SourceRef на факты LLM | | |
| 4 | contracts + codegen | | |
| 5 | документация обновлена | | |
| 6 | observability-метрика | | |
| 7 | Jira-зависимости актуализированы | | |

## Для аналитика

- Строка в журнал (`docs/state/SHADOW-RECONCILIATION.md` / `CABINET-RECONCILIATION.md`) добавлена в день прогона: <!-- да / n-a -->
- Расхождения выше допуска: <!-- нет / задача Jira с меткой блокера -->
