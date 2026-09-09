# API-FACTS: разведка WB API для PROXIMA AI

Сессия 1a, 30.08.2026, 05:59-06:11 UTC. Все вызовы с сервера `proxima` (`ssh -o BatchMode=yes`), токены из `/etc/proxima-ai/secrets/wb_*_token`, значения токенов не выводились и сервер не покидали. 18 вызовов, бюджет 35. Сессия 1b, 14:14 UTC: +2 вызова v3 `sales-funnel` по разрешению D16 (раздел «Воронка v3»), итого 20. Фикстуры: сервер `~/signal-inputs/fixtures/wb-api/`, копия в клоне `fixtures/wb-api/` (40 файлов, 436 МБ, untracked; `grep -rlE 'eyJ[A-Za-z0-9_-]{40,}' fixtures/` -> `clean` и на сервере, и на маке). Каждый факт ниже = вызов из лога в конце файла; чего не вызывал - помечено «не проверено».

## TL;DR

- **Ежедневный ряд продаж и заказов (Statistics API): 26 недель.** `sales` и `orders` с `dateFrom=2023-01-01&flag=0` отдают ряд с `2026-03-01` по сегодня (10 611 и 13 325 строк, потолок 80k не достигнут). `flag=1` по дню: `2026-02-28` отдаёт данные (77 продаж / 135 заказов), `2026-02-21` и `2026-02-15` - пустой массив. Окно скользящее, ~6 календарных месяцев назад; всё старше исчезает из API. Ряд непрерывный по месяцам (март-август по 1.7-2.6k строк/мес).
- **Воронка (просмотры, корзина): синхронно - только последние 7 дней.** v2 `POST /api/v2/nm-report/detail` и `/detail/history` -> `404 path not found` (путь снят, дедлайн миграции был 09.12.2025). Замена `POST /api/analytics/v3/sales-funnel/products/history` проверена 30.08 (D16): 200 за 24.08-30.08 с дневными записями (переходы, корзина, заказы, выкупы, конверсии - 11 полей; до 20 nmId за вызов, 3 вызова/мин), **400 `invalid start day: excess limit on days`** за 23.02-01.03. Спека: «максимум за последнюю неделю». Глубже недели - только async CSV `nm-report/downloads` (`DETAIL_HISTORY_REPORT`; по спеке до года и «только с подпиской Джем», глубина `startDate` не проверена).
- **Финотчёты (`reportDetailByPeriod`): 31 месяц, недельный разрез.** Первая страница (100 000 строк, 217 МБ) покрывает `2024-01-29..2025-10-18`, страница за 2026 (94 773 строки) - `2026-01-01..2026-08-23`, 34 недели. Последняя закрытая неделя `2026-08-17..2026-08-23` создана `2026-08-24`, лаг 1-8 дней.
- **`supplier/stocks` и `supplier/incomes` мертвы** (404 «This method is deprecated», «path not found»). Остатки - только через Analytics `stocks-report/wb-warehouses` (уже в коллекторе, не проверено).
- **Лимиты из заголовков:** `sales` 1/мин (429 после 32 с, `X-Ratelimit-Retry: 29`), `reportDetailByPeriod` 1/мин, `orders` 10, `seller-info` 10, `nm-report/downloads` 3. `X-Ratelimit-Reset` приходит только с 429.
- **Вердикт «>= 8 недель ежедневного ряда»: ДА** для продаж и заказов (26 недель). **НЕТ** для воронки: v3 отдаёт ровно последние 7 дней (проверено 30.08, D16), дневную историю глубже можно получить только через async CSV (`downloads`, квота 20 отчётов/день по коду репо).
- **Главный риск:** базы нормы по воронке к 30.09 не будет ни из одного источника: v3 не бэкфиллит (окно 7 дней), async CSV на глубину 6-12 мес не проверен. M-03 держится на заказах/продажах (D13), воронка - октябрь, и только если ежедневный сбор v3 или CSV стартует в первую неделю сентября: день, не снятый за 7 дней, из v3 пропадает. Второй риск: окно 6 мес означает, что история не копится сама - сбор надо запустить в сентябре, иначе к марту 2027 базы YoY не будет.

## A. Кабинет

`GET https://common-api.wildberries.ru/api/v1/seller-info`, statistics-токен, 05:59:04 UTC, 200, 139 B: `name` = «ИП Амирова О. Ф.», `tradeMark` = «ИП Амирова», `sid` = `a6836b3b-2db4-5dfb-b5d2-3987c12b8de9`. Подтверждено: все три токена того же кабинета (тенант `amirova-test`); аналитический и финансовый на другие хосты не проверялись отдельно, но `reportDetailByPeriod` прошёл на statistics-токене без 401, finance-токен не понадобился. В данных бренды `Meizel`, `Fanzo`, `Funny Elf`, первая `order_dt` в финотчётах `2023-12-03`.

## B/C. Таблица эндпоинтов

| Метод + путь | Токен | Ключевые поля | Проверенная глубина назад | Лимит (заголовки) | Ответ | Фикстура (`fixtures/wb-api/`) |
|---|---|---|---|---|---|---|
| GET common-api `/api/v1/seller-info` | statistics | name, tradeMark, sid, tin | n/a | limit 10, remaining 9 | 139 B, 0.08 s | `common/seller-info/20260830T055904Z__statistics-token.json` |
| GET statistics `/api/v1/supplier/sales` | statistics | date, lastChangeDate, nmId, supplierArticle, barcode, brand, subject, warehouseName, totalPrice, discountPercent, spp, priceWithDisc, finishedPrice, forPay, paymentSaleAmount, saleID (S/R), srid, isRealization (28 полей) | flag=0: `2026-03-01T05:51:52` .. `2026-08-30T07:01:10`, 10 611 строк; flag=1: 02-28 = 77, 02-21 = 0, 02-15 = 0 | limit 1, remaining 0; 429: reset 29, retry 29 | 8.77 МБ, 0.84 s | `statistics/supplier-sales/20260830T055939Z__dateFrom-2023-01-01_flag-0.json` (+4 flag=1) |
| GET statistics `/api/v1/supplier/orders` | statistics | как sales минус forPay/paymentSaleAmount/saleID, плюс isCancel, cancelDate (27 полей) | flag=0: `2026-03-01T00:51:40` .. `2026-08-30T06:39:33`, 13 325 строк; flag=1 02-28 = 135 | limit 10, remaining 9 | 10.85 МБ, 18.65 s | `statistics/supplier-orders/20260830T060041Z__dateFrom-2023-01-01_flag-0.json` |
| GET statistics `/api/v1/supplier/stocks` | statistics | - | **404 deprecated** | нет заголовков лимита | 258 B | `statistics/supplier-stocks/20260830T060148Z__dateFrom-2023-01-01.json` |
| GET statistics `/api/v1/supplier/incomes` | statistics | - | **404 path not found** | нет | 170 B | `statistics/supplier-incomes/20260830T060153Z__dateFrom-2023-01-01.json` |
| GET statistics `/api/v5/supplier/reportDetailByPeriod` | statistics (finance не понадобился) | 96 полей: realizationreport_id, date_from/date_to/create_dt, rr_dt, rrd_id, nm_id, doc_type_name (Продажа/Возврат/''), supplier_oper_name, quantity, retail_price, retail_amount, retail_price_withdisc_rub, ppvz_for_pay, ppvz_sales_commission, delivery_rub, storage_fee, penalty, deduction, acceptance, order_dt, sale_dt, srid | стр.1 (rrdid=0, limit 100000): rr_dt `2024-01-29..2025-10-18`, ровно 100 000 строк = потолок, 32 526 строк «Продажа»; 2026: rr_dt `2026-01-01..2026-08-23`, 94 773 строки, 34 недели, 15 774 «Продажа», retail_amount 13.72 M₽. Хвост `2025-10-19..2025-12-31` не вытянут (нужна пагинация rrdid) | limit 1, remaining 0 | 217.5 МБ 24.4 s; 211.3 МБ 25.8 s | `statistics/reportDetailByPeriod/20260830T060158Z__dateFrom-2023-01-01_...json`, `...20260830T060458Z__dateFrom-2026-01-01_...json` |
| POST analytics `/api/v2/nm-report/detail` | analytics (RW, только чтение) | - | **404 path not found**, 4 периода (20 мес, 6 мес, 3 мес, 1 мес) | нет | 176 B | `analytics/nm-report-detail/*.json` |
| POST analytics `/api/v2/nm-report/detail/history` | analytics | - | **404 path not found** (nmIDs 168118957, 686893199, 230474773 - топ-3 по priceWithDisc из фикстуры sales) | нет | 176 B | `analytics/nm-report-detail-history/20260830T060835Z__nmIDs-3_period-2026-08-24_2026-08-30_day.json` |
| GET analytics `/api/v2/nm-report/downloads` | analytics | data[]: id, status, name, size, startDate, endDate, createdAt | список: 2 отчёта `detail_history_report`, SUCCESS, окна `08-25..08-30` (создан `2026-08-30 00:51:06`) и `08-24..08-29` (`2026-08-29 00:53:37`), 8.3-8.5 КБ | limit 3, remaining 2 | 391 B, 0.12 s | `analytics/nm-report-downloads/20260830T060719Z__list.json` |
| POST analytics `/api/analytics/v3/sales-funnel/products/history` | analytics | product{nmId, title, vendorCode, brandName, subjectId, subjectName}, history[]{date, openCount, cartCount, orderCount, orderSum, buyoutCount, buyoutSum, buyoutPercent, addToCartConversion, cartToOrderConversion, addToWishlistCount}, currency | `2026-08-24..2026-08-30` = 7 дневных записей на каждый из 3 nmId; `2026-02-23..2026-03-01` = **400 `invalid start day: excess limit on days`** (спека: «максимум за последнюю неделю») | limit 3, remaining 2 (спека: 3/мин, интервал 20 с, всплеск 3) | 5 188 B, 0.88 s; 332 B, 0.08 s | `analytics/sales-funnel-v3-history/*.json` |

