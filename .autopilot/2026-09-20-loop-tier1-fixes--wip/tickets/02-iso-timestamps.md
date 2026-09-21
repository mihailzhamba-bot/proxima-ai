# T02 — R02: ISO таймстемпы loop-задач

**Требования:** R02 · **Зона:** services/webapp/src/lib/loop · **Волна:** 1 · **Status:** ready

## Что должно заработать

Карточка задачи на iPhone (JSC) показывает срок корректно: SQL отдаёт ISO 8601 через to_json, а не Postgres-текст с пробелом.

## Критерии приёмки

- [ ] taskSelect: to_json(t.due_at)#>>'{}', to_json(t.created_at)#>>'{}', to_json(e.created_at)#>>'{}'
- [ ] t.due_at::text в SQL не остаётся
- [ ] unit-тест на форму SQL; db-тест формата — CI
- [ ] typecheck/lint/test зелёные

## Прогон

- [x] реализовано
- [x] тест
- [x] ревью
