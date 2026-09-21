# T04 — R04: observe pinned к концу горизонта

**Требования:** R04 · **Зона:** services/webapp/src/lib/loop · **Волна:** 1 · **Status:** ready

## Что должно заработать

Вердикт наблюдения измеряется строго днём end (MSK, completed_at + horizon); поздняя сводка даёт честный unknown, а не «цель достигнута» по чужому дню.

## Критерии приёмки

- [ ] calendar.moscowDayAt добавлен; end считается через него
- [ ] brief_day < end → прежний unknown; > end → honest unknown; == end → замер
- [ ] unit-тесты: граница 21:00 UTC, арифметика end
- [ ] typecheck/lint/test зелёные

## Прогон

- [x] реализовано
- [x] тест
- [x] ревью