Не проверено (вне allowlist сессии): `POST /api/analytics/v3/sales-funnel/products` (агрегат за период до 365 дней с `pastPeriod`, без дневного разреза) и `/grouped/history`; `POST /api/analytics/v1/stocks-report/wb-warehouses`; `POST finance-api /api/finance/v1/sales-reports/detailed`; создание отчётов `POST nm-report/downloads`; скачивание `GET nm-report/downloads/file/{id}`; глубина `startDate` для async-отчёта.

## Ошибки и ограничения дословно

- `supplier/stocks`, 404, `application/problem+json`: `{"status":404,"statusText":"Not Found","title":"Not Found","detail":"This method is deprecated. Link: https://dev.wildberries.ru/release-notes?id=494","requestId":"bd8e4660c9f09fb7f54c19827f6d819b","origin":"ag-statistics"}`.
- `supplier/incomes`, 404: `{"detail":"Please consult the https://dev.wildberries.ru/openapi/api-information","origin":"ag-statistics","status":404,"statusText":"Not Found","title":"path not found"}`.
- `nm-report/detail` и `nm-report/detail/history`, 404, все 5 вызовов одинаково: `{"detail":"Please consult the https://dev.wildberries.ru/openapi/api-information","origin":"ag-contentanalytics","status":404,"statusText":"Not Found","title":"path not found"}`. Ошибки про длину периода получить не удалось - путь отсутствует целиком.
- `supplier/sales`, 429 (второй вызов через 32 с после предыдущего): `{"status":429,"statusText":"Too Many Requests","title":"Too Many Requests","detail":"rate limit exceeded, retry after the period specified in the X-RateLimit-Retry header","requestId":"1d80f4f389f047c0bdb00abc603fee02","origin":"ag-statistics"}`; заголовки `x-ratelimit-limit: 1`, `x-ratelimit-remaining: 0`, `x-ratelimit-reset: 29`, `x-ratelimit-retry: 29`. Это моя ошибка в темпе, не поведение API; после 429 эндпоинт больше не вызывался, бисекция границы окна на `2026-02-27` не сделана.
- Окно Statistics: `flag=0` фильтрует по дате продажи/заказа, не только по `lastChangeDate` - продажи 28.02 с `lastChangeDate` до `2026-03-14` в выборке `flag=0` отсутствуют. Граница между `02-21` (пусто) и `02-28` (данные есть); «сегодня минус 6 календарных месяцев» = `02-28` сходится, но точный алгоритм WB не подтверждён.
- `reportDetailByPeriod`: `limit=100000` - реальный потолок страницы (страница 1 вернула ровно 100 000), дальше только `rrdid` = последний `rrd_id` страницы (`3046950521984`); одна страница = 210-220 МБ и 25 с, полный бэкфилл 31 мес = 3-4 страницы при 1 вызове/мин.
- Заголовок `x-ratelimit-reset` на 200-ответах не приходит; `Retry-After` не встречался ни разу.
- Analytics-токен на сервере read-write; кто-то создаёт `detail_history_report` ежедневно около 00:51 МСК (окна по 6 дней) - на сервере нет ни таймера, ни cron, ни процесса под это (`systemctl list-timers`, `crontab -l`, `ps` 30.08). Потребитель токена вне сервера - вопрос в INVENTORY/бэклог PA-13 (ротация на read-only).

## D. Что уже написано в репо

| Эндпоинт | Код | Хранение |
|---|---|---|
| common `ping`, `seller-info`; `ping` statistics/analytics/finance/prices/promotion | `tools/wb_api_probe.py:72-82` (`ENDPOINTS`, `CATEGORY_PINGS`), `run_probe` `:292-394`, проверка JWT-скоупов `decode_token_claims` `:135-166` | content-addressed JSON в `/srv/proxima-ai/data/day1-wb-api/sha256/`, без БД |
| statistics `supplier/sales` (`flag=0`, 7 дней по lastChangeDate) | `tools/wb_api_probe.py:374-393`; `services/collector/src/business-signal/wb-client.ts:113-155` `WbSignalClient.sales` (курсор по lastChangeDate, страница 80 000, пауза 60 с, окно МСК `date-window.ts`) | `business_signal_raw_artifacts`, `business_signal_runs` (`db/migrations/004`), `fact_order_counts` nm_id x calendar_day (`007`) |
| analytics `POST /api/analytics/v1/stocks-report/wb-warehouses` | `wb-client.ts:157-190` `stocks` (offset-пагинация 250 000, пауза 20 с) | `business_signal_runs.stock_quantity/stock_as_of` |
| finance `POST /api/finance/v1/sales-reports/detailed` | `wb-client.ts:192-243` `finance` (rrdId-пагинация 100 000, пауза 60 с, терминатор 204); маржа в `calculate.ts:18` `calculateMargins` | `business_signal_raw_artifacts` |
| analytics `nm-report/downloads` create/status/file/retry (DETAIL_HISTORY_REPORT, day, последняя закрытая неделя) | `tools/wb_async_report.py` (`API_ROOT :32`, квота 20/день `:35`, poll 21 с `:34`, `AsyncReportCollector :652`) | `wb_analytics_report_tasks`, `wb_analytics_quota_events`, `raw_wb_analytics_responses` (`003`), `stg_wb_nm_report_rows` nm_id x row_date (`005`) |
| statistics `supplier/stocks`, `v5/reportDetailByPeriod` | запрещены гейтом `tools/verify_business_signal.py:27-29` («deprecated endpoint entered signal runtime») | - |
| statistics `supplier/orders`, v3 `sales-funnel/*` | нигде не используются | - |
| ручной XLSX-интейк WB | `services/collector/src/intake/manual-wb-xlsx.ts`, CLI `cli/manual-wb-xlsx-intake.ts` | `source_artifacts`, `artifact_manifests`, `intake_attempts` (`002`) |
| контракты | `contracts/source-artifact.schema.json` enum `source`: `official_wb_manual/statistics/analytics/finance`, `torgstat_supporting` | TS-типы `services/collector/src/contracts/` (codegen) |

Итого: продажи и финотчёт собираются, но в окне 7 дней под один сигнал (stockout); ни бэкфилла на 6 месяцев, ни ежедневного инкремента, ни таблицы дневного ряда продаж/заказов в миграциях нет. `wb_api_probe.py` и `wb_async_report.py` рабочие, обвязка (`prepare-day1-runtime.sh`, venv на сервере) есть по README.

## E. План Б по глубине

Условие D6 (>= 8 недель ежедневного ряда) для продаж/заказов выполнено: 26 недель. План Б нужен только для воронки (просмотры, корзина, конверсии), где синхронного метода нет и глубина не подтверждена. Варианты для заказчика, не решение:

1. **Копить N недель через async CSV (`nm-report/downloads`, уже написано в `wb_async_report.py`).** Старт 01.09: 4 недели к 29.09, 8 недель к 27.10. К 30.09 база нормы по воронке не успевает; отклонения по воронке уезжают в октябрь (M-04). Затраты: включить ежедневный запуск, квота 20 отчётов/день хватает на 1 кабинет с запасом. Неизвестно, как далеко назад принимает `startDate` (не проверено - возможно, один отчёт за 6 мес закроет бэкфилл сразу).
2. **Норма на финотчётах `reportDetailByPeriod`.** 31 месяц, есть YoY и сезонность, но разрез недельный и лаг 1-8 дней: «минус 23% против обычного вторника» на них не построить, только «неделя против типичной недели» и деньги (forPay, комиссия, логистика, хранение). Готово к использованию сразу, бэкфилл 3-4 страницы по 200+ МБ, 5 минут.
3. **Переопределить норму под доступную глубину: продажи и заказы из Statistics.** «Обычный вторник» = медиана того же дня недели за последние 8-12 недель по `orders`/`sales` (шт., приценка `priceWithDisc`, `forPay`). Данные есть уже сегодня, 30.09 реалистичен; воронка добавляется позже как второй слой. Обязательное условие: запустить ежедневный сбор в первую неделю сентября, потому что окно API скользящее и март 2026 выпадет из API в начале сентября.

