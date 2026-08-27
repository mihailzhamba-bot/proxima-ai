# Глоссарий и KPI-дерево M2

> Владелец всех метрик: Mike, Product Owner. Версия: 2026-08-27.
>
> Источники: [PRODUCT-VISION §3, §4 и §8](../../.planning/PRODUCT-VISION.md),
> [PMM-8](https://zhamba.atlassian.net/browse/PMM-8),
> [PMM backlog-run](../exec-plans/active/pm2-backlog-run.md). Числовые пороги
> не задаются этим документом: без названного ниже baseline они `UNKNOWN`.

## Граница

- Документ фиксирует определения M2, а не добавляет runtime-код, схемы или
  metric governance с версионированием.
- Метрики считает детерминированный код. LLM может объяснять их, но не
  вычислять. Каждый факт требует SourceRef.
- До M1 Data GO любой вывод M2 работает на staging-данных пилота и несёт
  маркировку `unreleased`.
- `revenue-based` ₽-оценка W1 не является `contribution` или profit.

## Глоссарий

| Термин | Каноническое определение | Граница или источник |
|---|---|---|
| Signal | Детерминированно найденное отклонение или риск с причиной, evidence и временем создания. | До 10 в день на кабинет; факт остаётся проверяемым через SourceRef. |
| Opportunity | Подтверждённый signal с описанной возможной пользой и рекомендуемым действием, ещё не решение AM. | Не подменяет факт или verified outcome. |
| Decision | Явное действие AM над рекомендацией: принять, отклонить или отложить с причиной. | Decision Inbox; read-only система сама действие не исполняет. |
| SourceRef | Семантический locator исходного факта в границах tenant/cabinet/snapshot. | Разрешается только через publication/release chain; разрыв цепочки блокирует чтение. |
| `unreleased` | Обязательная маркировка доверия M2-вывода до M1 Data GO. | DEC-006: staging-данные пилота, production release pointer не меняется. |
| GYR | Представление статуса signal в интерфейсе: green, yellow, red или neutral. | Не является R-level и не заменяет решение AM. |
| R-level | Порядковый risk level `R0`…`R3`, используемый quality/reviewer контуром. | Семантика и policy принадлежат действующему 07-quality contract; GYR не выводится из R-level автоматически. |
| Baseline 7/14/28 | Скользящее сравнение с окнами 7, 14 или 28 дней с учётом дня недели. | Окно и порог выбираются детектором/Client Passport только после baseline. |
| days-cover | Оценка дней покрытия: доступный остаток, делённый на детерминированную дневную скорость продаж. | Не считается при недостоверном остатке или скорости; порог per-client задаётся позднее. |
| `U × CVR × AOV` | Декомпозиция изменения продаж: трафик (`U`) × конверсия (`CVR`) × средний чек (`AOV`). | Методология SCN-001/002; компоненты не подменяют друг друга. |
| ДРР | Доля рекламных расходов: рекламные расходы / релевантная выручка за тот же период и срез. | W2, требует согласованных Advertising и Statistics данных. |
| contribution | Contribution after the agreed cost and tax treatment. | До решения [ADR-0001](../adr/0001-tax-regime-contribution.md) и закрытия его открытых вопросов значение `UNKNOWN`. |
| revenue-based ₽-оценка | Оценка «стоимости молчания» на выручке без заявления о прибыли или contribution. | W1 допускается отдельно; profit-based часть ждёт FIN-001/ADR. |

## KPI-дерево

| KPI | Формула и единица | Источник факта | Владелец | Порог и точка обновления |
|---|---|---|---|---|
| Time-to-detect отклонения | `signal_created_at - source_fact_available_at`, часы. | Timestamp доступности первичного WB-факта и timestamp создания signal. | Mike | Цель PV: дни → часы. Числовой порог `UNKNOWN` до baseline; не подменять временем запуска daily-цикла. |
| AM-время на мониторинг кабинета | Сумма завершённых записей AM time log на `cabinet-day`, минуты. | Структурированный замер PA-42. | Mike | Baseline и сравнение до/после задаёт PA-42. Ориентир PV: >60 мин/день и -50%+ к V2; runtime-порог `UNKNOWN`. |
| Signal recall / false positive | `recall = TP / (TP + FN)`; `FP share = FP / (TP + FP)`. | Вручную размеченный AM audit set кандидатов. | Mike | Без разметки обе величины `UNKNOWN`; critical errors всегда 0. Порог - после baseline. |
| Recommendation acceptance rate | `accepted / (accepted + rejected)`, %. | Решения Decision Inbox. Pending и deferred не входят в знаменатель. | Mike | Порог `UNKNOWN` до baseline. |
| Подтверждённые исходы | `closed signals with verified outcome / all closed signals`, %. | Decision Memory PMM-26: expected, actual и resolution. | Mike | Для принятого signal обязателен expected vs actual; для отклонённого - причина закрытия. Цель PV: 100% к концу M2. |
| Кабинеты на ежедневном мониторинге | Число уникальных кабинетов с 7 последовательными успешными scheduled daily-циклами. | Записи daily-цикла и Client Passport. | Mike | Учитываются только циклы в настроенные рабочие дни кабинета. Цель PV: 1 → 5; числовой operational threshold `UNKNOWN`. |
| Платящий клиент | Число уникальных внешних клиентов с подписанным договором на AI-аналитику. | Ручной договорной реестр Mike, без реквизитов в репозитории. | Mike | Цель PV: ≥1 к шести месяцам от зафиксированного старта M2. Пока дата старта не зафиксирована, дедлайн `UNKNOWN`. |

## Baseline и запреты на подмену данных

| Что остаётся `UNKNOWN` | Кто и чем закрывает |
|---|---|
| Числовые пороги time-to-detect, AM-времени, recall/FP и acceptance rate | Mike после PA-42 и размеченного AM audit set. |
| Пороги конкретного client/cabinet | Client Passport и соответствующий детектор после baseline 7/14/28. |
| Profit/contribution и налоговая ветка | FIN-001 и [ADR-0001](../adr/0001-tax-regime-contribution.md); до этого только revenue-based оценка. |
| Actual по действиям AM | PMM-26 Decision Memory; пропуск outcome для закрытого signal не допускается. |

## Связанные задачи

- PA-42 формирует baseline AM-времени и ручного time-to-detect.
- PMM-13 фиксирует baseline velocity команды, но не подменяет baseline KPI продукта.
- PMM-21 добавляет per-client пороги через Client Passport.
- PMM-26 хранит append-only цепочку decision → expected → actual → learning.
- PMM-28 обновляет фактический time-to-detect после первого сквозного signal.
