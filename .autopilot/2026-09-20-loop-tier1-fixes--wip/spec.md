# Spec — LOOP tier1 fixes

Источник: brief (протокол комнаты) + manifest R01-R08. Целевое дерево: 8d23519 (HEAD ветки fix/loop-pilot-review-tier1), НЕ PR-состояние 1dfb971.

## R01 — /brief guard сессии

`brief/page.tsx:26`: чтение очереди без обработки QueueError. Спека: обернуть в try/catch по образцу `/inbox/page.tsx:14-19`: 401 → `redirect("/login")`; остальные QueueError → честная страница с сообщением (заголовок «Утренняя сводка», текст ошибки в role="alert"). getBrief/getSummary не трогаем.

## R02 — ISO таймстемпы

`service.ts` taskSelect: `t.due_at::text` и `t.created_at::text` → `to_json(...)#>>'{}'` (ISO 8601 с T и смещением, JSC-совместимо); также `e.created_at::text` в подзапросе completed_at. `b.brief_day::text` (дата без времени) не трогаем. queue.tsx:73 не меняется. `taskSelect` экспортируется для unit-теста формы SQL. db-тест формата — CI.

## R03 — 409 на отменённый сигнал

`service.ts` accept: existing-запрос добирает статус задачи (тот же COALESCE-подзапрос, что в taskSelect); статус `cancelled` → `QueueError(409, "Сигнал уже решён, отмена финальна.")`; иначе прежний replay. Текст ошибки уже доходит до UI через общий error-путь `useCommand` (queue.tsx:26-28) — queue.tsx не меняется.

## R04 — observe pinned к end

В calendar.ts добавить `moscowDayAt(time: Date)` (UTC+3-день момента); `service.ts` observe: `end = moscowDayAt(completed_at + horizon_days)`. Логика: `row.brief_day < end` → прежний unknown «ещё нет полного дня»; `row.brief_day > end` → unknown с честной причиной (сводка за пределами окна, замер не проводится); `== end` → существенный путь замера. Unit-тесты: граница moscowDayAt 21:00 UTC, арифметика end.

## R05 — стоп-клин (bridge.py, текущее дерево)

- `_cancel`: ранний возврат `{"status":"cancelled"}` при `op["state"] == "cancelled"` независимо от stop_confirmed (состояние cancelled ставится только подтверждённой отменой или reconcile'ом upstream-TERMINAL — регресс отменён).
- Paperclip-ветка: после успешного POST cancel — GET статуса и нормализация через PAPERCLIP_STATUS_MAP; `stop_ok = нормализованный статус in TERMINAL`. При BridgeError на POST — прежнее поведение (остаётся unconfirmed).

## R06 — 500 + traceback + логи

- handler `except Exception` → `traceback.print_exc()` + `send_json(500, {"error":"internal bridge error; state uncertain; reconcile","uncertain":True})`.
- silencer `log_message` удалить (R06 манифеста).
- runner.py serve-цикл: `traceback.print_exc()` в except-ветке.
- Клиент JsonHTTP не меняется: 5xx уже uncertain (bridge.py:87), trusted_bridge читает uncertain-флаг (bridge.py:81-83).

## R07 — единая статус-мэпа

Модульная константа `PAPERCLIP_STATUS_MAP = {"succeeded":"completed","scheduled_retry":"interrupted","timed_out":"failed"}`; используется в reconcile (~:309) и fence (~:580). PR-listing дедуп — nit, вне scope.

## R08 — bind по умолчанию

`bridge.config.example.json`: `"bind": "127.0.0.1"`. OPERATIONS.txt — существующий файл, добавить абзац про сетевой доступ моста: compose публикует 127.0.0.1:18770; не-loopback bind допустим только с TLS-фронтом; JsonHTTP разрешает http только loopback/control-именам. test_loop_config.py bind не ассертит (проверено) — тест не требуется.

## Тесты

- tools/tests/test_loop_bridge.py: R05 — childless paperclip stop подтверждается по upstream-TERMINAL, повторный stop идемпотентен без сетевых вызовов; R06 — не-BridgeError в handler'е даёт 500+uncertain.
- services/webapp/src/tests/loop.test.ts: R02 форма taskSelect; R04 moscowDayAt/арифметика end.
- loop.db.test.ts: R02/R03 в CI (pg-roundtrip SKIP локально).

## Верификация

pytest tools/tests (uv) → vitest/typecheck/lint webapp → make verify (ожидаемо ровно один SKIP: pg-roundtrip) → reviewer-субагент → push → PR.