Рекомендация к Воротам 1: вариант 3 как основа M-02/M-03 + вариант 1 в фоне с первого дня + отдельное разрешение на одну проверку `v3/sales-funnel/products/history` (2 вызова: неделя назад и 12 месяцев назад) - это снимает главный риск. Проверка выполнена 30.08 (D16), результат в разделе «Воронка v3»: истории нет, вариант 1 остаётся единственным путём к глубине.

## Воронка v3 (30.08.2026, D16)

Сессия 1b, 14:14 UTC, 2 вызова по разрешению Mike (D16), оба с сервера `proxima`, analytics-токен `/etc/proxima-ai/secrets/wb_analytics_token`. Фикстуры: сервер `~/signal-inputs/fixtures/wb-api/analytics/sales-funnel-v3-history/`, копия в клоне (4 файла, `grep -rlE 'eyJ[A-Za-z0-9_-]{40,}'` -> `clean` на сервере и на маке).

**Спека.** `dev.wildberries.ru/openapi/analytics` (раздел «Воронка продаж») на fetch отдаёт 498; контракт взят из зеркала OpenAPI-спеки WB `github.com/eslazarev/wildberries-sdk`, файл `specs/11-analytics.yaml` (`info.title` «Аналитика и данные»), коммит `75743e63` от 25.08.2026. Описание метода дословно совпадает с поисковой выдачей по `dev.wildberries.ru/en/docs/openapi/analytics`.

- `POST https://seller-analytics-api.wildberries.ru/api/analytics/v3/sales-funnel/products/history`, тело `ItemHistoryRequest`: `selectedPeriod{start, end}` (даты `YYYY-MM-DD`, обязательно), `nmIds` (uint64[], 1..20, обязательно), `aggregationLevel` (`day` | `week`, по умолчанию `day`), `skipDeletedNm` (bool).
- Ограничения по спеке: «можно получить данные максимум за последнюю неделю»; обновление 1 раз в час; большая часть заказов/переходов/корзин появляется в течение часа, «малая часть - в течение нескольких дней»; выкупы, отмены и возвраты пишутся в день заказа. Лимит на аккаунт: 3 запроса/мин, интервал 20 с, всплеск 3 (персональный, сервисный, базовый с секретом); базовый токен - 2 запроса/ч. Коды ответов: 200, 400, 401, 402 (только для решений из каталога WB), 403, 429.
- Соседи: `POST …/v3/sales-funnel/products` - агрегат за период с сравнением `pastPeriod`, до 365 дней назад, пагинация, но без разреза по дням; `POST …/v3/sales-funnel/grouped/history` - дневной разрез по группам карточек. Для «периода до года» спека отправляет в CSV-отчёты `DETAIL_HISTORY_REPORT` (`nm-report/downloads`) с пометкой «доступны только с подпиской Джем».

**Вызовы (UTC).**

| Время | Период, параметры | Код | Время | Байт | Заголовки лимита | Файл (`fixtures/wb-api/analytics/sales-funnel-v3-history/`) |
|---|---|---|---|---|---|---|
| 14:14:24 | `2026-08-24..2026-08-30`, nmIDs [686893199, 168118957, 230474773], day | 200 | 0.88 s | 5 188 | `x-ratelimit-limit: 3`, `x-ratelimit-remaining: 2` | `20260830T141424Z__nmIDs-3_period-2026-08-24_2026-08-30_day.json` |
| 14:14:57 | `2026-02-23..2026-03-01`, те же nmIDs, day | 400 | 0.08 s | 332 | `limit: 3`, `remaining: 2` | `20260830T141457Z__nmIDs-3_period-2026-02-23_2026-03-01_day.json` |

nmIDs - топ-3 по числу строк в фикстуре `supplier-sales` (745 / 568 / 433 строк), тот же набор, что в v2-вызове 06:08. Ошибка 400 дословно: `{"title":"Invalid request body","detail":"code=400, message={Invalid request body validate: invalid start day: excess limit on days d1b265d8-6b48-4a3e-804a-86a1cdbdaede analytics-open-api}, internal=validate: invalid start day: excess limit on days","requestId":"d1b265d8-6b48-4a3e-804a-86a1cdbdaede","origin":"analytics-open-api"}`. `x-ratelimit-reset` / `retry` не приходили; `remaining` через 33 с снова 2 - слот вернулся по интервалу 20 с либо 400 не списывается, без третьего вызова не различить.

**Глубина назад: 7 дней, февраль-март недоступен.** `start = сегодня - 6` (24.08) прошёл и вернул по 7 дневных записей на nmId, включая текущий неполный день 30.08 (14:14 UTC: 152 перехода у 686893199 против 214-271 в полные дни); `start = 23.02` отклонён валидатором до обращения к данным. Точная граница (`start = сегодня - 7`, 8 дней) не бисектирована - бюджет 2 вызова.

**Структура ответа** (`ItemHistoryResponse`): массив по nmId; элемент = `product{nmId, title, vendorCode, brandName, subjectId, subjectName}` + `history[]` + `currency` (`RUB`). Дневная запись `history[]` - 11 полей, все целые: `date`, `openCount` (переходы в карточку), `cartCount`, `orderCount`, `orderSum`, `buyoutCount`, `buyoutSum`, `buyoutPercent`, `addToCartConversion` (%, целое), `cartToOrderConversion` (%, целое), `addToWishlistCount`. Показов (impressions) в v3 нет. Сумма за 24-30.08 по 686893199: 1 616 переходов, 141 корзина, 12 заказов на 17 303 ₽, 4 выкупа (выкупы неполные - считаются по дню заказа); по 168118957: 166 переходов, 1 корзина, 0 заказов.

**Вывод для плана Б (D13).** v3 - не история, а скользящее окно 7 дней: ежедневный инкремент, бэкфилла не даёт. Базу нормы по воронке (8 недель) он не построит ни к 30.09, ни к 27.10 без ежедневного сбора - день, не снятый за неделю, из API пропадает. Что это меняет в D13:

1. Бэкфилл глубже недели - по-прежнему только async CSV `DETAIL_HISTORY_REPORT` (вариант 1, без изменений). По спеке он и предназначен для «периода до года», но с оговоркой про подписку Джем; на кабинете ежедневные `detail_history_report` с окнами 6 дней создаются и получают SUCCESS - либо Джем есть, либо короткие окна проходят без него. `startDate` на 6-12 мес назад не проверен: отдельное разрешение, 3 вызова (create + status + file).
2. Ежедневный сбор v3 стоит запустить с первой недели сентября параллельно CSV как дневной источник воронки без парсинга CSV: 201 nmId в кабинете (уникальные `nmId` в `orders` flag=0) = 11 вызовов по 20 nmId, при 3/мин - 4 минуты в день; каждый день перекрывается 7 раз, что ловит «малую часть данных, которая появляется в течение нескольких дней».
3. Для M-03 (30.09) ничего не меняется: норма по заказам/продажам из Statistics; по воронке уже с 01.09 доступно только «вчера против последних 6 дней», полноценная норма - конец октября при сборе без пропусков.

## Лог вызовов (UTC 30.08.2026)

