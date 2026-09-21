# Interfaces — LOOP tier1 fixes

## Границы, решённые в спецификации

- `services/webapp/src/lib/loop/service.ts`: сигнатуры list/accept/cancel/complete/observe не меняются; меняется поведение веток (R02 формат строк, R03 409, R04 честный unknown). `taskSelect` дополнительно экспортируется для теста.
- `tools/loop/bridge.py`: HTTP-эндпоинты не меняются; семантика ответов меняется только для unexpected-исключений (400 → 500 + uncertain) и подтверждения стопа (R05). JsonHTTP-клиент не меняется.
- `tools/loop/calendar.ts`: добавляется чистый хелпер `moscowDayAt`, существующий `lastFullMoscowDay` не меняется.
- Вне изменений: db/migrations/*, contracts/*.schema.json, codegen-выход, .github/, queue.tsx.

## Правила рана

- Команды: `PATH=$HOME/.local/bin:$PATH uv run --python 3.14 --project services/control-plane --extra test pytest tools/tests -q`; `npm --workspace @proxima/webapp run test|typecheck|lint`; `npm test`; `make verify` (PUPPETEER_SKIP_DOWNLOAD=1 TMPDIR=/tmp).
- Коммиты: английский conventional, атомарно по тикетам; ветка fix/loop-pilot-review-tier1; push + PR без merge.
- Не трогать: миграции, контракты/codegen, .github/workflows; секреты нигде не печатать.
- Недостающая зависимость → BLOCKED, не самовольная установка.

## Построено тикетками (заполняется по ходу)

- T01: brief/page.tsx — try/catch по образцу /inbox.
- T02: taskSelect to_json + экспорт константы.
- T03: accept — статус existing → 409 на cancelled.
- T04: calendar.moscowDayAt + observe-ветвление по end.
- T05: bridge — PAPERCLIP_STATUS_MAP, paperclip stop-подтверждение, idempotent-cancelled возврат, 500+traceback, снят silencer; runner traceback.
- T06: example bind 127.0.0.1 + OPERATIONS.txt.
