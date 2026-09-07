# KNOWN_FAILURES — PROXIMA AI

| ID | Item | Reason | Owner | Task | Introduced | Expected resolution | Policy |
|---|---|---|---|---|---|---|---|
| KF-1 | ~~Pre-existing dirty tree (Makefile, tools/verify_runtime_boundary.py, .planning/STATE.md, untracked .mcp.json/opencode.json/.codex/)~~ RESOLVED 2026-08-17: those files are committed, `git status` reports a clean tree | other threads' work | Mike | closed by backlog audit 2026-08-17 | pre-2026-08-16 | done | CLOSED |
| KF-2 | ~~TASKS.md references HEAD 1a211c9 while repo HEAD moved past it~~ RESOLVED 2026-08-16 (task snapshot wording updated) | task snapshot drift | agent | fixed in remediation wave 2 | 2026-08-16 | done | CLOSED |
| KF-3 | ~~`mskDay: midnight boundary in both directions` (`services/collector/tests/wb-msk-day.test.ts`) падает примерно раз на три прогона `npm test`: ожидается `2026-08-30`, приходит `2026-08-29`. В изоляции файл проходит 10 из 10, на чистом `main` 104 из 104~~ RESOLVED 2026-09-07 (`fix/collector-kf3-msk-day`): подмена `'24' → '00'` в `moscowOffsetMinutes()` била по всем частям отформатированного `now`, а не только по часу - в минуту :24 смещение падало до 156 мин, 24-го числа уезжало на сутки и больше; теперь сворачивается только час, тест на границу полуночи идёт на фиксированных `now` | не ветка `hour === '24'`, а подмена без привязки к типу части: минута :24 и 24-е число месяца обнулялись | конвейер | закрыто в `fix/collector-kf3-msk-day`, 2026-09-07 | Story 1.4 (`services/collector/src/wb/msk-day.ts`) | done | CLOSED |

No test-level known failures: `make verify` must stay green; any red test = immediate register-or-fix.