| Время | Эндпоинт | Параметры | Код | Время | Байт | Файл (`fixtures/wb-api/`) |
|---|---|---|---|---|---|---|
| 05:59:04 | GET common `seller-info` | statistics-токен | 200 | 0.08 s | 139 | `common/seller-info/20260830T055904Z__statistics-token.json` |
| 05:59:39 | GET statistics `supplier/sales` | dateFrom=2023-01-01T00:00:00&flag=0 | 200 | 0.84 s | 8 766 279 | `statistics/supplier-sales/20260830T055939Z__dateFrom-2023-01-01_flag-0.json` |
| 06:00:41 | GET statistics `supplier/orders` | dateFrom=2023-01-01T00:00:00&flag=0 | 200 | 18.65 s | 10 854 000 | `statistics/supplier-orders/20260830T060041Z__dateFrom-2023-01-01_flag-0.json` |
| 06:01:48 | GET statistics `supplier/stocks` | dateFrom=2023-01-01T00:00:00 | 404 | 0.06 s | 258 | `statistics/supplier-stocks/20260830T060148Z__dateFrom-2023-01-01.json` |
| 06:01:53 | GET statistics `supplier/incomes` | dateFrom=2023-01-01T00:00:00 | 404 | 0.04 s | 170 | `statistics/supplier-incomes/20260830T060153Z__dateFrom-2023-01-01.json` |
| 06:01:58 | GET statistics `v5/reportDetailByPeriod` | dateFrom=2023-01-01&dateTo=2026-08-30&limit=100000&rrdid=0 | 200 | 24.40 s | 217 458 289 | `statistics/reportDetailByPeriod/20260830T060158Z__dateFrom-2023-01-01_dateTo-2026-08-30_limit-100000_rrdid-0_statistics-token.json` |
| 06:02:34 | GET statistics `supplier/sales` | dateFrom=2026-02-15&flag=1 | 200 | 0.08 s | 2 | `statistics/supplier-sales/20260830T060234Z__dateFrom-2026-02-15_flag-1.json` |
| 06:04:58 | GET statistics `v5/reportDetailByPeriod` | dateFrom=2026-01-01&dateTo=2026-08-30&limit=100000&rrdid=0 | 200 | 25.79 s | 211 293 715 | `statistics/reportDetailByPeriod/20260830T060458Z__dateFrom-2026-01-01_dateTo-2026-08-30_limit-100000_rrdid-0_statistics-token.json` |
| 06:05:32 | GET statistics `supplier/sales` | dateFrom=2026-02-28&flag=1 | 200 | 0.54 s | 62 967 | `statistics/supplier-sales/20260830T060532Z__dateFrom-2026-02-28_flag-1.json` |
| 06:05:33 | POST analytics `nm-report/detail` | period 2025-01-01..2026-08-30, page 1 | 404 | 0.04 s | 176 | `analytics/nm-report-detail/20260830T060533Z__period-2025-01-01_2026-08-30_page-1.json` |
| 06:05:54 | POST analytics `nm-report/detail` | period 2026-03-01..2026-08-30 | 404 | 0.05 s | 176 | `analytics/nm-report-detail/20260830T060554Z__period-2026-03-01_2026-08-30_page-1.json` |
| 06:06:16 | POST analytics `nm-report/detail` | period 2026-06-01..2026-08-30 | 404 | 0.04 s | 176 | `analytics/nm-report-detail/20260830T060616Z__period-2026-06-01_2026-08-30_page-1.json` |
| 06:06:37 | POST analytics `nm-report/detail` | period 2026-08-01..2026-08-30 | 404 | 0.05 s | 176 | `analytics/nm-report-detail/20260830T060637Z__period-2026-08-01_2026-08-30_page-1.json` |
| 06:07:19 | GET analytics `nm-report/downloads` | без параметров | 200 | 0.12 s | 391 | `analytics/nm-report-downloads/20260830T060719Z__list.json` |
| 06:08:35 | POST analytics `nm-report/detail/history` | nmIDs [168118957, 686893199, 230474773], 2026-08-24..2026-08-30, day | 404 | 0.05 s | 176 | `analytics/nm-report-detail-history/20260830T060835Z__nmIDs-3_period-2026-08-24_2026-08-30_day.json` |
| 06:08:35 | GET statistics `supplier/sales` | dateFrom=2026-02-21&flag=1 | 200 | 0.09 s | 2 | `statistics/supplier-sales/20260830T060835Z__dateFrom-2026-02-21_flag-1.json` |
| 06:08:38 | GET statistics `supplier/orders` | dateFrom=2026-02-28&flag=1 | 200 | 0.19 s | 108 338 | `statistics/supplier-orders/20260830T060838Z__dateFrom-2026-02-28_flag-1.json` |
| 06:09:07 | GET statistics `supplier/sales` | dateFrom=2026-02-27&flag=1 | 429 | 0.55 s | 279 | `statistics/supplier-sales/20260830T060907Z__dateFrom-2026-02-27_flag-1.json` |
| 14:14:24 | POST analytics `v3/sales-funnel/products/history` | nmIds [686893199, 168118957, 230474773], selectedPeriod 2026-08-24..2026-08-30, day (D16) | 200 | 0.88 s | 5 188 | `analytics/sales-funnel-v3-history/20260830T141424Z__nmIDs-3_period-2026-08-24_2026-08-30_day.json` |
| 14:14:57 | POST analytics `v3/sales-funnel/products/history` | те же nmIds, selectedPeriod 2026-02-23..2026-03-01, day (D16) | 400 | 0.08 s | 332 | `analytics/sales-funnel-v3-history/20260830T141457Z__nmIDs-3_period-2026-02-23_2026-03-01_day.json` |

Пропущенные по плану вызовы: 3 глубинных `detail/history` (3/6/12 мес) - не выполнялись, потому что базовый вызов вернул 404; finance-токен для `reportDetailByPeriod` - не понадобился (statistics-токен прошёл).

## flag=0 семантика (31.08.2026, Story 1.0)

Два read-вызова с сервера (`dateFrom=2026-08-28T00:00:00&flag=0`, D22): `orders` - 172 строки, `date` от 06.08 до 31.08, все `lastChangeDate` ≥ 28.08, **69 строк с `date < dateFrom`** → фильтр по `lastChangeDate`, допущение AD-4 подтверждено, `dateFrom = run_day-3` остаётся. `sales` - 108 строк, `date` 28-31.08, 0 строк раньше окна (обновления продаж реже). Уникальность ключей: `srid` 172/172, `saleID` 108/108 (и 13 325/13 325, 10 611 - на полных фикстурах 30.08 с учётом пар продажа+возврат по разным `saleID`). Фикстуры: `~/signal-inputs/fixtures/wb-api/statistics/supplier-{orders,sales}/*step0.json`.

## Артефакты для бэкфилла (Story 1.5 / 1.14)

| Файл (VPS `~/signal-inputs/fixtures/wb-api/statistics/`) | sha256 | retrieved_at |
|---|---|---|
| `supplier-sales/20260830T055939Z__dateFrom-2023-01-01_flag-0.json` | `77c99ddac2bbcf3fcedcecc0a386a5abb5727c2f213d38950b89a6916e13fc29` | 2026-08-30T05:59:39Z |
| `supplier-orders/20260830T060041Z__dateFrom-2023-01-01_flag-0.json` | `d2d0ecfed34b67dd0e4b4dc34228fa434d102b190ce18f8f27686987e76aa03e` | 2026-08-30T06:00:41Z |
| `supplier-sales/20260831T155341Z__dateFrom-2023-01-01_flag-0.json` | `d2f1dc9581ad1f1ab67d1f7ac874b1fa93109915a06d3b09505d960e0b65ec96` | 2026-08-31T15:53:41Z |
| `supplier-orders/20260831T155341Z__dateFrom-2023-01-01_flag-0.json` | `0c0318ff835d59e263a32cd1f565d8f899e28173e4eacc942c414756214daa40` | 2026-08-31T15:53:41Z |

Импорт в CAS - `tools/cas_import.ts` в Story 1.14 (runbook). `run_day` = дата `retrieved_at` артефакта; бэкфилл берёт самую свежую пару (31.08: sales 8.8 МБ, orders 10.9 МБ, оба ряда по-прежнему с 2026-03-01). Снапшот 31.08 снят как страховка непрерывности ряда до запуска ежедневного сбора.

## Эталоны недельных сумм W10/W35 (CAP-2, Story 1.14 §4 runbook)

Записано 08.09.2026 (runbook drift, `docs/state/RELEASE-READINESS-1.14.md` T5): AC Story 1.14 сверяет «W10 и W35 с API-FACTS», а в этом файле чисел до сих пор не было - они жили в `_bmad-output/specs/spec-wb-morning-brief/SPEC.md:33` (CAP-2 success) и `_bmad-output/planning-artifacts/epics.md:29` (FR3), оба от 30.08.2026 (коммит `d6a558a`), с формулировкой «недельные суммы совпадают с фикстурами 30.08». Здесь - те же числа с источником; до 08.09 в этом файле они не пересчитывались (пересчёт по формулам глоссария - раздел «Репетиция цепочки 1.14 на VPS» ниже).

| Неделя (ISO, Story 6.1 Given: «нумерация недель ISO для W10/W35») | Дни (`calendar_day`) | Заказы | Выручка, ₽ | Источник, дата |
|---|---|---|---|---|
| W10 | 2026-03-02 … 2026-03-08 | 649 | 700 860.50 | `SPEC.md:33`, `epics.md:29` - 30.08.2026 (там «700 860», округлено до рубля); копейки - пересчёт 08.09 по фикстуре 30.08, раздел «Репетиция…» ниже |
| W35 | 2026-08-24 … 2026-08-30 | 225 | 263 089 | те же; с 08.09 (~13:40 UTC, решение Mike) гейт §4 сумму W35 не сверяет - правило по дням в разделе «Что означают эталоны» ниже |

Метод сверки в релизе (runbook `docs/operations/release-m01.md` §4): для W10 - `sum(orders_count)`, `sum(revenue_rub)` из `fact_cabinet_daily_current` тенанта `amirova-test` за дни недели; для W35 с 08.09 - по дням (раздел «Что означают эталоны» ниже); формулы дня - `_bmad-output/specs/spec-wb-morning-brief/glossary.md` (конвенции D27). Полные фикстуры, по которым числа получены, - вне git (`~/signal-inputs/fixtures/wb-api/`, D15); по обезличенным фикстурам репозитория суммы невоспроизводимы (`epics.md`, Epic 6, коэффициент 0.8-1.2).

`UNKNOWN` (закрыть до или в день релиза): (1) чем именно считались числа 30.08 - скрипт/запрос эталона в репозитории не лежит, Story 6.1 создаёт `verification/golden/`; (2) входит ли в эталон W35 день 30.08 и в каком объёме: снимок 30.08 снят в 05:59-06:01 UTC (день 30.08 неполный: `lastChangeDate` до `2026-08-30T07:01:10`), а релиз 1.14 грузит пару 31.08 (полный 30.08) и переписывает дни с 27.08 живым хвостом. W10 от этого не зависит. Если в релизе разошёлся только W35 при сошедшемся W10 - сверять дни 24-29.08 по отдельности и решать с Mike/Владиславом (Story 6.1/6.4), не откатывать по умолчанию. Оба пункта закрыты 08.09 на репетиции - см. конец раздела «Репетиция цепочки 1.14 на VPS» ниже.

