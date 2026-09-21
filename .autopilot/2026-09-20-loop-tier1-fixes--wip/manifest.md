# Манифест требований

Источник: `2026-09-20-brief.md` (протокол Code Review Crew). Строку из этого списка может снять только пользователь.

| ID | Из брифа (дословно/сжато по протоколу) | Статус | Основание | Где |
|----|----------------------------------------|--------|-----------|-----|
| R01 | «/brief не падает на истёкшей сессии: guard как в /inbox - 401 → redirect /login, иные QueueError → честная страница» | done | 443abd8 | T01 |
| R02 | «Таймстемпы задач в ISO (to_json вместо ::text), JSC-совместимо; заодно created_at» | done | 443abd8 | T02 |
| R03 | «Ре-подтверждение отменённого сигнала → 409 "отмена финальна" вместо ложного success; replay не-отменённой сохранён» | done | 443abd8 | T03 |
| R04 | «Вердикт наблюдения привязан к дню конца горизонта: < end не прошло, > end честный unknown, == end вердикт; reuse calendar.ts» | done | 443abd8 | T04 |
| R05 | «Стоп-клин: stop_ok достижим для childless paperclip (upstream TERMINAL), повторный /stop идемпотентен, регресс cancelled→cancelling невозможен» | done | 731a5ce | T05 |
| R06 | «(tier 1.5, тот же коммит с R05) Unexpected-ошибка → 500 + traceback + uncertain; диагностика bridge и serve-цикла runner'а не глушится» | done | 731a5ce | T05 |
| R07 | «(tier 1.5, тот же коммит с R05) Единая PAPERCLIP_STATUS_MAP для reconcile и fence» | done | 731a5ce | T05 |
| R08 | «bind 127.0.0.1 в bridge.config.example.json + абзац в OPERATIONS.txt: не-loopback bind требует TLS-фронт» | done | 92075bb | T06 |

Follow-ups (вне scope, строкой в HANDOFF): fail_job ownership, статический bearer /api/loop/context, HTTP-таймауты bridge, burn 429-ключа, adopt-no-op, write-only events, рукописные пулы, SSH-словари, контракт без потребителя.

| Dec | Что доказал билд | Когда |
|-----|-------------------|-------|
| D01 | Старое поведение «навсегда cancelling» было зашито в test_loop_native.py:385 как ожидаемое - тест переведён на новую семантику (фикстура отдаёт upstream-TERMINAL, стоп теперь подтверждается) | 2026-09-20 |
| D02 | Ранний возврат `cancelled` сужен условием «нет живых hermes-children/jobs» по warning ревьюера - reconcile-отменённый прогон с живыми детьми идёт полным путём зачистки | 2026-09-20 |
| D03 | Окружение: `make` и chrome-headless-shell пришлось доустановить (make через apt, браузер вручную из chrome-for-testing в ~/.cache/puppeteer); `CI=true` обязателен для render_architecture под root (--no-sandbox) | 2026-09-20 |
