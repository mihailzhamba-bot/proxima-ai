# Манифест требований

Источник: `2026-08-27-brief.md` (задача PMM-20 + решения грилля 2026-08-27).
Строку из этого списка может снять **только пользователь**.

| ID | Из брифа (дословно/сжатие решения) | Статус | Основание | Где |
|----|---------------------|--------|-----------|-----|
| R01 | «baseline 7/14/28 с сезонностью дня недели» - мультипликативный индекс s_w; Expected(D,W) = MA(W) × s_w(D); триггер Expected(28) + корроборация 7/14; сигнал несёт все три дельты | in-ticket | — | T01 |
| R02 | «Декомпозиция отклонения: U×CVR×AOV, вклад каждого множителя» - Шепли, вклады суммируются в дельту ₽ точно | in-ticket | — | T01 |
| R03 | Метрика = заказы: U=openCard, CVR=orders/openCard, AOV=ordersSumRub/orders; выкупы контекстом в payload | in-ticket | — | T01 |
| R04 | «Порог: глобальный по умолчанию» - дефолт 20% против Expected(28) в конфиге + interface stub под Client Passport (safe default, PMM-21 rollback-режим) | in-ticket | — | T01 |
| R05 | «₽-фильтр значимости (сигналов ≤10/день на кабинет)» - revenue_delta_orders = Expected(D) − Actual(D), floor 3 000 ₽/день, топ-≤10 по убыванию | in-ticket | — | T01 |
| R06 | «дедуп между окнами baseline» - открытый сигнал блокирует новые до восстановления выше порога или cooldown 7 дней | in-ticket | — | T01 |
| R07 | «по SKU/кабинету» - SKU (nmID) + кабинет по зрелой панели (≥21/28), исключённые в payload (panel_size, excluded_count) | in-ticket | — | T01 |
| R08 | «исторически низкой активностью… сезонный коэффициент применён» + новые SKU: <21/28 дней → BLOCKED INSUFFICIENT_HISTORY, счётчик в observability, не молчаливый пропуск | in-ticket | — | T01 |
| R09 | Чистое ядро (ноль БД/сети) + отдельный loader (резолв DOWNLOADED task_id, реестр маппинга колонок, fail-closed на отсутствующую) | in-ticket | — | T02 |
| R10 | «день оценки D = вчера полный по Europe/Moscow», параметр для replay/backtest | in-ticket | — | T01 |
| R11 | «воспроизводимость сигнала по snapshot_id… результат идентичен» - snapshot_id = sha256 канонического JSON входного бандла, source_refs на task_id | in-ticket | — | T02 |
| R12 | DetectorResult типизирован 1:1 под минимальный набор PMM-29: scenario_code=SCN-001, snapshot_id, source_refs[], trust_marking=unreleased, ₽-дельта с method, + fingerprint=canonical_hash | in-ticket | — | T01 |
| R13 | Ядро в `services/control-plane/src/proxima_control_plane/detectors/scn001/` (Python 3.14, uv), деньги в Decimal | in-ticket | — | T01 |
| R14 | Тесты на явно помеченных инжектированных кейсах: FP-кейс выходных (нет сигнала), кейс падения (сигнал + вклады), детерминизм, дедуп, ₽-фильтр top-10 | in-ticket | — | T01 |
| R15 | «Детерминированный расчёт (LLM запрещён в числах)» | in-ticket | — | T01 |
| R16 | Read-only smoke против staging при поднятом туннеле: одна реальная строка payload, сверка реестра маппинга; туннель не поднят → UNKNOWN зафиксировать | in-ticket | — | T02 |
| R17 | Jira: PMM-20 → «В работе», комментарий с решениями грилля | in-spec | финальная фаза рана (оркестратор): не код, тасковый boundary не окупается — сознательное отступление от G3 | финал |
| R18 | Verify-гейт: `make verify` + чеклист PMM-12 (`docs/governance/dod-checklist.md`) + independent reviewer | in-ticket | — | T02 |
| R19i | Zero-guards: baseline=0, openCard=0 при orders>0, отрицательные значения - явные fail-closed кейсы, не crash/NaN | in-ticket | — | T01 |
| R20i | Всё помечено `unreleased` (DEC-006: staging-данные пилота вне release-контура) | in-ticket | — | T01 |

## Out of Scope (deferred, с основаниями)

| Что | Куда | Основание |
|---|---|---|
| Binding payload на `contracts/signal.schema.json` | PMM-29 (bot lane) → тонкий adapter | решение грилля 1: PMM-29 не стартуем (чужая линия) |
| Реальные per-client пороги | PMM-21 | решение грилля 1: stub + safe default |
| Перепривязка на импортный scenario engine | PA-41 W2 adaptation | решение грилля 8 |
| Реальный backtest на истории пилота | PMM-32 daily-цикл (накопление) | PMM-20 §12: «исторических данных пилота под backtest сейчас нет» |
| Диагноз причины, ₽-оценка (DEC-003), бенчмарки MPStats, SCN-002, категории | PMM-20 §6 Out of Scope | задача |