## Репетиция цепочки 1.14 на VPS (08.09.2026, D35)

Стенд: compose-проект `proxima-rehearsal` (`infra/compose.yaml` + `infra/compose.rehearsal.yaml`), свой postgres на `127.0.0.1:5434`, корень `~/orca/rehearsal`; код `main` `1c5e256`, скрипт `tools/rehearsal_run.sh` (PR #111), команда `all --live`. Боевой проект `proxima-ai` не трогался (`proxima-ai-postgres-1` рядом, аптайм 9 дней). Прогон 13:10:14Z → 13:11:55Z, `exit=1` только из-за гейта §4 (разбор ниже); все четыре прогона ledger - `SUCCEEDED`. Время везде UTC 08.09.2026, источник - лог прогона и `collector_runs` стенда.

| Шаг | Факт |
|---|---|
| `up` | образы `collector`, `control-plane`, `control-plane-admin` собраны; `apply-migrations` через `control-plane-admin` → `migrations: already current` (свежий том: initdb-mount применил 001-018); `schema_migrations` count=18, max=18 |
| `provision-runtime-roles.sh` ×2 | оба `ok (5 login roles, database proxima_test)`, WARNING нет; второй проход - только `NOTICE … has already been granted membership` (идемпотентен) |
| CAS-импорт пары 31.08 | `content_sha256` `d2f1dc95…` (sales), `0c0318ff…` (orders), `retrieved_at 2026-08-31T15:53:41Z`; `raw/` - `1010:1010` |
| `backfill` | run `9c1a9d1a-9b93-44b8-9a6e-e5c583a014b8`, SUCCEEDED, ledger 13:11:37.886 → 13:11:38.651 (событие `run-ledger:succeeded` 13:11:48.569: `finished_at` = `CURRENT_TIMESTAMP` транзакции, закрывающей прогон, т.е. её начало - `run-ledger.ts:79`); `run_day 2026-08-31`, `floor 2026-03-01`, 183 дня; orders 13 386 received / 13 386 inserted / 0 skipped, sales 10 675 / 10 675 / 0; `nm_daily` 201 subjects, 36 783 rows; `per_nm_sums_vs_cabinet` PASS (183 дня, 0 расхождений) |
| `tail --live` (`collect`) | run `c583eb57-3da6-473d-b26a-7899b5cee3cb`, SUCCEEDED, ledger 13:11:49.748 → 13:11:50.407 (`run-ledger:succeeded` 13:11:51.407); `--date-from 2026-08-27`, `source: flag`, `run_day 2026-09-08`; два read-вызова (лог ниже); orders 570 received / 353 inserted / 217 skipped, sales 406 / 215 / 191; версии 12 дней (27.08-07.09), `input_runs 1` (бэкфилл); `nm_daily` 203 subjects, 2 436 rows; `per_nm_sums_vs_cabinet` PASS (12 дней). Все 353 вставленных наблюдения новее пары 31.08 (`last_change_at` 2026-08-31 17:22:54Z … 2026-09-08 13:02:53Z), 50 из них с `date` раньше `dateFrom` (фильтр по `lastChangeDate`, как в факте flag=0 выше); 217 skipped = уже были в паре |
| токен | боевой statistics-токен (копия в `secrets/amirova-test_wb_statistics_token`, 422 байта, 0600 1010:1010) прошёл `assertLeastPrivilegeToken(token, 'statistics')` (`services/collector/src/jobs/collect.ts:132`): бит read-only и единственная категория statistics, срок не истёк. Проверка стоит до открытия прогона и fail-closed, отдельной строки в лог не пишет - SUCCEEDED прогона и есть факт прохождения |
| `norm` | run `86d83caf-3897-4369-90b3-2e5961591fe2`, SUCCEEDED, 13:11:53.017 → 13:11:53.019; `evaluation_day=2026-09-07 sample_days=14/14 status=ok`; `norm_daily_current` - 2 строки (`orders` 26.50, `revenue` 35 465.56), обе `ok`, `window_days 14` |
| `brief` | run `24482522-eec1-4223-bdb3-ae66ac1739e3`, SUCCEEDED, 13:11:54.561 → 13:11:54.758; `brief_day=2026-09-07 status=ok, orders 30 vs norm 26.50 (13.2%), signals 15 (sku 203, insufficient 186, threshold not applied)`; `brief_current` = `2026-09-07`, `ok`, этот run_id |
| `data_status_current` | `last_full_day 2026-09-07`, `collected_at 2026-09-08 13:11:50.406776+00`, `stale = false` |
| `collector_run_inputs` | `collect ← backfill`; `norm ← backfill, collect`; `brief ← norm, backfill, collect` - цепочка для транзитивного удаления по AD-3 записана |

Ledger `git_sha` / `image_id`: у всех четырёх прогонов `git_sha = 1c5e25646d8da5e8fe74d0a05397dbb431d51e52` (полный SHA `main`; скрипт передаёт `-e PROXIMA_GIT_SHA=$(git rev-parse HEAD)`), `image_id = NULL` у всех четырёх - `rehearsal_run.sh` не передаёт `PROXIMA_IMAGE_ID` (в релизе его ставит `tools/morning_run.sh:46,69` из `docker image inspect`, AD-6; на 15.09 проверить, что колонка заполнена). `notes`: `NULL` у `backfill`/`collect`, `evaluation_day=2026-09-07` у `norm`, `brief_day=2026-09-07` у `brief`.

### Лог двух живых вызовов (UTC 08.09.2026, исключение D35)

Время - события `fetched` в логе прогона `c583eb57…` (`collect.log` в корне стенда принадлежит root и здесь не читался); байты не логируются; ответы легли в CAS стенда `~/orca/rehearsal/raw/objects/sha256/`, в фикстуры `~/signal-inputs/` не копировались.

| Время | Эндпоинт | Параметры | Код | Строк (distinct) |
|---|---|---|---|---|
| 13:11:50.149 | GET statistics `supplier/orders` | dateFrom=2026-08-27&flag=0 | 200 | 570 (570) |
| 13:11:50.405 | GET statistics `supplier/sales` | dateFrom=2026-08-27&flag=0 | 200 | 406 (406) |

### Гейт §4: W10 сошёлся до копейки, W35 - вопрос определения эталона

`check` напечатал `W10 649 / 700860.50` против ожидаемых `649 / 700860.00` и `W35 228 / 282836.08` против `225 / 263089.00` - FAIL по обеим, `exit=1`. Разбор по фикстурам (`jq`, формулы `glossary.md`: заказы = строки `orders` с `isCancel == false` по `date[0:10]`; выручка = `sum(finishedPrice)` строк `sales` с `saleID` на `S`) и по стенду:

**W10 (02.03-08.03) сходится; расхождение - в точности записи.** Фикстура 30.08 (`supplier-orders/20260830T060041Z…`, `supplier-sales/20260830T055939Z…`) → **649** заказов и **700 860.50** ₽; пара 31.08 → те же 649 и 700 860.50 (март вне окна изменений); БД стенда - 649 / 700 860.50. Значит числа 30.08 считались этими же формулами, а «700 860» в `SPEC.md:33` / `epics.md:29` записано с округлением до рубля; `rehearsal_run.sh` кодировал его как `700860.00` и честно дал FAIL. Эталон в таблице выше уточнён до копеек, константа скрипта `W10_EXPECTED` - тоже; SPEC и epics оставлены в округлённой форме (планировочные артефакты 30.08 не правятся).

**W35 (24.08-30.08) не сходится, и конвейер здесь ни при чём.**

- Выручка: 282 836.08 в БД = пара 31.08 той же формулой (282 836.08). Снимок 30.08 даёт 263 088.84 = записанные «263 089» (округление до рубля). Вся разница - день 30.08: в снимке 05:59 UTC он держит 3 продажи на 2 620 ₽, в паре 31.08 и в БД - 31 продажу на 22 367.24 ₽; дни 24-29.08 по выручке совпадают во всех трёх источниках копейка в копейку (62 146.87 / 29 247.90 / 44 956.00 / 50 789.89 / 32 187.38 / 41 140.80).
- Заказы: 228 в БД, 225 - снимок 30.08 (день 30.08 в нём - 1 заказ), 254 - пара 31.08. По дням, `ok/cancel` по `isCancel`:

| День | Снимок 30.08 | Пара 31.08 | `stg_wb_orders_latest` стенда (последнее наблюдение) | `fact_cabinet_daily_current`: `orders_count`/`cancelled_count` | Версия факта |
|---|---|---|---|---|---|
| 24.08 | 57/2 | 55/6 | 55/8 | 55/6 | `backfill` |
| 25.08 | 39/6 | 40/7 | 39/10 | 40/7 | `backfill` |
| 26.08 | 29/2 | 28/4 | 23/10 | 28/4 | `backfill` |
| 27.08 | 36/0 | 36/0 | 33/5 | 33/5 | `collect` |
| 28.08 | 36/6 | 36/7 | 25/18 | 25/18 | `collect` |
| 29.08 | 27/0 | 27/0 | 21/8 | 21/8 | `collect` |
| 30.08 | 1/0 | 32/0 | 26/6 | 26/6 | `collect` |

Дни 24-26.08 в фактах = пара 31.08 точь-в-точь (у них одна версия - прогон `backfill`). Дни 27-30.08 переписаны живым хвостом (две версии, `_current` - прогон `collect`) и равны последним наблюдениям точь-в-точь: `isCancel` продолжает переключаться после снимка (28.08: 36/7 в паре 31.08 → 25/18 к 08.09; 25.08 между снимками - и вверх, 39 → 40: строки дня дописываются задним числом, 45 → 47 строк). `_latest` → факт → сумма без потерь: конвейер согласован.

Свойство определения, не дефект: для 24-26.08 staging стенда уже держит более поздние отмены (55/8, 39/10, 23/10 - те самые наблюдения хвоста с `date` раньше `dateFrom`), но факты остаются 55/6, 40/7, 28/4, потому что окно перезаписи хвоста начинается с `--date-from 2026-08-27` (AD-2: `run_day − 3` артефакта; агрегатор версионирует только `[floor, run_day − 1]`). Факт дня T - «заказы, какими их видел прогон утра T+3»; позже он меняется только явным `--date-from` глубже. Что считать эталоном W35 - решено Mike 08.09 (~13:40 UTC), раздел «Что означают эталоны» ниже; когда день «замораживается» (ширина окна перезаписи) - открытый вопрос Story 6.1/6.3, там же, кода не меняет.

### Что означают эталоны (уточнение таблицы «Эталоны недельных сумм», 08.09.2026)

| Неделя | Заказы | Выручка, ₽ | Что это | Правило гейта §4 (решение Mike в чате, 08.09 ~13:40 UTC) |
|---|---|---|---|---|
| W10 | 649 | 700 860.50 | фикстура 30.08, пересчёт 08.09 по формулам глоссария; пара 31.08 и БД стенда дают то же | сумма недели, равенство копейка в копейку (`W10_EXPECTED` в `rehearsal_run.sh`) |
| W35 | 225 | 263 089 | снимок 30.08 05:59 UTC с неполным днём 30.08 (1 заказ, 3 продажи на 2 620 ₽); после пары 31.08 + живого хвоста невоспроизводим (стенд 08.09: 228 / 282 836.08) | сумма недели **не сверяется**; вместо неё - по дням: 24-26.08 равны паре 31.08 точь-в-точь (таблица ниже), 27-30.08 равны последним наблюдениям самой базы (правило ниже); любое расхождение = гейт не пройден |

**Дни 24-26.08 (до окна живого хвоста `--date-from 2026-08-27`): равенство паре 31.08 точь-в-точь.** Константы - пересчёт пары 31.08 (`supplier-orders/20260831T155341Z…`, sha256 `0c0318ff…`; `supplier-sales/20260831T155341Z…`, sha256 `d2f1dc95…`) 08.09 по формулам глоссария через `jq`: `orders_count` = строки `orders` с `isCancel == false` по `date[0:10]`, `cancelled_count` = с `isCancel == true`, `revenue_rub` = `sum(finishedPrice)` строк `sales` с `saleID` на `S` по `date[0:10]`; `fact_cabinet_daily_current` стенда 08.09 (единственная версия - прогон `backfill`) дала те же значения. Скрипт держит их в `W35_DAYS_EXPECTED` (`tools/rehearsal_run.sh`), runbook §4 - в ожидаемом выводе SQL.

| `calendar_day` | `orders_count` | `cancelled_count` | `revenue_rub`, ₽ | Источник |
|---|---|---|---|---|
| 2026-08-24 | 55 | 6 | 62 146.87 | пара 31.08 (`jq`, 08.09); БД стенда 08.09 - то же |
| 2026-08-25 | 40 | 7 | 29 247.90 | те же |
| 2026-08-26 | 28 | 4 | 44 956.00 | те же |

**Дни 27-30.08 (переписаны живым хвостом): внутренняя согласованность, внешней константы нет.** WB переключает `isCancel` неделями (28.08: 7 → 18 отмен между 31.08 и 08.09), поэтому заказы этих дней в релизе 15.09 будут другими, чем на репетиции, и сравнивать их не с чем, кроме самой базы. Правило: `fact_cabinet_daily_current.orders_count` / `cancelled_count` дня равны счёту строк `stg_wb_orders_latest` за московский день `payload->>'date'` (первые 10 символов бесзонного текста WB - `services/collector/src/wb/msk-day.ts`, AD-7) с `isCancel` не-true / true (так считает `services/collector/src/facts/cabinet-daily.ts`). На стенде 08.09 обе проекции дали 33/5, 25/18, 21/8, 26/6. SQL - runbook §4; `rehearsal_run.sh check` делает то же для дней `DATE_FROM..2026-08-30`.

`UNKNOWN` из раздела «Эталоны»: (1) закрыт - числа 30.08 воспроизводятся формулами глоссария по фикстуре 30.08 (скрипта эталона в репозитории по-прежнему нет, `verification/golden/` - Story 6.1); (2) закрыт - день 30.08 в эталон W35 входит в объёме снимка 05:59 UTC (1 заказ, 3 продажи на 2 620 ₽), поэтому эталон W35 после полной пары 31.08 не воспроизводится по построению.

**Открытый вопрос для Story 6.1/6.3 - определение `orders_count` («заказы на момент `run_day − 3`»).** Факт дня T - заказы, какими их видел прогон утра T+3: окно перезаписи AD-2 (`dateFrom = run_day − 3`, версионируются только дни `[floor, run_day − 1]`) замораживает день, а отмены, проставленные WB позже, в факт не попадают, пока день не переписан явным `--date-from` глубже. Числа стенда 08.09: 28.08 - 7 → 18 отмен между 31.08 и 08.09; дни 24-26.08 в фактах 55/40/28 «ok», тогда как последние наблюдения `stg_wb_orders_latest` уже дают 55/39/23 «ok» (55/8, 39/10, 23/10 ok/cancel). Определение записано в глоссарий («Заказы»); ширина окна - три дня или больше, и что тогда считать эталоном недели - вопрос Владиславу в Story 6.1/6.3 с этими числами; кода не меняет (решение Mike 08.09, ~13:40 UTC).

## Репетиция наката миграций 007-018 поверх боевого дампа (09.09.2026, M1/D37)

Закрывает `docs/state/RELEASE-READINESS-1.14.md` §6 п. 4: до 09.09 миграции 007-018 нигде не накатывались поверх живой схемы 6 с данными - репетиция D35, CI `apply-migrations-in-container` (`images.yml`) и `pg-roundtrip` стартуют с пустого тома. Стенд одноразовый и отдельный: compose-проект `proxima-migtest` (postgres `127.0.0.1:5435`, своя сеть `proxima-migtest-private`, свой том и свой каталог секретов, корень `~/orca/migtest`); override `compose.migtest.yaml` снимает монтирование `db/migrations` в `docker-entrypoint-initdb.d` (`volumes: !override`) - иначе initdb поднял бы сразу схему 18 и проверять было бы нечего. Боевой `proxima-ai-postgres-1` не трогался. Все числа ниже сняты read-only (`docker exec … psql -tA`, только SELECT) 09.09.2026 10:15-10:25 UTC; сверка - против стенда `proxima-rehearsal` (D35), собранного с нуля.

**Порядок.** (1) поднять пустой postgres; (2) восстановить ночной дамп `/var/backups/proxima/2026-09-09-proxima.sql.gz` (64 565 байт gz, 620 297 байт SQL, снят 03:00 UTC); (3) `docker compose --profile jobs run --rm control-plane-admin make apply-migrations ENV_FILE=infra/jobs.env` - exit 0, 007…018 одним проходом; (4) `infra/bootstrap/provision-runtime-roles.sh` дважды; (5) сверка структуры со стендом из нуля.

Что копия действительно боевая, видно по самому ledger: у миграций 1-6 в `schema_migrations` стоят боевые `applied_at` - `2026-08-13 09:06:35.795692+00` … `2026-08-14 17:53:26.058255+00`; они пережили restore. Миграции 7-18 легли `2026-09-09 10:15:17.228679+00` → `10:15:17.518809+00`, то есть весь накат - один проход в 0.29 с. Для сравнения: на стенде из нуля все 18 строк датированы `2026-09-08 13:11:23`.

### До и после

| Что | База из дампа (схема 6) | После 007-018 | Как получено |
|---|---|---|---|
| `schema_migrations` | 6 строк, max 6 | **18 строк, max 18** | `SELECT count(*), max(version)` |
| объекты в `public` | 13 таблиц, 0 вьюх | **48** = 35 таблиц + 13 вьюх | `information_schema.tables` |
| политики RLS | 0 | **58** на 24 таблицах | `pg_policies`; сумма `CREATE POLICY` в 007-018 - те же 58 |
| роли `proxima*` | 2 (`proxima`, `proxima_diagnostics`) | **10** после миграций, **15** после `provision-runtime-roles` | `pg_roles`; 8 NOLOGIN-групп создают 009 и 011, 5 LOGIN-ролей - скрипт provision |

Состав 13 таблиц дампа = ровно то, что создают 001-006: `artifact_manifests`, `business_signal_raw_artifacts`, `business_signal_runs`, `dim_product`, `dim_warehouse_map`, `intake_attempts`, `raw_wb_analytics_responses`, `schema_migrations`, `source_artifacts`, `stg_wb_nm_report_rows`, `tenants`, `wb_analytics_quota_events`, `wb_analytics_report_tasks`. Ни вьюх, ни политик, ни ролей в 001-006 нет - отсюда нули в левой колонке.

### Данные пилота: ни одна строка не изменилась

| Таблица | Строк до | Строк после |
|---|---|---|
| `stg_wb_nm_report_rows` | 1220 | 1220 |
| `dim_warehouse_map` | 60 | 60 |
| `business_signal_raw_artifacts` | 27 | 27 |
| `business_signal_runs` | 11 | 11 |
| `dim_product` | 9 | 9 |
| `raw_wb_analytics_responses` | 7 | 7 |
| `tenants` | 2 | 2 |

Новые таблицы лестницы созданы и пусты: `collector_runs`, `stg_wb_orders_obs`, `fact_cabinet_daily`, `norm_daily`, `brief_daily`, `fact_nm_daily`, `fact_funnel_daily` - все 0 строк. `provision-runtime-roles.sh` прошёл дважды с exit 0; второй проход отличается только пятью `NOTICE: role … has already been granted membership` - по числу членств, которые скрипт выдаёт (`proxima_collector → proxima_job_collector`, `proxima_collector → proxima_source_publisher`, `proxima_norm → proxima_job_norm`, `proxima_webapp → proxima_webapp_readonly`, `proxima_janitor → proxima_run_janitor`; все пять на стенде есть).

### Обновлённая схема структурно совпадает со схемой из нуля

Сравнение инвентарей `proxima-migtest` (дамп + 007-018) и `proxima-rehearsal` (initdb 001-018), схема `public`:

| Инвентарь | migtest | rehearsal | Расхождений |
|---|---|---|---|
| колонки (`information_schema.columns`: тип, длина, nullable, default) | 429 | 429 | **0** |
| индексы (`pg_indexes`, полный `indexdef`) | 86 | 86 | **0** |
| политики (`pg_policies`: cmd, `qual`, `with_check`, роли) | 58 | 58 | **0** |
| таблицы + вьюхи | 48 | 48 | **0** |
| гранты на таблицы (`information_schema.role_table_grants`) | 505 | 457 | **48**, все - лишние в migtest |

Порядок наката 6 → 18 даёт ту же схему, что и сборка с нуля: ни одной колонки, ни одного индекса, ни одной политики в разнице. Единственное расхождение - гранты, и оно объясняется целиком одной строкой боевой базы (ниже).

### Находка 1: обычный дамп базы несёт GRANT'ы, но не роли

Первый restore упал: `ERROR: role "proxima_diagnostics" does not exist`. `pg_dump` одной базы (не `pg_dumpall`) выгружает `GRANT … TO proxima_diagnostics`, но сами роли живут в кластере и в дамп не попадают. Лечится созданием роли-заглушки `NOLOGIN` до restore; со второго раза восстановление прошло без единой ошибки. Для релиза 15.09 накат идёт по живой базе, где роли на месте, так что прямого пути это не касается - но касается **отката §7 и `restore_check.sh`**: восстановление боевого дампа в чистый кластер требует, чтобы все роли-грантополучатели существовали заранее.

### Находка 2: `proxima_diagnostics` бесшумно получает SELECT на новые таблицы

Все 48 «лишних» грантов в обновлённой копии - `SELECT` роли `proxima_diagnostics`, ровно по одному на каждый из 48 объектов `public`; в обратную сторону (только в rehearsal) - ноль строк. Причина видна в `pg_default_acl` боевой копии: две записи `proxima_diagnostics=r/proxima` (объекты `r` - таблицы и `S` - последовательности, схема `public`), то есть на боевой базе когда-то выполнили `ALTER DEFAULT PRIVILEGES FOR ROLE proxima GRANT SELECT ON TABLES/SEQUENCES TO proxima_diagnostics`. На стенде из нуля `pg_default_acl` пуст. Из 48 объектов 13 получили грант вместе с дампом, а 35 - все таблицы и вьюхи, созданные 007-018, - автоматически в момент создания.

Что это даёт на практике, проверено на стенде: `proxima_diagnostics` - `NOLOGIN`, `NOBYPASSRLS`, и **ни одна из 58 политик её не называет**. Под `SET LOCAL ROLE proxima_diagnostics` она читает `tenants` (2 строки - на этой таблице RLS не включён) и получает **0 строк** из `stg_wb_nm_report_rows`, `raw_wb_analytics_responses`, `business_signal_runs`. То есть право есть, данных нет: расширение видимости ожидаемое и безвредное, отдельной правки не требует. Заметить его стоит в двух местах - при аудите грантов после релиза (сверка «схема как из нуля» покажет ровно эти 48 строк) и в Story 6.4, если роль аналитика когда-нибудь захотят строить поверх `proxima_diagnostics`.

Побочно из того же инвентаря: `proxima_sandbox` - единственная не-владельческая роль с `rolbypassrls = true` (роль песочницы Story 1.8; `provision-runtime-roles.sh` отзывает у неё `CONNECT` к `postgres`/`template0`/`template1` и выдаёт только к `proxima_test`). На обоих стендах одинаково, к накату отношения не имеет.

### Открытые вопросы репетиции

- Идемпотентность `provision-runtime-roles.sh` подтверждена прогоном оркестратора (два раза exit 0); при перепроверке фактов скрипт повторно не запускался - это запись, а не чтение. Косвенно её держат пять членств выше.
- Точный текст строки `migrations: 007_…, …, 018_nm_daily.sql` и сообщение первого упавшего restore - из вывода оркестратора; `~/orca/migtest/logs/` пуст, файла лога не осталось. Косвенное подтверждение наката одним проходом - разброс `applied_at` у 007-018 в 0.29 с.
- `pg_default_acl` самой боевой базы напрямую не читался (`proxima-ai-postgres-1` не трогался) - находка 2 доказана на её восстановленной копии.

## Формат бэкапа (31.08.2026, факт)

`/var/backups/proxima/YYYY-MM-DD-{proxima,proxima_dev}.sql.gz` - локально **plain gzip, без age**; age-ключи (`backup_age_key.txt` 0600 root, `backup_age_recipient` 0644) используются скриптом только для S3-копии. `proxima-pg-backup.sh` снят в `infra/backup/` (sha256 `d29feb24…`). Для `proxima-restore-check@` локальный дамп: `gunzip | psql` без age; AD-17 уточнён.

## Остатки (02.09.2026, OQ-13)

Разведка по разрешению Mike 02.09.2026 (план «проверка PRD v2», ветка 3): три read-вызова с сервера токеном категории «Аналитика» (`/etc/proxima-ai/secrets/wb_analytics_token`, подстановка через `sudo -n cat`, значение не выводилось). Ответы и заголовки ответов - фикстуры на VPS, без заголовков авторизации. В БД и код ничего не записано. Поводом были факты из зеркала спецификации OpenAPI (ресёрч R2, уверенность средняя); ниже - что подтвердилось живым вызовом.

| Вызов | Статус | Что вернул | Лимит из заголовков | Размер, время | Фикстура |
|---|---|---|---|---|---|
| `POST analytics /api/analytics/v1/stocks-report/wb-warehouses`, тело `{"params":{"nmIDs":[],"limit":50,"offset":0}}` (форма из `wb-client.ts:166`) | **200** | `data.items[]` - 444 строки с полями `nmId`, `chrtId`, `warehouseId`, `warehouseName`, `regionName`, `quantity`, `inWayToClient`, `inWayFromClient`; пустой `nmIDs` отдаёт весь кабинет, строка = размер × склад; `limit` ограничивает не строки (444 > 50), вероятно - число nmId на страницу (не проверено) | `x-ratelimit-limit: 1`, `x-ratelimit-remaining: 0` - **измеренный лимит 1 запрос на окно** (период окна в заголовках не назван; зеркало спецификации давало 3/мин - расхождение) | 76 608 B, 1.89 s | `analytics/stocks-report-wb-warehouses/20260902T130436Z__stocks_probe.json` |
| `POST analytics /api/v2/nm-report/downloads`, `reportType: STOCK_HISTORY_DAILY_CSV`, `params` как у `DETAIL_HISTORY_REPORT` (`nmIDs`, `startDate`, `endDate`, `timezone`, `aggregationLevel`) | **400** `Invalid request body` | `decode CSVDailyStocksParams: … decode field "params": invalid: currentPeriod (field required), stockType (field required), skipDeletedNm (field required)` - тип отчёта **существует и распознан**, отказа по подписке нет; тело должно нести `currentPeriod`, `stockType`, `skipDeletedNm` (те же параметры, что у метода остатков в спецификации). Задача не создана, квота не потрачена | `x-ratelimit-limit: 3`, `remaining: 2` (3/мин, как на 30.08) | 289 B, 0.62 s | `analytics/nm-report-downloads/20260902T130459Z__create_stock_history.json` |
| `GET analytics /api/v2/nm-report/downloads` | **200** | `data[]` - 2 задачи, обе `detail_history_report`, `SUCCESS`, окна `08-28..09-02` (создана `2026-09-02 01:04:29`) и `08-27..09-01` (`2026-09-01 01:03:43`), ~8 КБ - внешний потребитель токена продолжает создавать отчёт ежедневно (D20) | `x-ratelimit-limit: 3`, `remaining: 2` | 391 B, 0.51 s | `analytics/nm-report-downloads/20260902T130520Z__list.json` |

Выводы для реестра AD-4 и OQ-13:

- **Срез остатков по складам есть** и уже пригоден для `fact_stock_daily` при ежедневном снимке: поля дают остаток и «в пути» по каждому размеру и складу с регионом. Лимит по заголовку - 1 запрос на окно; пагинация по `offset` при полном кабинете (444 строк за один ответ при `limit 50`) требует отдельной проверки семантики `limit`. Кандидат на включение в реестр (новый AD, OQ-13).
- **Дневная история остатков через CSV `STOCK_HISTORY_DAILY_CSV` доступна на этом токене без подписки «Джем»** (отказа по подписке не было); обязательные параметры - `currentPeriod`, `stockType`, `skipDeletedNm`. Глубина `currentPeriod` и формат CSV не проверены: нужен один повторный вызов с исправленным телом и скачивание файла.
- Расхождение с зеркалом спецификации: лимит `stocks-report` 1 (заголовок) против 3/мин (зеркало). Приоритет у живого замера; в PRD и отчёте R2 уверенность по лимиту понижена.

### Лог вызовов (UTC 02.09.2026)

| Время | Вызов | Тело / параметры | Статус | Время | Байт | Фикстура |
|---|---|---|---|---|---|---|
| 13:04:36 | POST analytics `stocks-report/wb-warehouses` | `nmIDs: [], limit 50, offset 0` | 200 | 1.89 s | 76 608 | `analytics/stocks-report-wb-warehouses/20260902T130436Z__stocks_probe.json` |
| 13:04:59 | POST analytics `nm-report/downloads` | `STOCK_HISTORY_DAILY_CSV`, params в форме DETAIL_HISTORY_REPORT | 400 | 0.62 s | 289 | `analytics/nm-report-downloads/20260902T130459Z__create_stock_history.json` |
| 13:05:20 | GET analytics `nm-report/downloads` | - | 200 | 0.51 s | 391 | `analytics/nm-report-downloads/20260902T130520Z__list.json` |
| 13:10:44 | POST analytics `nm-report/downloads` | `STOCK_HISTORY_DAILY_CSV`, `params: {currentPeriod: {start: 2026-08-26, end: 2026-09-01}, stockType: "", skipDeletedNm: true}` | 200 `{"data": "Началось формирование файла/отчета"}` | 0.87 s | 77 | `analytics/nm-report-downloads/20260902T131044Z__create_stock_history_v2.json` |
| 13:11:50 | GET analytics `nm-report/downloads` | - | 200; задача `SUCCESS` через ~65 с | 0.51 s | 568 | `analytics/nm-report-downloads/20260902T131150Z__list_after_create.json` |
| 13:11:51 | GET analytics `nm-report/downloads/file/{id}` | - | 200, `application/zip` | 0.59 s | 12 203 | `analytics/nm-report-downloads/20260902T131151Z__download_stock_history.bin` |

## async CSV глубина (проба Story 3.0, 08.09.2026)

Выполнено оркестратором с VPS по исключению из решения 7а (D32), analytics-токен read-write (`wb_analytics_token`), ответы и заголовки сохранены в `~/signal-inputs/fixtures/wb-api/analytics/nm-report-downloads/20260908T06*__probe30_*`. Запросов всего 6: список до создания, create с телом без `id` (400), create, два status, file; отчётов создано 1 (квота D20: 1 из 20 в сутки).

| Факт | Значение | Источник |
|---|---|---|
| `POST nm-report/downloads` без клиентского `id` | **400** `{"title":"Invalid request body","detail":"invalid: id (field required)"}` - `id` (UUID клиента) обязателен, как в `tools/wb_async_report.py` `build_request` | `20260908T061830Z__probe30_create.json` |
| Максимальный `startDate` для `DETAIL_HISTORY_REPORT` | **6 месяцев принято**: `startDate: 2026-03-08`, `endDate: 2026-09-07`, `aggregationLevel: day`, `nmIDs: []` → 200 `{"data":"Началось формирование файла/отчета"}`; спека «до года» глубже не проверялась | `20260908T062012Z__probe30_create2.request.json`, `…__probe30_create2.json` |
| Время готовности | `SUCCESS` через **≈95 с** после создания (создан 06:20:12, первый status 06:21:48 уже SUCCESS) | `…__probe30_status1.json` |
| Размер | ZIP **289 118 байт**, один CSV `<id>.csv`, **32 172 строки** данных, **184 дня** (2026-03-08..2026-09-07), **328 nmId** | `…__probe30_file.bin` |
| Колонки CSV (`DETAIL_HISTORY_REPORT`, day) | `nmID, dt, openCardCount, addToCartCount, ordersCount, ordersSumRub, buyoutsCount, buyoutsSumRub, cancelCount, cancelSumRub, addToCartConversion, cartToOrderConversion, buyoutPercent, addToWishlist, currency` - длинный формат (строка на nmId × день), в отличие от широкого `STOCK_HISTORY_DAILY_CSV` (02.09) | заголовок CSV в `…__probe30_file.bin` |
| Поле `name` в списке | равно `userReportName` запроса (`proxima-probe30-2026-03-08-2026-09-07`); отчёты внешнего потребителя называются `detail_history_report` → guard Story 3.2 по префиксу `proxima-<tenant>-` возможен | `…__probe30_status1.json` |
| Часовой пояс `createdAt` | **UTC**: `createdAt: 2026-09-08 06:20:12` при create в 06:20:13Z; чтение D20 (UTC → день МСК) подтверждено | `…__probe30_status1.json` + журнал `logs/day-2026-09-08/probe-3.0.log` |
| Лимиты | `x-ratelimit-limit: 3`, `remaining: 2` на всех вызовах (3/мин, как 30.08 и 02.09) | заголовки `.headers` |
| Внешний потребитель | в списке до создания 2 отчёта `detail_history_report` за 2026-09-03..08 (создан 2026-09-08 00:50:38 UTC) и 09-02..07 - продолжает ежедневно (D20, OQ-10) | `20260908T061829Z__probe30_list_before.json` |

Следствия: Story 3.3 - `CSV_COLUMN_MAP` переводится на реальные имена (`openCardCount → open_card`, `addToCartCount → cart`, `ordersCount → orders`, `ordersSumRub → orders_sum_rub`, `buyoutsCount → buyouts`, `buyoutsSumRub → buyouts_sum_rub`; `cancelCount`/`cancelSumRub`/конверсии/`addToWishlist`/`currency` - в payload); Story 3.2 - guard по префиксу и трактовка `createdAt` как UTC подтверждены; бэкфилл воронки на 6 месяцев одним отчётом реалистичен (CAP-6). Не проверено: глубина больше 6 месяцев; `STOCK_HISTORY_DAILY_CSV` глубина `currentPeriod`.

### Дневная история остатков - подтверждено (второй заход, 3 вызова по отдельному ок Mike)

- Тип отчёта `STOCK_HISTORY_DAILY_CSV` создаётся на токене «Аналитика» **без подписки «Джем»**; обязательные `params`: `currentPeriod {start, end}`, `stockType` (пусто = все), `skipDeletedNm`. Формирование заняло меньше 65 секунд; лимит создания и списка - 3/мин по заголовкам; квота 1 из 20 в сутки (D20: внешний потребитель тратит ещё 1).
- Файл - ZIP с одним CSV (`<id>.csv`, разделитель запятая): 787 строк данных за 7 дней. Колонки: `VendorCode, Name, NmID, SubjectName, BrandName, SizeName, ChrtID, OfficeName` и далее по одной колонке на дату (`26.08.2026 … 01.09.2026`) с остатком в штуках. Строка = артикул × размер (`ChrtID`) × склад (`OfficeName`: склады WB и «Свой склад»). Даты - в формате `dd.mm.yyyy`, широкий формат, для загрузки нужен unpivot по датам.
- Глубина `currentPeriod` назад **не проверена** (запрошено 7 дней); проверить одним вызовом с `start = 2026-03-01` в единице работы (кандидат на бэкфилл истории остатков).
- Вывод для OQ-13: источник дневной истории остатков есть на текущем токене, для `fact_stock_daily` достаточно ежедневного снимка через `stocks-report/wb-warehouses` (лимит 1 на окно) плюс еженедельного CSV как источника истории и сверки. Включение в реестр AD-4 - новый AD; фикстура CSV содержит реальные названия товаров кабинета - в git только после обезличивания (`tools/anonymize_fixture.py`, D15).
